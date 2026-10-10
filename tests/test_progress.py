"""Progress reporting for long conversions."""

import io
import os
import re
import subprocess
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
REPO_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PYTHON = str(REPO_VENV_PYTHON) if REPO_VENV_PYTHON.exists() else sys.executable


def has_render_deps() -> bool:
    return subprocess.run([PYTHON, "-c", "import pygments, weasyprint"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not has_render_deps(), reason="pygments/weasyprint not available")


@pytest.fixture(scope="module")
def progress():
    sys.path.insert(0, str(SCRIPTS))
    import progress
    return progress


class TtyStream(io.StringIO):
    def isatty(self):
        return True


def test_page_estimate_counts_wrapped_lines(progress):
    short = "x = 1\n" * 590                       # about 10 pages of short lines
    long_lines = ("y" * 200 + "\n") * 295         # 295 lines, each wraps to 3 rows: ~885 rows
    assert 9 <= progress.estimate_pages([short]) <= 12
    assert 14 <= progress.estimate_pages([long_lines]) <= 18
    # every file starts on a new page, plus the contents page
    assert progress.estimate_pages(["a\n", "b\n", "c\n"], contents=True) == 4


def test_terminal_output_updates_one_line(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=3, lines=120, estimated_pages=10)
    for page in range(1, 11):
        p.page(page)
    p.writing()
    p.done(pages=10, output="/tmp/out.pdf")
    out = stream.getvalue()
    assert out.startswith("code2pdf: 3 files, 120 lines (~10 pages)")
    assert "\r" in out and "[2/3] Laying out page 10 of ~10" in out
    assert "[3/3] Writing PDF" in out
    assert re.search(r"Done: 10 pages in \d+:\d\d", out)


def test_estimate_grows_when_exceeded(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=5)
    p.page(7)
    assert "page 7 of ~" in stream.getvalue()
    assert "of ~5" not in stream.getvalue().split("\r")[-1]


def test_log_output_prints_every_ten_percent(progress):
    stream = io.StringIO()  # not a terminal
    p = progress.Progress(stream, files=2, lines=50, estimated_pages=100)
    for page in range(1, 101):
        p.page(page)
    p.done(pages=100, output="out.pdf")
    lines = stream.getvalue().splitlines()
    assert "\r" not in stream.getvalue()
    assert 9 <= sum("Laying out page" in l for l in lines) <= 11


def test_quiet_prints_nothing(progress):
    stream = TtyStream()
    p = progress.Progress(stream, files=2, lines=50, estimated_pages=10, quiet=True)
    p.page(1)
    p.done(pages=1, output="out.pdf")
    assert stream.getvalue() == ""


def test_conversion_reports_progress(temp_dir):
    for i in range(3):
        (temp_dir / f"f{i}.py").write_text("x = 1\n" * 200)
    cmd = [PYTHON, str(SCRIPTS / "dir_to_pdf.py"), str(temp_dir), str(temp_dir / "merged.pdf"),
           "[]", "env*", '["py"]', "[]", "true", "", "", "", ""]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "code2pdf: 3 files, 600 lines" in result.stderr
    assert "Laying out page" in result.stderr
    assert re.search(r"Done: \d+ pages in \d+:\d\d", result.stderr)


def test_silent_stages_keep_ticking_in_a_terminal(progress):
    import time
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=5, tick=0.05)
    p.preparing()
    time.sleep(0.3)
    p.page(1)
    p.writing()
    time.sleep(0.3)
    p.done(pages=5, output="out.pdf")
    out = stream.getvalue()
    assert out.count("[1/3] Preparing") >= 3
    assert out.count("[3/3] Writing PDF") >= 3
    after_done = out.split("Done:")[1]
    time.sleep(0.2)
    assert stream.getvalue().split("Done:")[1] == after_done  # ticker stopped


def test_time_left_includes_writing(progress, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: clock[0])
    stream = TtyStream()
    p = progress.Progress(stream, files=1, lines=10, estimated_pages=100, tick=None)
    p.page(1)
    clock[0] += 10.0  # 10 s for 50 pages: ~10 s more layout, ~10 s of writing (0.5 x 20 s)
    p.page(50)
    assert "~0:20 left" in stream.getvalue().split("\r")[-1]
