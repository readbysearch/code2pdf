"""Big documents are rendered in parts (child processes) and joined; output must match one pass."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable
FIXED_EPOCH = "1767225600"  # 2026-01-01 00:00 UTC


def has_deps() -> bool:
    return subprocess.run([PYTHON, "-c", "import pygments, weasyprint, pypdf"], capture_output=True).returncode == 0


pytestmark = [pytest.mark.skipif(not has_deps(), reason="pygments/weasyprint/pypdf not available"),
              pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext not installed")]


@pytest.fixture(scope="module")
def parts():
    sys.path.insert(0, str(SCRIPTS))
    import parts
    return parts


@pytest.fixture
def project(temp_dir):
    root = temp_dir / "proj"
    files = {"a.py": 30, "b.md": 5, "lib/c.py": 150, "lib/deep/d.sh": 70, "z.py": 3}
    for rel, lines in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f"# {rel} line {n} — 你好\n" if n % 10 == 0 else f"value_{n} = {n}\n" for n in range(1, lines + 1))
        path.write_text(body)
    return root


def convert(root, output, part_pages=None, jobs="2", extra=()):
    env = dict(os.environ, SOURCE_DATE_EPOCH=FIXED_EPOCH, TZ="UTC", CODE2PDF_JOBS=jobs)
    env.pop("CODE2PDF_PART_PAGES", None)
    if part_pages:
        env["CODE2PDF_PART_PAGES"] = str(part_pages)
    cmd = [PYTHON, str(SCRIPTS / "dir_to_pdf.py"), str(root), str(output), "[]", "env*",
           '["py", "md", "sh"]', "[]", "true", "", "", "", "", *extra]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    assert result.returncode == 0, result.stderr
    return result


def page_texts(pdf):
    from pypdf import PdfReader
    count = len(PdfReader(str(pdf)).pages)
    return [subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(pdf), "-"],
                           capture_output=True, text=True).stdout for p in range(1, count + 1)]


def test_partition_keeps_order_and_whole_files(parts):
    groups = parts.partition([3, 1, 5, 120, 2, 2], part_pages=6)
    assert [i for g in groups for i in g] == list(range(6))
    assert groups == [[0, 1], [2], [3], [4, 5]]  # a 120-page file is a part on its own


def test_parts_output_matches_single_pass(project, temp_dir):
    single, joined = temp_dir / "single.pdf", temp_dir / "joined.pdf"
    convert(project, single)
    result = convert(project, joined, part_pages=2)
    assert "parts" in result.stderr

    single_pages, joined_pages = page_texts(single), page_texts(joined)
    assert len(joined_pages) == len(single_pages)
    for s, j in zip(single_pages, joined_pages):
        # same body text and same header/footer text on every page
        assert re.sub(r"\s+", " ", s).strip() == re.sub(r"\s+", " ", j).strip()


def test_contents_links_and_bookmarks_point_at_each_file(project, temp_dir):
    from pypdf import PdfReader
    joined = temp_dir / "joined.pdf"
    convert(project, joined, part_pages=2)
    reader = PdfReader(str(joined))
    texts = page_texts(joined)

    outline = {item.title: reader.get_destination_page_number(item) for item in reader.outline}
    assert set(outline) == {"a.py", "b.md", "lib/c.py", "lib/deep/d.sh", "z.py"}
    for rel, page in outline.items():
        assert f"{rel} line" in texts[page] or rel.endswith(".md") or rel == "z.py", rel
        assert rel.rsplit("/", 1)[-1] in texts[page]

    targets = []
    for annot in reader.pages[0].get("/Annots", []):
        annot = annot.get_object()
        assert "/A" not in annot or "/URI" not in annot["/A"], "placeholder link left unresolved"
        targets.append(reader.get_page_number(annot["/Dest"][0].get_object()))
    # WeasyPrint makes one link area per fragment (name, dot leader, number); all must hit a file start
    assert set(targets) == set(outline.values())

    # contents page numbers are the 1-based pages the bookmarks point at
    numbers = [int(n) for n in re.findall(r"\.\s*(\d+)\s*$", texts[0], re.M)]
    assert sorted(numbers) == sorted(p + 1 for p in outline.values())


def test_every_page_has_header_and_footer(project, temp_dir):
    joined = temp_dir / "joined.pdf"
    convert(project, joined, part_pages=2)
    texts = page_texts(joined)
    total = len(texts)
    for number, text in enumerate(texts, 1):
        assert re.search(rf"\b{number}\s*/\s*{total}\b", text), f"footer missing on page {number}"
        if number > 1:
            assert "proj, 2026-01-01" in text, f"header missing on page {number}"


def test_metadata(project, temp_dir):
    from pypdf import PdfReader
    joined = temp_dir / "joined.pdf"
    convert(project, joined, part_pages=2)
    info = PdfReader(str(joined)).metadata
    assert info.title == "proj"
    assert str(info.get("/CreationDate", "")).startswith("D:20260101000000")


def test_small_documents_stay_single_pass(project, temp_dir):
    result = convert(project, temp_dir / "out.pdf")
    assert "parts" not in result.stderr


def test_one_job_also_works(project, temp_dir):
    single, joined = temp_dir / "single.pdf", temp_dir / "joined.pdf"
    convert(project, single)
    convert(project, joined, part_pages=3, jobs="1")
    assert len(page_texts(joined)) == len(page_texts(single))


def test_no_part_files_left_behind(project, temp_dir):
    out_dir = temp_dir / "out"
    out_dir.mkdir()
    convert(project, out_dir / "merged.pdf", part_pages=2)
    assert sorted(p.name for p in out_dir.iterdir()) == ["merged.pdf"]


@pytest.mark.parametrize("ram_gb, cpus, expected", [(4, 8, 1), (8, 8, 2), (15, 8, 2), (16, 8, 3), (64, 8, 3), (24, 2, 2)])
def test_default_jobs_by_memory(parts, monkeypatch, ram_gb, cpus, expected):
    monkeypatch.delenv("CODE2PDF_JOBS", raising=False)
    page = 4096
    monkeypatch.setattr(parts.os, "sysconf", lambda name: page if name == "SC_PAGE_SIZE" else ram_gb * (1 << 30) // page)
    monkeypatch.setattr(parts.os, "cpu_count", lambda: cpus)
    assert parts.default_jobs() == expected


def test_metadata_matches_single_pass_creator(project, temp_dir):
    from pypdf import PdfReader
    convert(project, temp_dir / "joined.pdf", part_pages=2)
    assert PdfReader(str(temp_dir / "joined.pdf")).metadata.get("/Creator") == "code2pdf"
