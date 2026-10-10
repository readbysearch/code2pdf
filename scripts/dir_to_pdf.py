#!/usr/bin/env python3
"""
Convert a directory of source files into one PDF: a table of contents followed by
every file, rendered in a single WeasyPrint pass.

Usage (positional arguments match print_all.sh):
  dir_to_pdf.py ROOT OUTPUT BLACKLIST_JSON BLACKLIST_PATTERN EXTENSIONS_JSON NAMES_JSON
                INCLUDE_NO_EXTENSION IGNORE_FILES IGNORE_TYPES IGNORE_FOLDERS INCLUDE_TYPES
                [--list-files] [--theme NAME]
  dir_to_pdf.py --list-themes

  --list-files   Print the selected files (relative to ROOT) instead of rendering.
  --theme NAME   paper (default), mono, or any Pygments style; default from $CODE2PDF_THEME.
  --list-themes  Print every theme name.

Dates: the contents page says when the PDF was printed ($SOURCE_DATE_EPOCH overrides "now")
and, in a git repository, which commit; each file shows its last commit date, "uncommitted
changes", or outside git its modification date.
"""

import argparse
import datetime
import fnmatch
import html
import json
import os
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path


def split_list(value):
    return [item for item in value.split(",") if item] if value else []


def split_extension(name):
    """'a.tar.gz' -> 'gz'; names without a dot have no extension (same as print_all.sh)."""
    return name.rsplit(".", 1)[1] if "." in name else ""


class Selector:
    """File selection rules, kept identical to the previous bash implementation."""

    def __init__(self, args):
        self.blacklist = set(json.loads(args.blacklist_json or "[]"))
        self.pattern = args.blacklist_pattern
        self.extensions = set(json.loads(args.extensions_json or "[]"))
        self.names = set(json.loads(args.names_json or "[]"))
        self.include_no_extension = args.include_no_extension == "true"
        self.ignore_files = set(split_list(args.ignore_files))
        self.ignore_types = set(split_list(args.ignore_types))
        self.ignore_folders = set(split_list(args.ignore_folders))
        self.include_types = set(split_list(args.include_types))

    def skip_folder(self, name):
        return (name in self.blacklist or name in self.ignore_folders
                or (self.pattern and fnmatch.fnmatchcase(name, self.pattern)))

    def wants_file(self, name):
        extension = split_extension(name)
        if name in self.ignore_files:
            return False
        if self.include_types:
            return extension in self.include_types
        if extension and extension in self.ignore_types:
            return False
        if not extension and self.include_no_extension:
            return True
        return extension in self.extensions or name in self.names


def collect_files(root, selector, exclude):
    """Depth-first walk, entries sorted by name; hidden entries skipped; symlink loops cut."""
    visited = {os.path.realpath(root)}
    selected = []

    def walk(folder):
        try:
            entries = sorted(os.listdir(folder))
        except OSError as e:
            print(f"Warning: cannot read {folder}: {e}", file=sys.stderr)
            return
        for name in entries:
            if name.startswith("."):
                continue
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                real = os.path.realpath(path)
                if real in visited or selector.skip_folder(name):
                    continue
                visited.add(real)
                walk(path)
            elif os.path.isfile(path):
                if os.path.realpath(path) in exclude or not selector.wants_file(name):
                    continue
                selected.append(os.path.relpath(path, root))

    walk(root)
    return selected


class SourceInfo:
    def __init__(self, summary, files):
        self.summary = summary  # e.g. "from commit 7afaa74 (main)"; "" outside git
        self.files = files      # rel path -> "last changed 2026-10-08" / "uncommitted changes" / "modified ..."


