"""Warn when Chinese/Japanese/Korean text would print as empty boxes (no font has the characters)."""

import os
import subprocess
import sys
from pathlib import Path
import pytest
from tests.conftest import CODE2PDF  # noqa: E402


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(SCRIPTS))
    import dir_to_pdf
    return dir_to_pdf


def fake_fc_list(folder, covered=(), log=None):
    """An fc-list that reports a font only for the ':charset=<hex>' queries in COVERED."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "fc-list"
    record = f'echo "$1" >> "{log}"\n' if log else ""
    cases = "".join(f'  *charset={c}*) echo "Some CJK Font";;\n' for c in covered)
    script.write_text(f'#!/bin/sh\n{record}case "$1" in\n{cases}esac\n')
    script.chmod(0o755)
    return str(script)


def test_reports_scripts_without_fonts(mod, temp_dir):
    fc = fake_fc_list(temp_dir / "bin")
    assert mod.missing_cjk_fonts(["x = '中文'", "# かな", "# 한국어"], fc_list=fc) == ["Chinese", "Japanese", "Korean"]


def test_nothing_missing_when_fonts_cover_the_text(mod, temp_dir):
    fc = fake_fc_list(temp_dir / "bin", covered=("4e2d", "3042", "d55c"))
    assert mod.missing_cjk_fonts(["中文 かな 한국어"], fc_list=fc) == []


def test_only_scripts_that_appear_are_checked(mod, temp_dir):
    log = temp_dir / "calls.log"
    fc = fake_fc_list(temp_dir / "bin", covered=("4e2d",), log=log)
    assert mod.missing_cjk_fonts(["只有中文"], fc_list=fc) == []
    assert log.read_text().split() == [":charset=4e2d"]


def test_no_cjk_text_means_no_fontconfig_query(mod, temp_dir):
    log = temp_dir / "calls.log"
    fc = fake_fc_list(temp_dir / "bin", log=log)
    assert mod.missing_cjk_fonts(["print('hello')", "Ünïcödé but not CJK"], fc_list=fc) == []
    assert not log.exists()


def test_without_fc_list_nothing_is_reported(mod):
    assert mod.missing_cjk_fonts(["中文"], fc_list=None) == []


@pytest.mark.skipif(subprocess.run([PYTHON, "-c", "import weasyprint"], capture_output=True).returncode != 0,
                    reason="weasyprint not available")
def test_conversion_warns_with_a_fix(temp_dir):
    project = temp_dir / "proj"
    project.mkdir()
    (project / "a.py").write_text("# 你好\nprint('hi')\n")
    bin_dir = temp_dir / "bin"
    fake_fc_list(bin_dir)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    cmd = [PYTHON, str(SCRIPTS / "dir_to_pdf.py"), str(project), str(project / "merged.pdf"),
           "[]", "env*", '["py"]', "[]", "true", "", "", "", ""]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    assert result.returncode == 0, result.stderr
    assert "Chinese" in result.stderr and "empty boxes" in result.stderr
    assert "setup_cjk_fonts.sh" in result.stderr
    assert (project / "merged.pdf").exists()
    # repeated after "Done:", where it can't scroll away behind the progress lines
    after_done = result.stderr.split("Done:", 1)[1]
    assert "empty boxes" in after_done and "setup_cjk_fonts.sh" in after_done


# Apple's CJK fonts (PingFang, Hiragino) carry an Apple-only 'cidg' table. Left in an embedded
# subset, Preview follows it and prints most characters empty or as other characters.

def embedded_font_tables(pdf):
    """The OpenType table tags of each font program embedded in PDF."""
    import io
    from fontTools.ttLib import TTFont
    from pypdf import PdfReader
    found = {}
    for page in PdfReader(pdf).pages:
        for ref in page["/Resources"]["/Font"].values():
            for descendant in ref.get_object().get("/DescendantFonts", []):
                descriptor = descendant.get_object()["/FontDescriptor"].get_object()
                for key in ("/FontFile2", "/FontFile3"):
                    if key in descriptor:
                        stream = descriptor[key].get_object()
                        found[id(stream)] = set(TTFont(io.BytesIO(stream.get_data())).keys())
    return list(found.values())


def test_finisher_drops_cidg_and_keeps_the_font_usable():
    import io
    import pydyf
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables.DefaultTable import DefaultTable
    sys.path.insert(0, str(SCRIPTS))
    import theme
    font = TTFont(theme.font_files()[0])
    font["cidg"] = DefaultTable("cidg")
    font["cidg"].data = b"\0" * 64
    data = io.BytesIO()
    font.save(data)
    pdf = pydyf.PDF()
    font_stream = pydyf.Stream([data.getvalue()], pydyf.Dictionary({"Length1": len(data.getvalue())}))
    other = pydyf.Stream([b"BT /F1 9 Tf ET"])
    pdf.add_object(font_stream)
    pdf.add_object(other)
    theme.drop_apple_cid_tables(None, pdf)
    kept = font_stream.stream[0]
    assert "cidg" not in TTFont(io.BytesIO(kept)) and "glyf" in TTFont(io.BytesIO(kept))
    assert font_stream.extra["Length1"] == len(kept) < len(data.getvalue())
    assert other.stream == [b"BT /F1 9 Tf ET"]


@pytest.mark.skipif(not subprocess.run(["sh", "-c", "fc-list :charset=4e2d | grep -q ."]).returncode == 0,
                    reason="no font with Chinese characters")
@pytest.mark.parametrize("part_pages", [None, "1"], ids=["one pass", "parts"])
def test_printed_cjk_fonts_have_no_cidg(temp_dir, part_pages):
    source = temp_dir / "note.md"
    source.write_text("# 温馨提示：没有干货，全是吐槽\n\n" + "在药企做AI转型艰难又痛苦，总结了四宗罪。\n" * 150)
    env = {**os.environ, **({"CODE2PDF_PART_PAGES": part_pages} if part_pages else {})}
    if part_pages:
        env.pop("CODE2PDF_JOBS", None)
        result = subprocess.run([CODE2PDF, "-a", str(temp_dir), "-o", str(temp_dir / "out.pdf")],
                                capture_output=True, text=True, env=env)
        assert "parts" in result.stderr
    else:
        result = subprocess.run([CODE2PDF, "-s", str(source), "-o", str(temp_dir / "out.pdf")],
                                capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    tables = embedded_font_tables(temp_dir / "out.pdf")
    assert tables and all("cidg" not in t for t in tables)
