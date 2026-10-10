#!/usr/bin/env python3
"""
Convert a directory of source files into one PDF: a table of contents followed by
every file, rendered in a single WeasyPrint pass.

Usage (positional arguments match print_all.sh):
  dir_to_pdf.py ROOT OUTPUT BLACKLIST_JSON BLACKLIST_PATTERN EXTENSIONS_JSON NAMES_JSON
                INCLUDE_NO_EXTENSION IGNORE_FILES IGNORE_TYPES IGNORE_FOLDERS INCLUDE_TYPES
                [--list-files] [--theme NAME]
  dir_to_pdf.py --list-themes

  --list-files       Print the selected files (relative to ROOT) instead of rendering.
  --include GLOB     Also include matching files, even hidden ones or ones in skipped folders.
  --exclude GLOB     Leave out matching files and folders; wins over everything else.
  --files-from FILE  Convert exactly the files listed in FILE (- for stdin), in that order.
  --output PDF       Write here instead of OUTPUT (a folder gets merged.pdf inside it).
  --theme NAME       paper (default), mono, or any Pygments style; default from $CODE2PDF_THEME.
  --quiet            No progress output (also $CODE2PDF_QUIET).
  --list-themes      Print every theme name.

Globs: * and ? match within a name, ** matches any number of folders. A glob without "/"
matches a name at any depth (*_test.go); one with "/" matches the path from ROOT
(src/legacy, docs/**/*.md). A glob that matches a folder covers everything in it.

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
import signal
import subprocess
import sys
import tempfile


def split_list(value):
    return [item for item in value.split(",") if item] if value else []


def split_extension(name):
    """'a.tar.gz' -> 'gz'; names without a dot have no extension (same as print_all.sh)."""
    return name.rsplit(".", 1)[1] if "." in name else ""


class Pattern:
    """An --include/--exclude glob, matched against paths relative to ROOT split into names."""

    def __init__(self, text, root):
        self.text = text
        path = text.strip()
        if os.path.isabs(path) and (path + "/").startswith(root.rstrip("/") + "/"):
            path = os.path.relpath(path, root)
        while path.startswith("./"):
            path = path[2:]
        path = path.rstrip("/")
        anchored = "/" in path
        self.segments = [part for part in path.split("/") if part not in ("", ".")]
        if not self.segments:
            raise ValueError(f"empty pattern: {text!r}")
        if not anchored:
            self.segments.insert(0, "**")
        self.used = False

    def covers(self, parts):
        """True if the pattern matches PARTS or one of its folders."""
        hit = any(_glob_match(self.segments, parts[:n]) for n in range(1, len(parts) + 1))
        self.used = self.used or hit
        return hit

    def may_reach(self, parts, skipped):
        """Could the pattern match PARTS (a folder) or something below it? A folder that is
        normally skipped (SKIPPED[i]) must be named literally: * never pulls in node_modules or .git."""
        return _glob_reach(self.segments, parts, skipped)


def _name_match(name, glob):
    """fnmatch, but like the shell a wildcard doesn't match a leading dot (* skips .env)."""
    return fnmatch.fnmatchcase(name, glob) and (glob.startswith(".") or not name.startswith("."))


def _glob_match(pattern, parts):
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(_glob_match(pattern[1:], parts[i:]) for i in range(len(parts) + 1))
    return bool(parts) and _name_match(parts[0], pattern[0]) and _glob_match(pattern[1:], parts[1:])


def _glob_reach(pattern, parts, skipped):
    if not parts or not pattern:  # inside the folder, or the pattern already matched a parent
        return True
    if pattern[0] == "**":
        return (_glob_reach(pattern[1:], parts, skipped)
                or (not skipped[0] and _glob_reach(pattern, parts[1:], skipped[1:])))
    ok = parts[0] == pattern[0] if skipped[0] else _name_match(parts[0], pattern[0])
    return ok and _glob_reach(pattern[1:], parts[1:], skipped[1:])


def is_binary(path):
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(8192)
    except OSError:
        return False


