import subprocess
import sys
from pathlib import Path

from lore.render import normalise_text, render_pdf

LORE = Path(__file__).resolve().parents[2] / "content" / "lore"


def test_normalise_text_replaces_typographic_characters():
    assert normalise_text("“Hello”—it’s… ‘fine’ – ok") == '"Hello"-it\'s... \'fine\' - ok'


def test_normalise_text_keeps_latin1_accents_and_drops_the_rest():
    assert normalise_text("Café naïve") == "Café naïve"
    assert normalise_text("dragon 🐉 here").encode("latin-1")


def test_render_pdf_produces_a_pdf():
    pdf = render_pdf("# Title\n\n## Section\n\nSome *text* with “quotes” — and dashes.\n")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_every_lorebook_renders():
    for md in LORE.glob("*.md"):
        assert render_pdf(md.read_text()).startswith(b"%PDF-"), md.name


def test_cli_writes_one_pdf_per_markdown(tmp_path):
    out = tmp_path / "out"
    rc = subprocess.run(
        [sys.executable, "-m", "lore.render", str(LORE), str(out)],
        cwd=Path(__file__).resolve().parents[1], check=False,
    ).returncode
    assert rc == 0
    assert sorted(p.stem for p in out.glob("*.pdf")) == sorted(p.stem for p in LORE.glob("*.md"))
