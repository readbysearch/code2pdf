"""Regression tests: print_all.sh must not touch other files in /tmp."""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
import pytest
from tests.conftest import run_command


BREW_VENV_BIN = Path("/opt/homebrew/opt/code2pdf/libexec/bin")


def python_env() -> dict:
    """Environment whose python3 can import pygments and weasyprint."""
    env = os.environ.copy()
    if BREW_VENV_BIN.exists():
        env["PATH"] = f"{BREW_VENV_BIN}:{env['PATH']}"
    return env


def has_pdf_deps() -> bool:
    if not shutil.which("gs") or not shutil.which("jq"):
        return False
    result = subprocess.run(
        ["python3", "-c", "import pygments, weasyprint"],
        env=python_env(), capture_output=True
    )
    return result.returncode == 0


def page_count(pdf: Path) -> int:
    result = subprocess.run(
        ["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c",
         f"({pdf}) (r) file runpdfbegin pdfpagecount = quit"],
        capture_output=True, text=True, check=True
    )
    return int(result.stdout.strip())


def run_print_all(project_root: Path, target: Path):
    script = project_root / "scripts" / "print_all.sh"
    cmd = [
        "bash", str(script), str(target), str(project_root / "config" / "vimrc"),
        '["node_modules", ".git", "dist", "out"]', "env*",
        '["py", "md"]', '["README"]', "true", "", "", "", "",
    ]
    proc = subprocess.run(cmd, env=python_env(), capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


@pytest.mark.skipif(not has_pdf_deps(), reason="gs, jq, pygments or weasyprint not available")
class TestPrintAllTmpIsolation:
    """print_all.sh used to `rm /tmp/*.pdf` and merge every PDF in /tmp."""

    @pytest.fixture
    def sentinels(self):
        tag = uuid.uuid4().hex
        pdf = Path(f"/tmp/code2pdf_sentinel_{tag}.pdf")
        ps = Path(f"/tmp/code2pdf_sentinel_{tag}.ps")
        subprocess.run(["gs", "-q", "-sDEVICE=pdfwrite", "-o", str(pdf), "-c", "showpage"], check=True)
        ps.write_text("%!PS\nshowpage\n")
        yield pdf, ps
        pdf.unlink(missing_ok=True)
        ps.unlink(missing_ok=True)

    @pytest.fixture
    def project(self, temp_dir):
        (temp_dir / "a.py").write_text("print('a')\n")
        (temp_dir / "b.md").write_text("# b\n")
        return temp_dir

    def test_unrelated_tmp_files_survive(self, project_root, project, sentinels):
        pdf, ps = sentinels
        returncode, _, stderr = run_print_all(project_root, project)
        assert returncode == 0, stderr
        assert pdf.exists(), "print_all.sh deleted an unrelated PDF in /tmp"
        assert ps.exists(), "print_all.sh deleted an unrelated PS file in /tmp"

    def test_merged_pdf_excludes_unrelated_tmp_pdfs(self, project_root, project, sentinels):
        returncode, _, stderr = run_print_all(project_root, project)
        assert returncode == 0, stderr
        # table of contents + a.py + b.md, one page each; the sentinel must not be merged in
        assert page_count(project / "merged.pdf") == 3

    def test_no_work_files_left_behind(self, project_root, project):
        before = set(Path("/tmp").iterdir())
        returncode, _, stderr = run_print_all(project_root, project)
        assert returncode == 0, stderr
        leftovers = [p for p in set(Path("/tmp").iterdir()) - before
                     if p.name.startswith("code2pdf") or p.suffix == ".pdf" or p.name == "table_of_contents"]
        assert leftovers == []
