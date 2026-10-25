


"""Extract relevant answers from retrieved PDF passages without an API."""

import re


STOP_WORDS = {
    "what", "when", "where", "which", "who", "why", "how",
    "does", "do", "did", "is", "are", "was", "were", "have",
    "has", "had", "can", "could", "would", "should", "will",
    "the", "a", "an", "to", "of", "in", "on", "at", "by",
    "for", "from", "with", "about", "this", "that", "these",
    "those", "their", "they", "them", "it", "its", "and",
    "or", "if", "then", "please", "tell", "explain", "give",
    "show", "me", "my", "we", "our", "company", "employee",
    "employees", "person", "people", "following",
}

# Related words help connect different ways of asking a question.
RELATED_TERMS = {
    "conduct": {"behavior", "behaviour", "professional", "respect", "ethics"},
    "rules": {"policy", "policies", "guidelines", "requirements", "must"},
    "handbook": {"conduct", "behavior", "behaviour", "workplace", "policy"},
    "work": {"working", "workplace", "remote", "office", "employment"},
    "home": {"remote", "work", "telework", "flexible", "approval"},
    "remote": {"home", "work", "workplace", "approval", "manager"},
    "phishing": {"suspicious", "email", "security", "report", "links"},
    "email": {"phishing", "suspicious", "report", "security"},
    "security": {"password", "confidential", "incident", "report", "data"},
    "password": {"security", "confidential", "account", "credentials"},
    "onboarding": {"joining", "new", "documents", "identity", "forms", "HR"},
    "joining": {"onboarding", "documents", "identity", "employment"},
    "documents": {"records", "identity", "bank", "education", "forms"},
    "training": {"learning", "skills", "development", "manager", "request"},
    "performance": {"review", "goals", "feedback", "training", "manager"},
    "salary": {"payroll", "payment", "wages", "paid", "pay"},
    "payroll": {"salary", "payment", "wages", "payslip", "pay"},
    "payment": {"salary", "payroll", "paid", "payslip", "bank"},
    "leave": {"annual", "sick", "casual", "absence", "days", "holiday"},
    "annual": {"leave", "days", "accrues", "monthly", "carry-forward"},
    "sick": {"leave", "medical", "certificate", "paid", "days"},
    "casual": {"leave", "urgent", "personal", "days"},
    "paid": {"salary", "payroll", "leave", "payment"},
    "unpaid": {"leave", "salary", "payment"},
    "apply": {"request", "submit", "portal", "approval"},
    "request": {"apply", "submit", "approval", "manager"},
    "report": {"notify", "inform", "security", "manager", "HR"},
    "manager": {"approval", "supervisor", "request", "training"},
    "salary": {"payroll", "payment", "payslip", "bank", "monthly"},
    "monthly": {"month", "salary", "payroll", "accrues"},
}


def normalise(text):
    """Convert text to lowercase and standardise whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def words_in(text):
    """Return useful words, including short numbers and policy terms."""
    return set(re.findall(r"\b[a-z][a-z'-]*\b|\b\d+(?:\.\d+)?\b", normalise(text)))


def expand_terms(question):
    """Add related terms without removing the original question keywords."""
    original = words_in(question) - STOP_WORDS
    expanded = set(original)

    for word in original:
        expanded.update(RELATED_TERMS.get(word, set()))

    # Handle common word forms and policy phrases.
    if "accrues" in original or "accrue" in original:
        expanded.update({"accrues", "accrue", "accrual", "monthly", "month"})

    if "days" in original or "day" in original:
        expanded.update({"days", "day", "annual", "leave", "working"})

    if "paid" in original or "unpaid" in original:
        expanded.update({"paid", "unpaid", "payment", "salary"})

    return original, expanded


def extract_passages(user_message):
    """Read numbered passages from the RAG context."""
    pattern = (
        r"BEGIN PASSAGE\s+\S+\s+\[(\d+)\][^\n]*\n"
        r"(.*?)"
        r"\nEND PASSAGE\s+\S+\s+\[\1\]"
    )

    return re.findall(pattern, user_message, flags=re.DOTALL)


def split_sentences(text):
    """Split PDF text into sentences or separate bullet lines."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)

    cleaned = []
    for part in parts:
        part = re.sub(r"^\s*[-*•]+\s*", "", part).strip()
        part = re.sub(r"^\d+[.)]\s*", "", part).strip()

        if part and len(part) > 2:
            cleaned.append(part)

    return cleaned