class Selector:
    """File selection. The default rules (built-in lists, --ignore-*, --include-types) are kept
    identical to the previous bash implementation; --include adds to them and --exclude wins."""

    def __init__(self, args, root=""):
        self.blacklist = set(json.loads(args.blacklist_json or "[]"))
        self.pattern = args.blacklist_pattern
        self.extensions = set(json.loads(args.extensions_json or "[]"))
        self.names = set(json.loads(args.names_json or "[]"))
        self.include_no_extension = args.include_no_extension == "true"
        self.ignore_files = set(split_list(args.ignore_files))
        self.ignore_types = set(split_list(args.ignore_types))
        self.ignore_folders = set(split_list(args.ignore_folders))
        self.include_types = set(split_list(args.include_types))
        self.includes = [Pattern(text, root) for text in getattr(args, "include", None) or []]
        self.excludes = [Pattern(text, root) for text in getattr(args, "exclude", None) or []]
        self.binaries = []  # binary files that matched, skipped

    def excluded(self, parts):
        return any([pattern.covers(parts) for pattern in self.excludes])  # list: mark every match used

    def included(self, parts):
        return any([pattern.covers(parts) for pattern in self.includes])

    def may_include_below(self, parts):
        skipped = [name.startswith(".") or self.skip_folder(name) for name in parts]
        return any(pattern.may_reach(parts, skipped) for pattern in self.includes)

    def unused_patterns(self):
        return ([("--include", p.text) for p in self.includes if not p.used]
                + [("--exclude", p.text) for p in self.excludes if not p.used])

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
    """Depth-first walk, entries sorted by name; hidden entries skipped unless --include names
    them; symlink loops cut. Inside a normally skipped folder only --include matches count."""
    visited = {os.path.realpath(root)}
    selected = []

    def walk(folder, parts, forced):
        try:
            entries = sorted(os.listdir(folder))
        except OSError as e:
            print(f"Warning: cannot read {folder}: {e}", file=sys.stderr)
            return
        for name in entries:
            path = os.path.join(folder, name)
            rel_parts = parts + [name]
            if os.path.isdir(path):
                real = os.path.realpath(path)
                if real in visited or selector.excluded(rel_parts):
                    continue
                skipped = forced or name.startswith(".") or selector.skip_folder(name)
                if skipped and not selector.may_include_below(rel_parts):
                    continue
                visited.add(real)
                walk(path, rel_parts, skipped)
            elif os.path.isfile(path):
                if os.path.realpath(path) in exclude or selector.excluded(rel_parts):
                    continue
                default = not forced and not name.startswith(".") and selector.wants_file(name)
                if (selector.included(rel_parts) or default) and not skip_binary(path, root, selector):
                    selected.append(os.path.relpath(path, root))

    walk(root, [], False)
    return selected


def skip_binary(path, root, selector):
    """Binary files can't be printed; they are reported together by report_binaries()."""
    if is_binary(path):
        selector.binaries.append(os.path.relpath(path, root))
        return True
    return False


def report_binaries(binaries):
    if binaries:
        shown = ", ".join(binaries[:3]) + (", …" if len(binaries) > 3 else "")
        noun = "file" if len(binaries) == 1 else "files"
        print(f"Skipped {len(binaries)} binary {noun}: {shown}", file=sys.stderr)


def read_file_list(source, root, selector, exclude):
    """Files named in SOURCE (- for stdin), one per line, relative to ROOT (or the current
    folder) or absolute, kept in the given order. Only exclusions and binary checks apply."""
    try:
        text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    except OSError as e:
        raise ValueError(f"cannot read --files-from {source}: {e.strerror}")
    selected, seen, problems = [], set(), []
    for line in text.splitlines():
        name = line.strip()
        if not name:
            continue
        path = name if os.path.isabs(name) else os.path.join(root, name)
        if not os.path.exists(path) and not os.path.isabs(name) and os.path.exists(name):
            path = name  # relative to the current folder
        path = os.path.abspath(path)
        rel = os.path.relpath(path, root)
        if not os.path.isfile(path):
            problems.append(f"not a file: {name}")
        elif rel == ".." or rel.startswith(".." + os.sep):
            problems.append(f"outside {root}: {name}")
        elif rel not in seen:
            seen.add(rel)
            if (os.path.realpath(path) in exclude or selector.excluded(rel.split(os.sep))
                    or skip_binary(path, root, selector)):
                continue
            selected.append(rel)
    if problems:
        raise ValueError("--files-from: " + "; ".join(problems))
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


