r"""Convert the .txt sample documents into real PDFs using PyMuPDF.

Run from the project root:   python tools\make_sample_pdfs.py
Each .txt file in sample_documents (and its 'optional' sub-folder) becomes a .pdf next to it.
Markers: '# ' title, '## ' heading, '- ' bullet, '---PAGE---' forces a new page.
"""
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    sys.exit("PyMuPDF is not installed. Activate your environment and run: pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent / "sample_documents"
PAGE_W, PAGE_H = 595, 842          # A4 in points
MARGIN = 56
BODY, BOLD = "helv", "hebo"


def wrap(text, font, size, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if pymupdf.get_text_length(trial, fontname=font, fontsize=size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def build_pdf(txt_path):
    doc = pymupdf.open()
    state = {"page": None, "y": 0}

    def new_page():
        state["page"] = doc.new_page(width=PAGE_W, height=PAGE_H)
        state["y"] = MARGIN

    def draw(text, font, size, indent=0, bullet=False, space_after=0):
        width = PAGE_W - 2 * MARGIN - indent
        leading = size * 1.35
        for i, line in enumerate(wrap(text, font, size, width)):
            if state["y"] + leading > PAGE_H - MARGIN:
                new_page()
            x = MARGIN + indent
            if bullet and i == 0:
                # a drawn dot (not text) keeps the extracted text clean
                state["page"].draw_circle((MARGIN + indent - 8, state["y"] + size * 0.62), 1.6, color=(0, 0, 0), fill=(0, 0, 0))
            state["page"].insert_text((x, state["y"] + size), line, fontname=font, fontsize=size)
            state["y"] += leading
        state["y"] += space_after

    new_page()
    for raw in txt_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line == "---PAGE---":
            new_page()
        elif line.startswith("# "):
            draw(line[2:], BOLD, 18, space_after=8)
        elif line.startswith("## "):
            state["y"] += 8
            draw(line[3:], BOLD, 13, space_after=3)
        elif line.startswith("- "):
            draw(line[2:], BODY, 10.5, indent=14, bullet=True, space_after=2)
        elif line == "":
            state["y"] += 5
        else:
            draw(line, BODY, 10.5, space_after=2)

    out = txt_path.with_suffix(".pdf")
    doc.save(str(out))
    pages = doc.page_count
    doc.close()
    return out, pages


def main():
    files = sorted(ROOT.glob("**/*.txt"))
    if not files:
        sys.exit(f"No .txt files found in {ROOT}")
    for txt in files:
        out, pages = build_pdf(txt)
        print(f"Created {out.relative_to(ROOT.parent)}  ({pages} page(s))")


if __name__ == "__main__":
    main()