def is_heading(sentence):
    """Identify short section headings that are not complete answers."""
    text = sentence.strip()
    word_count = len(text.split())

    return (
        word_count <= 5
        and len(text) < 55
        and not re.search(r"[.!?;:]$", text)
    )


def score_sentence(sentence, original_terms, expanded_terms, question):
    """Rank a sentence by topic relevance and direct question matches."""
    sentence_lower = normalise(sentence)
    sentence_words = words_in(sentence_lower)

    score = len(sentence_words & original_terms) * 3
    score += len(sentence_words & expanded_terms)

    # Reward exact topic phrases from the question.
    question_phrases = [
        phrase for phrase in (
            "code of conduct", "work from home", "work from home policy",
            "sick leave", "annual leave", "casual leave",
            "phishing email", "security incident", "employee handbook",
            "training request", "salary payment", "payroll schedule",
        )
        if phrase in question
    ]

    for phrase in question_phrases:
        if phrase in sentence_lower:
            score += 5

    # Prefer informative sentences over short headings.
    if is_heading(sentence):
        score -= 3

    if len(sentence.split()) >= 7:
        score += 1

    return score


def generate(messages):
    """Return relevant extractive answers using the supplied PDF passages."""
    user_message = next(
        (
            message.get("content", "")
            for message in reversed(messages)
            if message.get("role") == "user"
        ),
        "",
    )

    question_match = re.search(
        r"EMPLOYEE QUESTION:\s*(.*)",
        user_message,
        flags=re.DOTALL,
    )

    if not question_match:
        return "Please enter a question."

    question = normalise(question_match.group(1))
    passages = extract_passages(user_message)

    if not passages:
        return "No document passages could be extracted."

    original_terms, expanded_terms = expand_terms(question)

    # Collect sentences and retain their passage reference numbers.
    candidates = []
    seen = set()

    for number, passage in passages:
        sentences = split_sentences(passage)

        for index, sentence in enumerate(sentences):
            sentence_key = normalise(sentence)

            if sentence_key in seen:
                continue

            seen.add(sentence_key)

            score = score_sentence(
                sentence,
                original_terms,
                expanded_terms,
                question,
            )

            if score > 0:
                candidates.append({
                    "score": score,
                    "number": int(number),
                    "sentence": sentence,
                    "index": index,
                    "sentences": sentences,
                })

    if not candidates:
        return (
            "I couldn't find a clear answer in the available documents. "
            "Try asking with specific policy keywords."
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)

    # If the best match is a heading, include the following useful lines
    # from that same passage so answers do not contain only a heading.
    selected = []
    selected_keys = set()

    for candidate in candidates:
        sentence = candidate["sentence"]
        key = normalise(sentence)

        if key not in selected_keys:
            selected.append((candidate["number"], sentence))
            selected_keys.add(key)

        if is_heading(sentence):
            following = candidate["sentences"][
                candidate["index"] + 1:candidate["index"] + 4
            ]

            for next_sentence in following:
                next_key = normalise(next_sentence)

                if (
                    next_key not in selected_keys
                    and len(next_sentence.split()) >= 5
                ):
                    selected.append((candidate["number"], next_sentence))
                    selected_keys.add(next_key)

        if len(selected) >= 5:
            break

    # Prefer sentences that directly address the main topic.
    # Preserve document wording and source references.
    return "\n".join(
        f"- {sentence}"
        for number, sentence in selected[:5]
    )
    return " ".join(
    sentence.rstrip(".") + "."
    for number, sentence in selected[:5]
    )