def _git(root, *args):
    result = subprocess.run(["git", "-C", root, "-c", "core.quotePath=false", *args],
                            capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def _modified(path):
    return "modified " + datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def source_info(root, files):
    """Per-file dates and a one-line source summary, from git when ROOT is inside a repository."""
    fallback = {rel: _modified(os.path.join(root, rel)) for rel in files}
    try:
        toplevel = _git(root, "rev-parse", "--show-toplevel")
    except OSError:  # git not installed
        return SourceInfo("", fallback)
    if not toplevel:
        return SourceInfo("", fallback)

    # Uncommitted: modified, staged or untracked (status paths are relative to the repository root)
    prefix = os.path.relpath(os.path.realpath(root), os.path.realpath(toplevel.strip()))
    prefix = "" if prefix == "." else prefix + "/"
    dirty = set()
    entries = (_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".") or "").split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) > 3:
            path = entry[3:]
            if path.startswith(prefix):
                dirty.add(path[len(prefix):])
            if entry[0] in "RC":  # renames/copies are followed by the old path
                i += 1
        i += 1

    # Last commit date per file: newest first, stop once every file is found
    wanted = set(files) - dirty
    changed = {}
    head = _git(root, "rev-parse", "--short", "HEAD")
    if head and wanted:
        proc = subprocess.Popen(["git", "-C", root, "-c", "core.quotePath=false", "log", "--relative",
                                 "--no-renames", "--format=@@%cs", "--name-only", "--", "."],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        date = None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.startswith("@@"):
                date = line[2:]
            elif line in wanted and line not in changed:
                changed[line] = date
                if len(changed) == len(wanted):
                    break
        proc.kill()
        proc.wait()

    labels = {}
    for rel in files:
        if rel in dirty:
            labels[rel] = "uncommitted changes"
        elif rel in changed:
            labels[rel] = "last changed " + changed[rel]
        else:
            labels[rel] = fallback[rel]

    summary = ""
    if head:
        branch = (_git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
        summary = f"from commit {head.strip()}" + (f" ({branch})" if branch and branch != "HEAD" else "")
        if dirty & set(files):
            summary += " with uncommitted changes"
    return SourceInfo(summary, labels)


def printed_at():
    """Now (local time), or $SOURCE_DATE_EPOCH (UTC) for reproducible output."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.datetime.fromtimestamp(int(epoch), tz=datetime.timezone.utc)
    return datetime.datetime.now().astimezone()


def count_lines(source):
    return source.count("\n") + (1 if source and not source.endswith("\n") else 0)


def build_html(entries, theme, project, printed_moment, info, contents=True):
    """entries: [(display path, absolute path)]; info: SourceInfo keyed by display path."""
    printed = printed_moment.date().isoformat()
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from code_to_pdf import lexer_for, read_source
    import theme as themes

    formatter = HtmlFormatter(style=theme.style, linespans="L", cssclass="highlight")
    groups = OrderedDict()
    sections = []
    total_lines = 0
    for i, (rel, path) in enumerate(entries):
        source = read_source(path)
        lexer = lexer_for(rel, source)
        lines = count_lines(source)
        total_lines += lines
        folder, name = os.path.split(rel)
        groups.setdefault(folder, []).append(f'<li><a href="#f{i}">{html.escape(name)}</a></li>')
        code = highlight(source, lexer, formatter).replace('id="L-', f'id="f{i}-L-')
        folder_html = f'<div class="dir">{html.escape(folder)}/</div>' if folder else ""
        language = "Plain text" if lexer.name == "Text only" else lexer.name
        details = f"{language}, {lines:,} line{'s' if lines != 1 else ''}"
        if info.files.get(rel):
            details += f", {info.files[rel]}"
        sections.append(
            f'<section class="file"><header>{folder_html}'
            f'<h1 id="f{i}" data-path="{html.escape(rel)}">{html.escape(name)}</h1>'
            f'<div class="meta">{html.escape(details)}</div></header>{code}</section>')

    title = project or (entries[0][0] if entries else "code2pdf")
    nav = ""
    if contents:
        toc = "".join(
            f'<h2>{html.escape((folder or project) + "/")}</h2><ol>{"".join(items)}</ol>'
            for folder, items in groups.items())
        printed_line = f"Printed {printed}" + (f" {info.summary}" if info.summary else "")
        nav = (f'<nav class="toc"><h1>{html.escape(project)}</h1>'
               f'<p class="summary">{len(entries):,} file{"s" if len(entries) != 1 else ""}, '
               f'{total_lines:,} line{"s" if total_lines != 1 else ""}</p>'
               f'<p class="summary">{html.escape(printed_line)}</p>{toc}</nav>')

    header_right = f"{project}, {printed}" if project else printed
    style_defs = formatter.get_style_defs(".highlight")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<meta name="generator" content="code2pdf">
<meta name="dcterms.created" content="{printed_moment.isoformat(timespec='seconds')}">
<style>{themes.font_face_css()}{style_defs}{themes.page_css(theme, header_right)}</style>
</head>
<body>
{nav}{''.join(sections)}
</body>
</html>
"""


def render_document(entries, output, theme_name="paper", project=None, contents=True, root=None):
    """Render [(display path, absolute path)] into OUTPUT. Raises ValueError for an unknown theme."""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    import theme as themes

    theme = themes.resolve_theme(theme_name)
    if root is None:  # single file: dates come from its own folder
        rel, path = entries[0]
        single = source_info(os.path.dirname(path), [os.path.basename(path)])
        info = SourceInfo(single.summary, {rel: single.files[os.path.basename(path)]})
    else:
        info = source_info(root, [rel for rel, _ in entries])

    document = build_html(entries, theme, project, printed_at(), info, contents=contents)
    out_dir = os.path.dirname(os.path.abspath(output))
    fd, tmp = tempfile.mkstemp(prefix=".code2pdf-", suffix=".pdf", dir=out_dir)
    os.close(fd)
    try:
        HTML(string=document, base_url=root or out_dir).write_pdf(tmp, font_config=FontConfiguration())
        os.replace(tmp, output)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Convert a directory of source files into one PDF.")
    for name in ("root", "output", "blacklist_json", "blacklist_pattern", "extensions_json",
                 "names_json", "include_no_extension", "ignore_files", "ignore_types",
                 "ignore_folders", "include_types"):
        parser.add_argument(name, nargs="?", default="")
    parser.add_argument("--list-files", action="store_true")
    parser.add_argument("--list-themes", action="store_true")
    parser.add_argument("--theme", default=os.environ.get("CODE2PDF_THEME", "paper"))
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_themes:
        import theme as themes
        print("\n".join(themes.list_themes()))
        return 0

    root = os.path.abspath(args.root or ".")
    if not os.path.isdir(root):
        print(f"Error: directory not found: {args.root}", file=sys.stderr)
        return 1
    output = os.path.abspath(args.output or os.path.join(root, "merged.pdf"))

    files = collect_files(root, Selector(args), exclude={os.path.realpath(output)})
    if args.list_files:
        print("\n".join(files))
        return 0
    if not files:
        print(f"Error: no matching files in {root}", file=sys.stderr)
        return 1

    print(f"Rendering {len(files)} files from {root}", file=sys.stderr)
    entries = [(rel, os.path.join(root, rel)) for rel in files]
    try:
        render_document(entries, output, theme_name=args.theme, project=os.path.basename(root),
                        contents=True, root=root)
    except ValueError as e:
        print(f"Error: {e}; run `code2pdf --list-themes` to see the names", file=sys.stderr)
        return 1
    print(f"Success: PDF created at {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
