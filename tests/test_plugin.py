"""The Claude Code plugin (plugins/code2pdf) and the marketplace that lists it.

The skill restates a few options; this keeps them from drifting away from `--help`.
"""

import json
import re
import subprocess
from pathlib import Path
from tests.conftest import posix_only  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
PLUGIN = PROJECT_ROOT / "plugins" / "code2pdf"
SKILL = PLUGIN / "skills" / "code2pdf" / "SKILL.md"


def help_text(tool):
    result = subprocess.run([str(PROJECT_ROOT / "bin" / tool), "--help"], capture_output=True, text=True)
    return result.stdout + result.stderr


def test_manifests():
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((PROJECT_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["name"] == "code2pdf" and re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    [entry] = market["plugins"]
    assert entry["name"] == plugin["name"]
    assert (PROJECT_ROOT / entry["source"]).resolve() == PLUGIN.resolve()


def test_skill_frontmatter():
    text = SKILL.read_text()
    front = text.split("---\n")[1]
    fields = dict(line.split(": ", 1) for line in front.strip().split("\n"))
    assert fields["name"] == "code2pdf"
    assert 200 < len(fields["description"]) < 1024


@posix_only  # runs code2txt or the bash launchers
def test_every_option_in_the_skill_exists():
    """The skill says "read --help" for the rest, but the options it does name must be real:
    those in code2pdf/code2txt commands, and those written alone in backticks."""
    text = SKILL.read_text()
    known = {"code2pdf": help_text("code2pdf"), "code2txt": help_text("code2txt")}
    named = []
    for tool, args in re.findall(r"\b(code2pdf|code2txt)\b([^`|&;\n]*)", text):
        named += [(tool, option) for option in re.findall(r"(?<![\w-])(--?[a-zA-Z][\w-]*)", args)]
    for option in re.findall(r"`(--?[a-z][\w-]*)`", text):
        named.append(("either", option))
    assert len(named) > 8, named

    def documented(option, text):
        return re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", text)

    missing = [(tool, option) for tool, option in named
               if not documented(option, known["code2pdf"] + known["code2txt"] if tool == "either" else known[tool])]
    assert not missing, missing
