#!/usr/bin/env python3
"""
Convert a directory of source files into one PDF: a table of contents followed by
every file, rendered in a single WeasyPrint pass.

Usage (positional arguments match print_all.sh):
  dir_to_pdf.py ROOT OUTPUT BLACKLIST_JSON BLACKLIST_PATTERN EXTENSIONS_JSON NAMES_JSON
                INCLUDE_NO_EXTENSION IGNORE_FILES IGNORE_TYPES IGNORE_FOLDERS INCLUDE_TYPES
                [--list-files]

  --list-files  Print the selected files (relative to ROOT) instead of rendering.
"""

import argparse
import fnmatch
import html
import json
import os
import sys
import tempfile
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


PAGE_CSS = """
@page {
    size: A4;
    margin: 2cm;
    @top-center {
        content: string(file);
        font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
        font-size: 10pt;
        color: #666;
    }
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
        font-size: 10pt;
        color: #666;
    }
}
body {
    font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono", "DejaVu Sans Mono", "Courier New", monospace;
    font-size: 9pt;
    line-height: 1.4;
    margin: 0;
}
nav.toc h1 {
    font-family: "Noto Sans SC", "DejaVu Sans", sans-serif;
    font-size: 16pt;
}
nav.toc ol {
    list-style: none;
    padding: 0;
}
nav.toc a {
    color: inherit;
    text-decoration: none;
}
nav.toc a::after {
    content: leader('.') target-counter(attr(href), page);
}
section.file {
    break-before: page;
}
section.file h1 {
    string-set: file content();
    font-size: 11pt;
    margin: 0 0 8pt 0;
}
.highlight {
    background-color: #f8f8f8;
    border: 1px solid #ddd;
    padding: 10px;
}
.highlight pre {
    margin: 0;
    font-family: inherit;
    font-size: 9pt;
    line-height: 1.4;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.highlight .linenos {
    color: #999;
    background-color: #eee;
    padding-right: 10px;
    border-right: 1px solid #ccc;
    margin-right: 10px;
}
"""


def build_html(root, files):
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from code_to_pdf import lexer_for, read_source

    formatter = HtmlFormatter(style="default", full=False, linenos="inline", cssclass="highlight")
    toc, sections = [], []
    for i, rel in enumerate(files):
        label = html.escape(rel)
        code = highlight(read_source(os.path.join(root, rel)), lexer_for(rel), formatter)
        toc.append(f'<li><a href="#f{i}">{label}</a></li>')
        sections.append(f'<section class="file"><h1 id="f{i}">{label}</h1>{code}</section>')

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{html.escape(os.path.basename(os.path.abspath(root)))}</title>
<style>{PAGE_CSS}{formatter.get_style_defs('.highlight')}</style>
</head>
<body>
<nav class="toc"><h1>Table of Contents</h1><ol>{''.join(toc)}</ol></nav>
{''.join(sections)}
</body>
</html>
"""


def render(root, files, output):
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    document = build_html(root, files)
    out_dir = os.path.dirname(os.path.abspath(output))
    fd, tmp = tempfile.mkstemp(prefix=".code2pdf-", suffix=".pdf", dir=out_dir)
    os.close(fd)
    try:
        HTML(string=document, base_url=root).write_pdf(tmp, font_config=FontConfiguration())
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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
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
    render(root, files, output)
    print(f"Success: PDF created at {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