# One probe character per script: if no installed font has it, that script prints as empty boxes
CJK_SCRIPTS = [
    ("Chinese", "4e2d", ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF))),  # 中
    ("Japanese", "3042", ((0x3040, 0x30FF), (0x31F0, 0x31FF))),                  # あ
    ("Korean", "d55c", ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))),  # 한
]


def missing_cjk_fonts(texts, fc_list="auto"):
    """Scripts (Chinese/Japanese/Korean) that occur in TEXTS but that no installed font covers,
    according to fontconfig's fc-list. Returns [] when fc-list is unavailable (can't tell)."""
    if fc_list == "auto":
        import shutil
        fc_list = shutil.which("fc-list")
    present = []
    for name, probe, ranges in CJK_SCRIPTS:
        if any(lo <= ord(ch) <= hi for text in texts for ch in text if ord(ch) >= 0x1100 for lo, hi in ranges):
            present.append((name, probe))
    if not present or not fc_list:
        return []
    missing = []
    for name, probe in present:
        try:
            found = subprocess.run([fc_list, f":charset={probe}", "family"], capture_output=True, text=True,
                                   timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return []
        if not found:
            missing.append(name)
    return missing


def warn_missing_cjk_fonts(texts):
    """Print a warning if CJK text has no font; return a one-line reminder for after "Done:" (or "")."""
    missing = missing_cjk_fonts(texts)
    if not missing:
        return ""
    setup = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_cjk_fonts.sh")
    print(f"Warning: the files contain {'/'.join(missing)} text, but no installed font has those characters,\n"
          f"  so they will print as empty boxes. Install a CJK font, then convert again:\n"
          f"    without sudo: {setup}   (~26 MB, into ~/.local/share/fonts)\n"
          f"    with sudo:    sudo apt install fonts-noto-cjk", file=sys.stderr)
    return (f"Warning: {'/'.join(missing)} text printed as empty boxes (no CJK font installed). "
            f"Fix: {setup}, then convert again.")


def count_lines(source):
    return source.count("\n") + (1 if source and not source.endswith("\n") else 0)


def build_sections(entries, theme, info, sources=None, first_index=0):
    """One <section> per file. Returns (sections, groups, total_lines, style_defs), where groups is
    group_by_folder() for the contents page; indexes start at FIRST_INDEX."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from code_to_pdf import lexer_for, read_source

    formatter = HtmlFormatter(style=theme.style, linespans="L", cssclass="highlight")
    sections = []
    total_lines = 0
    for i, (rel, path) in enumerate(entries, first_index):
        source = sources[path] if sources and path in sources else read_source(path)
        lexer = lexer_for(rel, source)
        lines = count_lines(source)
        total_lines += lines
        folder, name = os.path.split(rel)
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
    groups = group_by_folder([rel for rel, _ in entries], first_index)
    return sections, groups, total_lines, formatter.get_style_defs(".highlight")


def group_by_folder(rels, first_index=0):
    """[(folder, [(index, file name)])] in document order. A folder that comes back later (a
    root file after a subfolder, or a --files-from list) gets a new heading, so the contents
    page always follows page order."""
    groups = []
    for i, rel in enumerate(rels, first_index):
        folder, name = os.path.split(rel)
        if not groups or groups[-1][0] != folder:
            groups.append((folder, []))
        groups[-1][1].append((i, name))
    return groups


def build_contents(project, file_count, total_lines, printed, info, groups, page_numbers=None):
    """The contents page. Without PAGE_NUMBERS, entries link to #f<i> and WeasyPrint fills in the
    numbers; with {index: page}, the numbers are written in and links use the placeholder
    code2pdf:f<i>, which parts.py rewires once the parts are joined."""
    def entry(i, name):
        if page_numbers is None:
            return f'<li><a href="#f{i}">{html.escape(name)}</a></li>'
        return f'<li><a href="code2pdf:f{i}" data-page="{page_numbers[i]}">{html.escape(name)}</a></li>'

    toc = "".join(
        f'<h2>{html.escape((folder or project) + "/")}</h2><ol>{"".join(entry(i, n) for i, n in items)}</ol>'
        for folder, items in groups)
    printed_line = f"Printed {printed}" + (f" {info.summary}" if info.summary else "")
    return (f'<nav class="toc"><h1>{html.escape(project)}</h1>'
            f'<p class="summary">{file_count:,} file{"s" if file_count != 1 else ""}, '
            f'{total_lines:,} line{"s" if total_lines != 1 else ""}</p>'
            f'<p class="summary">{html.escape(printed_line)}</p>{toc}</nav>')


def wrap_document(title, printed_moment, css, body):
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<meta name="generator" content="code2pdf">
<meta name="dcterms.created" content="{printed_moment.isoformat(timespec='seconds')}">
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def header_right(project, printed):
    return f"{project}, {printed}" if project else printed


def build_html(entries, theme, project, printed_moment, info, contents=True, sources=None):
    """The whole document in one HTML string (single-pass rendering).
    entries: [(display path, absolute path)]; info: SourceInfo keyed by display path;
    sources: optional {absolute path: text} already read by the caller."""
    import theme as themes

    printed = printed_moment.date().isoformat()
    sections, groups, total_lines, style_defs = build_sections(entries, theme, info, sources)
    nav = build_contents(project, len(entries), total_lines, printed, info, groups) if contents else ""
    title = project or (entries[0][0] if entries else "code2pdf")
    css = themes.font_face_css() + style_defs + themes.page_css(theme, header_right(project, printed))
    return wrap_document(title, printed_moment, css, nav + "".join(sections))


class _WeasyPrintProgress:
    """Forward WeasyPrint's progress log (stages, and one message per laid-out page) to Progress."""

    def __init__(self, progress):
        import logging
        self.progress = progress
        self.logger = logging.getLogger("weasyprint.progress")
        self.handler = logging.Handler()
        self.handler.emit = self.emit
        self.saved = (self.logger.level, self.logger.propagate)

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("Step 1 "):
            self.progress.preparing()
        elif message.startswith("Step 5 - Creating layout - Page "):
            self.progress.page(int(message.split("Page ")[1].split()[0]))
        elif message.startswith("Step 6 "):
            self.progress.writing()

    def __enter__(self):
        import logging
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        return self

    def __exit__(self, *exc):
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.saved[0])
        self.logger.propagate = self.saved[1]


