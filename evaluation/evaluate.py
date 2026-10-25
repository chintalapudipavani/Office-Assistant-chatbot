r"""Simple evaluation of retrieval quality and answer faithfulness.

Run from the project root, with the sample documents already loaded:

    python evaluation\evaluate.py --retrieval-only     (no LLM calls, no API cost)
    python evaluation\evaluate.py                      (also calls your configured LLM)

What it measures
  Retrieval  : for answerable questions, are the expected document AND the expected phrase
               among the chunks retrieved for that user? (hit rate)
  Refusal    : for unanswerable questions, does the system say it could not find the answer?
  Answer     : does the answer contain at least one expected keyword?
  Faithfulness (rough heuristic): every number in the answer must also appear in the
               retrieved text. Numbers that do not are reported as 'unsupported'.
This is a quick sanity check, not a scientific benchmark. Read the failing cases yourself.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from rag import pipeline, retriever  # noqa: E402

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def norm(text):
    return re.sub(r"\s+", " ", text.lower())


def numbers(text):
    text = re.sub(r"\[\d+\]", " ", text)          # ignore citation markers like [1]
    return {n.replace(",", "").rstrip(".") for n in NUMBER_RE.findall(text)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only", action="store_true", help="skip LLM calls")
    parser.add_argument("--file", default=str(ROOT / "evaluation" / "test_questions.json"))
    args = parser.parse_args()

    questions = json.loads(Path(args.file).read_text(encoding="utf-8"))
    users = {"employee": SimpleNamespace(is_staff=False, is_authenticated=True),
             "staff": SimpleNamespace(is_staff=True, is_authenticated=True)}

    ans_total = doc_hits = phrase_hits = kw_hits = kw_total = 0
    refuse_total = refuse_ok = 0
    unsupported_cases = []
    print(f"{'ID':>3}  {'Result':<8} Question")

    for q in questions:
        user = users[q.get("as", "employee")]
        chunks = retriever.retrieve([q["question"]], user)
        joined = norm(" ".join(c.text for c in chunks))
        notes = []

        if q["answerable"]:
            ans_total += 1
            doc_ok = any(q["expected_document"] in c.filename.lower() for c in chunks)
            phrase_ok = q["retrieval_phrase"].lower() in joined
            doc_hits += doc_ok
            phrase_hits += phrase_ok
            ok = doc_ok and phrase_ok
            notes.append(f"doc={'Y' if doc_ok else 'N'} phrase={'Y' if phrase_ok else 'N'}")
            if not args.retrieval_only:
                result = pipeline.answer_question(q["question"], user, [])
                kw_total += 1
                kw_ok = result.answer_found and any(k.lower() in result.answer.lower() for k in q["expected_any"])
                kw_hits += kw_ok
                ok = ok and kw_ok
                notes.append(f"keyword={'Y' if kw_ok else 'N'}")
                extra = numbers(result.answer) - numbers(" ".join(c.text for c in chunks))
                if extra:
                    unsupported_cases.append((q["id"], sorted(extra)))
                    notes.append(f"UNSUPPORTED NUMBERS {sorted(extra)}")
                if result.is_error:
                    notes.append(f"ERROR: {result.answer}")
        else:
            refuse_total += 1
            if args.retrieval_only:
                ok = len(chunks) == 0
                notes.append(f"chunks_retrieved={len(chunks)} (0 expected)")
            else:
                result = pipeline.answer_question(q["question"], user, [])
                ok = (not result.answer_found) and not result.is_error
                notes.append(f"answer_found={result.answer_found}")
            refuse_ok += ok
        print(f"{q['id']:>3}  {'PASS' if ok else 'FAIL':<8} {q['question']}  [{'; '.join(notes)}]")

    print("\n=== Summary ===")
    print(f"Retrieval - expected document found : {doc_hits}/{ans_total}")
    print(f"Retrieval - expected phrase found   : {phrase_hits}/{ans_total}")
    print(f"Unanswerable handled correctly      : {refuse_ok}/{refuse_total}")
    if not args.retrieval_only:
        print(f"Answers containing expected keyword : {kw_hits}/{kw_total}")
        print(f"Answers with unsupported numbers    : {len(unsupported_cases)} {unsupported_cases or ''}")
    else:
        print("(LLM answers were skipped: run without --retrieval-only to test answers and faithfulness.)")
    print("\nIf unanswerable questions fail, RAISE RETRIEVAL_MIN_SCORE in .env. "
          "If answerable ones fail to retrieve, LOWER it.")


if __name__ == "__main__":
    main()
