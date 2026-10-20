#!/usr/bin/env python3
"""
Version report for `code2pdf --version` / `code2txt --version`.

The version comes from the VERSION file next to scripts/:
  - in GitHub tarballs (Homebrew, install.sh) git's export-subst fills it in, e.g.
    "v3.6-2-gd656529|d656529|2026-10-10" (describe | commit | commit date)
  - build-deb.sh writes it for the .deb
  - in a git checkout it still holds the $Format placeholder, so `git describe` is used

Only the standard library is used, so this works even when WeasyPrint is broken or missing.

Usage: version.py NAME [--no-deps]
"""

import os
import re
import subprocess
import sys

# The Windows build (packaging/windows) unpacks VERSION next to its modules
INSTALL_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def from_describe(describe):
    """`git describe --tags [--dirty]` output -> human version: v3.6 -> 3.6, v3.6-3-gabc -> 3.6+3."""
    dirty = describe.endswith("-dirty")
    if dirty:
        describe = describe[: -len("-dirty")]
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*[\w.]*?)(?:-(\d+)-g[0-9a-f]+)?", describe)
    if not match or re.fullmatch(r"[0-9a-f]{7,40}", describe):  # a bare commit hash: no release tag yet
        text = "unreleased"
    else:
        text = match.group(1) + (f"+{match.group(2)}" if match.group(2) and match.group(2) != "0" else "")
    return text + (", uncommitted changes" if dirty else "")


def _git(directory, *args):
    try:
        result = subprocess.run(["git", "-C", directory, *args], capture_output=True, encoding="utf-8",
                                errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def read_version(install_dir=INSTALL_DIR):
    """(version, commit, date); version is "unknown" if neither VERSION nor git can tell."""
    try:
        with open(os.path.join(install_dir, "VERSION"), encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        text = ""
    if text and "$Format" not in text and text.count("|") == 2:
        describe, commit, date = text.split("|")
        return from_describe(describe), commit, date
    if os.path.isdir(os.path.join(install_dir, ".git")):
        describe = _git(install_dir, "describe", "--tags", "--dirty", "--always")
        commit = _git(install_dir, "rev-parse", "--short", "HEAD")
        date = _git(install_dir, "log", "-1", "--format=%cs")
        if commit:
            return from_describe(describe), commit, date
    return "unknown", "", ""


def install_kind(install_dir=INSTALL_DIR):
    if getattr(sys, "frozen", False):
        return "Windows build"
    path = os.path.realpath(install_dir) if os.path.exists(install_dir) else install_dir
    if "/Cellar/code2pdf/" in path + "/":
        return "Homebrew"
    if path.rstrip("/") in ("/usr/share/code2pdf", "/usr/local/share/code2pdf") and \
            not os.path.isdir(os.path.join(path, "venv")):
        return "Debian package"
    if os.path.isdir(os.path.join(path, "venv", "conda-meta")):
        return "install.sh (conda-forge environment)"
    if os.path.isdir(os.path.join(path, "venv")):
        return "install.sh"
    if os.path.isdir(os.path.join(path, ".git")):
        return "git checkout"
    if os.path.isdir(os.path.join(path, "bin")) and os.path.isdir(os.path.join(path, "scripts")):
        return "source tree"  # e.g. an unpacked GitHub tarball, run in place
    return "unknown"


def _module_version(name):
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:  # Python < 3.8
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        pass
    try:  # some distro packages ship without metadata
        module = __import__(name)
        return getattr(module, "__version__", "installed")
    except Exception:
        return None


def dependencies_line():
    parts = [f"python {sys.version.split()[0]}"]
    for name in ("weasyprint", "pygments", "pypdf"):
        found = _module_version(name)
        parts.append(f"{name} {found}" if found else f"{name} not installed")
    return ", ".join(parts)


def fc_list_command():
    """fontconfig's fc-list: on PATH, or next to the modules in the Windows build."""
    import shutil
    found = shutil.which("fc-list")
    if not found and getattr(sys, "frozen", False):
        bundled = os.path.join(INSTALL_DIR, "fc-list.exe")
        found = bundled if os.path.isfile(bundled) else None
    return found


def cjk_font_line():
    fc_list = fc_list_command()
    if not fc_list:
        return "unknown (fc-list not found)"
    try:
        out = subprocess.run([fc_list, ":charset=4e2d", "family"], capture_output=True, encoding="utf-8",
                             errors="replace", timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    families = sorted({name.strip() for line in out.splitlines() for name in line.split(",")
                       if name.strip() and not name.strip().startswith(".")})  # "." = hidden system fonts
    if not families:
        return ("none (Chinese/Japanese/Korean would print as empty boxes; "
                + ("add the language in Windows' settings)" if sys.platform == "win32" else "see setup_cjk_fonts.sh)"))
    # Same preference as the code font fallback in theme.py (CJK_MONO_FALLBACK)
    for wanted in ("Noto Sans Mono CJK SC", "Noto Sans Mono CJK TC", "Noto Sans Mono CJK JP",
                   "Noto Sans Mono CJK KR", "Noto Sans Mono CJK", "PingFang SC", "Hiragino Sans", "Noto Sans CJK",
                   "Microsoft YaHei", "Yu Gothic", "Malgun Gothic"):
        for family in families:
            if family.startswith(wanted):
                return family
    return families[0]


def report(name, with_deps=True, install_dir=INSTALL_DIR):
    version, commit, date = read_version(install_dir)
    first = f"{name} {version}"
    if commit:
        first += f" (commit {commit}{', ' + date if date else ''})"
    lines = [first, f"  installed: {install_kind(install_dir)}, {os.path.realpath(install_dir)}"]
    if with_deps:
        lines.append("  " + dependencies_line())
        lines.append("  CJK font: " + cjk_font_line())
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    print(report(args[0] if args else "code2pdf", with_deps="--no-deps" not in args))
