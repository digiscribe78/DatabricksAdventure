"""Render Markdown lorebooks into styled PDF "campaign books".

fpdf2's built-in fonts are latin-1 only, so typographic characters are normalised first.
That keeps the build free of system font dependencies.
"""

import sys
from pathlib import Path

import markdown
from fpdf import FPDF

_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}


def normalise_text(text: str) -> str:
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def render_pdf(markdown_text: str) -> bytes:
    html = markdown.markdown(normalise_text(markdown_text))
    pdf = FPDF(format="A5")
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Times", size=11)
    pdf.write_html(html)
    return bytes(pdf.output())


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m lore.render <lore_dir> <out_dir>", file=sys.stderr)
        return 2
    src, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    for md in sorted(src.glob("*.md")):
        (out / f"{md.stem}.pdf").write_bytes(render_pdf(md.read_text()))
        print(f"rendered {md.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