def render_document(entries, output, theme_name="paper", project=None, contents=True, root=None,
                    quiet=True, jobs=None):
    """Render [(display path, absolute path)] into OUTPUT. Raises ValueError for an unknown theme.
    Unless QUIET, reports progress on stderr."""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    from code_to_pdf import read_source
    import progress as progress_report
    import theme as themes

    theme = themes.resolve_theme(theme_name)
    sources = {path: read_source(path) for _, path in entries}
    cjk_reminder = warn_missing_cjk_fonts(list(sources.values()) + [rel for rel, _ in entries])
    progress = progress_report.Progress(
        sys.stderr, files=len(entries), lines=sum(count_lines(text) for text in sources.values()),
        estimated_pages=progress_report.estimate_pages(list(sources.values()), contents=contents), quiet=quiet)
    if root is None:  # single file: dates come from its own folder
        rel, path = entries[0]
        single = source_info(os.path.dirname(path), [os.path.basename(path)])
        info = SourceInfo(single.summary, {rel: single.files[os.path.basename(path)]})
    else:
        info = source_info(root, [rel for rel, _ in entries])

    moment = printed_at()
    out_dir = os.path.dirname(os.path.abspath(output))
    estimates = [progress_report.estimate_pages([sources[path]]) for _, path in entries]
    import parts as parts_mode
    big = contents and root is not None and sum(estimates) > 2 * parts_mode.part_pages()
    if big and not parts_mode.available():
        if not quiet:
            print("  (pypdf is not installed, so this big document is rendered in one pass; "
                  "install pypdf to use less memory)", file=sys.stderr)
        big = False
    if big:
        fd, tmp = tempfile.mkstemp(prefix=".code2pdf-", suffix=".pdf", dir=out_dir)
        os.close(fd)
        try:
            pages = parts_mode.render_in_parts(entries, tmp, theme, project, moment, info, sources, estimates,
                                               progress, root, jobs=jobs)
            os.replace(tmp, output)
        except BaseException:
            progress.abort()
            raise
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        progress.done(pages=pages, output=output)
        if cjk_reminder:
            print(cjk_reminder, file=sys.stderr)
        return

    document = build_html(entries, theme, project, moment, info, contents=contents, sources=sources)
    fd, tmp = tempfile.mkstemp(prefix=".code2pdf-", suffix=".pdf", dir=out_dir)
    os.close(fd)
    try:
        with _WeasyPrintProgress(progress):
            rendered = HTML(string=document, base_url=root or out_dir).render(font_config=FontConfiguration())
            rendered.write_pdf(tmp)
        os.replace(tmp, output)
    except BaseException:
        progress.abort()
        raise
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    progress.done(pages=len(rendered.pages), output=output)
    if cjk_reminder:
        print(cjk_reminder, file=sys.stderr)


