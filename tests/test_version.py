"""--version: which code2pdf this is, how it was installed, and the libraries it uses."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from tests.conftest import CODE2PDF  # noqa: E402


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"


@pytest.fixture(scope="module")
def version():
    sys.path.insert(0, str(SCRIPTS))
    import version
    return version


@pytest.mark.parametrize("describe, expected", [
    ("v3.6", "3.6"),
    ("v3.6-3-g1a2b3c4", "3.6+3"),
    ("v3.6-dirty", "3.6, uncommitted changes"),
    ("v3.6-3-g1a2b3c4-dirty", "3.6+3, uncommitted changes"),
    ("1a2b3c4", "unreleased"),
])
def test_describe_to_version(version, describe, expected):
    assert version.from_describe(describe) == expected


def test_version_file_from_github_tarball(version, temp_dir):
    (temp_dir / "VERSION").write_text("v3.6-2-gd656529|d656529|2026-10-10\n")
    assert version.read_version(str(temp_dir)) == ("3.6+2", "d656529", "2026-10-10")


def test_unexpanded_placeholder_falls_back_to_git(version, temp_dir):
    (temp_dir / "VERSION").write_text("$Format:%(describe:tags)|%h|%cs$\n")
    assert version.read_version(str(temp_dir)) == ("unknown", "", "")


def source_has_version_info():
    """A git checkout, or a GitHub tarball whose VERSION git filled in; not a plain file copy."""
    return (PROJECT_ROOT / ".git").is_dir() or "$Format" not in (PROJECT_ROOT / "VERSION").read_text()


@pytest.mark.skipif(not source_has_version_info(), reason="plain copy: neither .git nor a filled-in VERSION")
def test_checkout_uses_git(version):
    v, commit, date = version.read_version(str(PROJECT_ROOT))
    assert v != "unknown" and re.fullmatch(r"[0-9a-f]{7,}", commit) and re.fullmatch(r"\d{4}-\d\d-\d\d", date)


@pytest.mark.parametrize("layout, expected", [
    ("Cellar", "Homebrew"),
    ("usr-share", "Debian package"),
    ("venv", "install.sh"),
    ("conda", "install.sh (conda-forge environment)"),
    ("git", "git checkout"),
    ("tree", "source tree"),
])
def test_install_kind(version, temp_dir, layout, expected):
    base = {"Cellar": temp_dir / "opt/homebrew/Cellar/code2pdf/3.6", "usr-share": Path("/usr/share/code2pdf")}.get(layout, temp_dir / "inst")
    if layout in ("venv", "conda"):
        (base / "venv/bin").mkdir(parents=True)
    if layout == "conda":
        (base / "venv/conda-meta").mkdir(parents=True)
    if layout == "git":
        (base / ".git").mkdir(parents=True)
    if layout == "tree":
        (base / "bin").mkdir(parents=True)
        (base / "scripts").mkdir()
    assert version.install_kind(str(base)) == expected


def test_launchers_print_version(temp_dir):
    for cmd in ("code2pdf", "code2txt"):
        result = subprocess.run([str(PROJECT_ROOT / "bin" / cmd), "--version"], capture_output=True, text=True,
                                timeout=60, cwd=temp_dir)
        assert result.returncode == 0, result.stderr
        first = result.stdout.splitlines()[0]
        if source_has_version_info():
            assert re.match(rf"{cmd} \S+.* \(commit [0-9a-f]{{7,}}, \d{{4}}-\d\d-\d\d\)$", first), first
        else:
            assert first == f"{cmd} unknown", first
        kind = "git checkout" if (PROJECT_ROOT / ".git").is_dir() else "source tree"  # CI may check out a tarball
        assert f"installed: {kind}" in result.stdout
    pdf = subprocess.run([CODE2PDF, "-V"], capture_output=True, text=True, timeout=60).stdout
    assert re.search(r"python \d+\.\d+.*weasyprint", pdf)
    assert "CJK font:" in pdf


def test_version_works_without_pdf_dependencies(temp_dir):
    """--version must help debug a broken install, so it can't require WeasyPrint."""
    # A python3 that can't see site/dist-packages, i.e. has no WeasyPrint even where it is installed system-wide
    shim = temp_dir / "shim"
    shim.mkdir()
    (shim / "python3").write_text('#!/bin/sh\nexec /usr/bin/python3 -S "$@"\n')
    (shim / "python3").chmod(0o755)
    env = {"HOME": os.environ["HOME"], "PATH": f"{shim}:/usr/bin:/bin"}
    link = temp_dir / "code2pdf"
    link.symlink_to(PROJECT_ROOT / "bin" / "code2pdf")
    fake_home = temp_dir / "home"
    shutil.copytree(PROJECT_ROOT / "scripts", fake_home / "scripts")
    (fake_home / "VERSION").write_text("v3.6|abc1234|2026-10-11\n")
    env["CODE2PDF_HOME"] = str(fake_home)
    result = subprocess.run([str(link), "--version"], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("code2pdf 3.6 (commit abc1234, 2026-10-11)")
    assert "weasyprint not installed" in result.stdout
