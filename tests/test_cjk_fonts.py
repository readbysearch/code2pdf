"""Warn when Chinese/Japanese/Korean text would print as empty boxes (no font has the characters)."""

import os
import subprocess
import sys
from pathlib import Path
import pytest


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
