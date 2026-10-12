"""install.sh pieces that can be tested without a full install: PATH setup and release selection."""

import os
import subprocess
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
INSTALL_SH = PROJECT_ROOT / "install.sh"

UBUNTU_PROFILE = '''# ~/.profile: executed by the command interpreter for login shells.
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
'''


def run_function(snippet, home, path_extra="", env_extra=None):
    """Source install.sh without running the installer, then run SNIPPET."""
    env = {"HOME": str(home), "PATH": f"{path_extra}/usr/bin:/bin", "CODE2PDF_INSTALL_SOURCED": "1",
           "TERM": "dumb", **(env_extra or {})}
    script = f'source "{INSTALL_SH}"\nINSTALL_DIR="$HOME/.local/bin"\nINSTALL_DIR_USER="$HOME/.local/bin"\n{snippet}\n'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, timeout=60)


@pytest.fixture
def home(temp_dir):
    h = temp_dir / "home"
    (h / ".local" / "bin").mkdir(parents=True)
    return h


def test_sourcing_does_not_run_the_installer(home):
    result = run_function("echo sourced-ok", home)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("sourced-ok")
    assert "Installer" not in result.stdout


def test_stock_ubuntu_profile_is_left_alone(home):
    """Ubuntu's ~/.profile already adds ~/.local/bin; a non-interactive install (ssh, CI) must not
    append another PATH line just because its own PATH lacks it."""
    (home / ".profile").write_text(UBUNTU_PROFILE)
    (home / ".bashrc").write_text("# bashrc\n")
    result = run_function("configure_path", home)
    assert result.returncode == 0, result.stderr
    assert (home / ".profile").read_text() == UBUNTU_PROFILE
    assert (home / ".bashrc").read_text() == "# bashrc\n"
    assert ".profile" in result.stdout


def test_path_line_added_when_nothing_provides_it(home):
    (home / ".bashrc").write_text("# bashrc\n")
    (home / ".profile").write_text("# nothing about local bin\n")
    result = run_function("configure_path", home)
    assert result.returncode == 0, result.stderr
    assert "Added by code2pdf installer" in (home / ".bashrc").read_text()
    # a second run must not add it again
    run_function("configure_path", home)
    assert (home / ".bashrc").read_text().count("Added by code2pdf installer") == 1


def test_nothing_to_do_when_already_on_path(home):
    (home / ".bashrc").write_text("# bashrc\n")
    result = run_function("configure_path", home, path_extra=f"{home}/.local/bin:")
    assert result.returncode == 0, result.stderr
    assert (home / ".bashrc").read_text() == "# bashrc\n"


def fake_curl(folder, location=None, api_json=None):
    """A curl that answers the releases/latest redirect (-I) and the API, or fails."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "curl"
    head = f'printf "HTTP/2 302\\r\\nlocation: {location}\\r\\n\\r\\n"; exit 0' if location else "exit 22"
    api = f"printf '%s' '{api_json}'; exit 0" if api_json else "exit 22"
    script.write_text(f'''#!/bin/sh
case "$*" in
  *api.github.com*) {api};;
  *-I*|*--head*) {head};;
  *) exit 22;;
esac
''')
    script.chmod(0o755)
    return f"{folder}:"


def test_latest_release_from_redirect(home, temp_dir):
    path = fake_curl(temp_dir / "bin", location="https://github.com/readbysearch/code2pdf/releases/tag/v3.7.2")
    result = run_function("latest_release_tag", home, path_extra=path)
    assert result.stdout.strip() == "v3.7.2", result.stderr


def test_latest_release_from_api_when_redirect_fails(home, temp_dir):
    path = fake_curl(temp_dir / "bin", api_json='{"tag_name": "v3.8", "name": "v3.8"}')
    result = run_function("latest_release_tag", home, path_extra=path)
    assert result.stdout.strip() == "v3.8", result.stderr


def test_no_release_found_returns_nothing(home, temp_dir):
    path = fake_curl(temp_dir / "bin")
    result = run_function("latest_release_tag || echo none", home, path_extra=path)
    assert result.stdout.strip() == "none"


def test_default_ref_is_latest_release_and_main_is_opt_in(home, temp_dir):
    path = fake_curl(temp_dir / "bin", location="https://github.com/readbysearch/code2pdf/releases/tag/v3.7.2")
    default = run_function('REF=""; choose_ref; echo "ref=$REF"', home, path_extra=path)
    assert "ref=v3.7.2" in default.stdout, default.stdout + default.stderr
    assert "--ref main" in default.stdout
    explicit = run_function('REF="main"; choose_ref; echo "ref=$REF"', home, path_extra=path)
    assert "ref=main" in explicit.stdout


def test_falls_back_to_main_with_a_warning(home, temp_dir):
    path = fake_curl(temp_dir / "bin")
    result = run_function('REF=""; choose_ref; echo "ref=$REF"', home, path_extra=path)
    assert "ref=main" in result.stdout
    assert "WARNING" in result.stdout


def test_python_env_errors_go_to_a_file_the_user_can_write(home, temp_dir):
    """In a system install $SHARE_DIR belongs to root. The setup's errors used to be redirected there
    by the user's own shell, which failed before the setup ran: a broken install."""
    share = temp_dir / "share"
    share.mkdir()
    share.chmod(0o555)
    log = temp_dir / "errors.log"
    snippet = f'''
SHARE_DIR="{share}"; SUDO=""; USE_CONDA=false
create_system_env() {{ touch "{temp_dir}/system-env-ran"; echo "pip failed" >&2; return 1; }}
create_conda_env() {{ echo "conda failed" >&2; return 1; }}
setup_python_env "$SHARE_DIR/venv" "{log}" || echo "status $?"  # install.sh runs with set -e
'''
    try:
        result = run_function(snippet, home)
    finally:
        share.chmod(0o755)
    assert (temp_dir / "system-env-ran").exists(), result.stderr
    assert "status 1" in result.stdout
    assert "pip failed" in log.read_text() and "conda failed" in log.read_text()