def exit_on_signals():
    """End the run on SIGTERM or SIGHUP (a command timeout, a closed terminal) the way Ctrl-C
    does, so `finally` removes the temp files and parts workers are stopped."""
    def stop(signum, frame):
        raise KeyboardInterrupt(signal.Signals(signum).name)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)


def run_main(main, *args):
    """sys.exit(main(*args)), with an interruption reported in one line instead of a traceback."""
    exit_on_signals()
    try:
        return main(*args)
    except KeyboardInterrupt as e:
        print(f"code2pdf: stopped ({e.args[0] if e.args else 'SIGINT'}); nothing was written",
              file=sys.stderr)
        return 130


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Convert a directory of source files into one PDF.")
    for name in ("root", "output", "blacklist_json", "blacklist_pattern", "extensions_json",
                 "names_json", "include_no_extension", "ignore_files", "ignore_types",
                 "ignore_folders", "include_types"):
        parser.add_argument(name, nargs="?", default="")
    parser.add_argument("--list-files", action="store_true")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--files-from")
    parser.add_argument("--output", dest="output_option")
    parser.add_argument("--list-themes", action="store_true")
    parser.add_argument("--theme", default=os.environ.get("CODE2PDF_THEME", "paper"))
    parser.add_argument("--quiet", action="store_true", default=bool(os.environ.get("CODE2PDF_QUIET")))
    parser.add_argument("--jobs", type=int, default=None)
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
    output = os.path.abspath(args.output_option or args.output or os.path.join(root, "merged.pdf"))
    if os.path.isdir(output):
        output = os.path.join(output, "merged.pdf")
    if args.files_from and args.include:
        print("Error: --include has no effect with --files-from (the list is used as given)",
              file=sys.stderr)
        return 1

    try:
        selector = Selector(args, root)
        exclude = {os.path.realpath(output)}
        if args.files_from:
            files = read_file_list(args.files_from, root, selector, exclude)
        else:
            files = collect_files(root, selector, exclude)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    report_binaries(selector.binaries)
    for option, text in selector.unused_patterns():
        print(f"Warning: {option} {text!r} matched nothing", file=sys.stderr)
    if args.list_files:
        print("\n".join(files))
        return 0
    if not files:
        print(f"Error: no matching files in {root}", file=sys.stderr)
        return 1

    entries = [(rel, os.path.join(root, rel)) for rel in files]
    os.makedirs(os.path.dirname(output), exist_ok=True)
    try:
        render_document(entries, output, theme_name=args.theme, project=os.path.basename(root),
                        contents=True, root=root, quiet=args.quiet, jobs=args.jobs)
    except ValueError as e:
        print(f"Error: {e}; run `code2pdf --list-themes` to see the names", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(run_main(main))
