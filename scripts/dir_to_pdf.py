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
import re
import signal
import subprocess
import sys
import tempfile
from collections import namedtuple


def split_list(value):
    return [item for item in value.split(",") if item] if value else []


# One file to print: RANGES are ((start, end), ...) 1-based and inclusive, () for the whole file;
# MARKED lines get a bar in the margin; REMOVED are line numbers after which lines were removed
# (0: before line 1)
Entry = namedtuple("Entry", "rel path ranges marked removed", defaults=((), (), ()))

_PART = r"(?:\+?\d+(?:-\d*)?|-\d+)"
_RANGES = re.compile(rf":({_PART}(?:,{_PART})*)$")


def parse_spec(name):
    """'src/app.py:10-20,+12-14,-16' -> ('src/app.py', ((10, 20),), ((12, 14),), (16,)): lines to
    print, lines to mark (also printed), and where lines were removed. A name without a range
    suffix -> (name, (), (), ())."""
    match = _RANGES.search(name)
    if not match:
        return name, (), (), ()
    ranges, marked, removed = [], [], []
    for part in match.group(1).split(","):
        if part.startswith("-"):
            removed.append(int(part[1:]))
            continue
        target = marked if part.startswith("+") else ranges
        start, dash, end = part.lstrip("+").partition("-")
        target.append((int(start), int(end) if end else (None if dash else int(start))))
    return name[:match.start()], tuple(ranges), tuple(marked), tuple(removed)


def split_ranges(name):
    """'src/app.py:10-20,40-' -> ('src/app.py', ((10, 20), (40, None))); 'a.py:7' -> one line;
    a name without a range suffix -> (name, ())."""
    base, ranges, marked, _ = parse_spec(name)
    return base, ranges + marked


def resolve_spec(ranges, marked, removed, total):
    """(ranges, marked, removed, note) within a file of TOTAL lines. Every range is printed, and
    +ranges are also marked; with no range at all the whole file is. Raises ValueError like
    resolve_ranges."""
    marked, note = resolve_ranges(marked, total) if marked else ((), None)
    if ranges or marked:
        ranges, note_ranges = resolve_ranges(ranges + marked, total)
        note = note or note_ranges
    for n in removed:
        if n > total:
            raise ValueError(f"-{n}: line {n} is after the end (the file has {total:,} lines)")
    return ranges, marked, tuple(sorted(set(removed))), note


def resolve_ranges(ranges, total):
    """Sorted, merged ranges within a file of TOTAL lines, and a note if an end was cut to the
    file's end. Raises ValueError for ranges that can't be printed."""
    resolved, note = [], None
    for start, end in ranges:
        if start < 1:
            raise ValueError("line numbers start at 1")
        if end is not None and end < start:
            raise ValueError(f"{start}-{end} ends before it starts")
        if start > total:
            raise ValueError(f"line {start} starts after the end (the file has {total:,} lines)")
        if end is None or end > total:
            if end is not None:
                note = f"the file has {total:,} lines; printing up to line {total:,}"
            end = total
        resolved.append((start, end))
    merged = []
    for start, end in sorted(resolved):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return tuple(merged), note


_CLOSER = re.compile(r"[}\])]|end\b")


def _indent(line):
    return len(line) - len(line.expandtabs(8).lstrip())


def cut_blocks(source, ranges):
    """[(start, end, block_end)] for each range that stops inside an indented block, such as a
    function whose last lines are left out. Indentation only, so it works for any language:
    the lines after END that are indented deeper than the range's first line, plus a closing
    `}`, `)`, `]` or `end` at that line's own indent, belong to the same block."""
    lines = source.expandtabs(8).split("\n")
    found = []
    for start, end in ranges:
        head = next((line for line in lines[start - 1:end] if line.strip()), None)
        if head is None:
            continue
        base, last = _indent(head), end
        for n in range(end, len(lines)):  # lines[n] is line n + 1
            line = lines[n]
            if not line.strip():
                continue
            if _indent(line) > base:
                last = n + 1
                continue
            if _indent(line) == base and _CLOSER.match(line.lstrip()):
                last = n + 1
            break
        if last > end:
            found.append((start, end, last))
    return found


def cut_block_warnings(entries, sources):
    """One line per range that seems to stop before the end of its block (not for entries with
    marks: those pieces are cut on purpose, e.g. by --changed)."""
    warnings = []
    for entry in entries:
        if not entry.ranges or entry.marked or entry.removed:
            continue
        source = sources[entry.path]
        for start, end, last in cut_blocks(source, entry.ranges):
            longer = [(a, last if (a, b) == (start, end) else b) for a, b in entry.ranges]
            whole = range_spec(entry.rel, resolve_ranges(longer, count_lines(source))[0], entry.marked,
                               entry.removed)
            warnings.append(f"Warning: {entry.rel}:{start}-{end} stops inside a block that goes on to "
                            f"line {last}; to print it whole, use {whole}")
    return warnings


def ranges_text(ranges, dash="–", sep=", "):
    """((12, 14), (18, 18)) -> '12–14, 18'"""
    return sep.join(f"{a}" if a == b else f"{a}{dash}{b}" for a, b in ranges)


def lines_label(ranges):
    one = len(ranges) == 1 and ranges[0][0] == ranges[0][1]
    return ("line " if one else "lines ") + ranges_text(ranges)


def range_spec(rel, ranges, marked=(), removed=()):
    """The --files-from / --list-files form: 'a.py:12-14,18-18', with marks 'a.py:1-9,+3-4,-6'.
    A range that a mark covers is left out: '+3-4' prints lines 3-4 already."""
    plain = [(a, b) for a, b in ranges if not any(c <= a and b <= d for c, d in marked)]
    parts = ([f"{a}-{b}" for a, b in plain] + [f"+{a}-{b}" for a, b in marked]
             + [f"-{n}" for n in removed])
    return rel + (":" + ",".join(parts) if parts else "")


def excerpt_label(ranges, total=None):
    """'lines 12–14, 18' (with ' of 40' when TOTAL is given); past four ranges, '13 parts, 280
    of 778 lines', which stays readable."""
    if len(ranges) <= 4:
        return lines_label(ranges) + (f" of {total:,}" if total is not None else "")
    shown = sum(b - a + 1 for a, b in ranges)
    return f"{len(ranges)} parts, {shown:,}" + (f" of {total:,}" if total is not None else "") + " lines"


def marked_label(marked, word="marked"):
    """'4 lines marked'; WORD is 'changed' for --changed."""
    count = sum(b - a + 1 for a, b in marked)
    return f"{count:,} line{'s' if count != 1 else ''} {word}"


REMOVED_MARKER = '<span class="removed">lines removed</span>'


def mark_html(code, index, marked, removed):
    """Give marked lines the class `marked` (a bar in the margin) and put a 'lines removed'
    marker after each line in REMOVED, so it travels with that line into an excerpt."""
    lines = {n for a, b in marked for n in range(a, b + 1)}
    if lines:
        code = re.sub(rf'<span id="f{index}-L-(\d+)">',
                      lambda m: m.group(0)[:-1] + ' class="marked">' if int(m.group(1)) in lines else m.group(0),
                      code)
    marker = REMOVED_MARKER
    for n in sorted(removed, reverse=True):
        nxt = re.search(rf'<span id="f{index}-L-{n + 1}"[ >]', code)
        at = nxt.start() if nxt else code.rindex("</pre>")
        code = code[:at] + marker + code[at:]
    return code


def excerpt_source(source, ranges):
    """Only the lines in RANGES (for counting and page estimates)."""
    lines = source.splitlines(keepends=True)
    return "".join("".join(lines[a - 1:b]) for a, b in ranges)


def excerpt_html(code, index, ranges, total):
    """Keep the line spans of RANGES from Pygments' linespans output (highlighting the whole file
    keeps the lexer right inside multi-line strings and comments), mark what is left out, and
    restart the line counter at each range so the numbers are the file's own."""
    starts = [(m.start(), int(m.group(1))) for m in re.finditer(rf'<span id="f{index}-L-(\d+)"[ >]', code)]
    end_pre = code.rindex("</pre>")
    if not starts:
        return code
    lines = {n: code[pos:(starts[k + 1][0] if k + 1 < len(starts) else end_pre)]
             for k, (pos, n) in enumerate(starts)}
    head = code[:starts[0][0]]
    if ranges and ranges[0][0] > 1:  # lines removed before line 1 aren't next to anything shown
        head = head.replace(REMOVED_MARKER, "")
    out, shown = [head], 0
    for start, end in ranges:
        if start > shown + 1:
            out.append(f'<span class="gap" style="counter-reset: line {start - 1}">'
                       f'{html.escape(lines_label(((shown + 1, start - 1),)))} not shown</span>')
        out.extend(lines[n] for n in range(start, end + 1) if n in lines)
        shown = end
    if shown < total:
        out.append(f'<span class="gap">{html.escape(lines_label(((shown + 1, total),)))} not shown</span>')
    out.append(code[end_pre:])
    return "".join(out)


def split_extension(name):
    """'a.tar.gz' -> 'gz'; names without a dot have no extension (same as print_all.sh)."""
    return name.rsplit(".", 1)[1] if "." in name else ""


def rel_path(path, root):
    """PATH relative to ROOT, with "/" between names on every system, as git and the PDF show
    paths (".." when it's on another Windows drive)."""
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return ".."


def is_outside(rel):
    return rel == ".." or rel.startswith("../")


class Pattern:
    """An --include/--exclude glob, matched against paths relative to ROOT split into names."""

    def __init__(self, text, root):
        self.text = text
        path = text.strip().replace(os.sep, "/")  # on Windows, src\legacy is src/legacy
        if os.path.isabs(path) and not is_outside(rel_path(path, root)):
            path = rel_path(path, root)
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
                    selected.append(rel_path(path, root))

    walk(root, [], False)
    return selected


def skip_binary(path, root, selector):
    """Binary files can't be printed; they are reported together by report_binaries()."""
    if is_binary(path):
        selector.binaries.append(rel_path(path, root))
        return True
    return False


def report_binaries(binaries):
    if binaries:
        shown = ", ".join(binaries[:3]) + (", …" if len(binaries) > 3 else "")
        noun = "file" if len(binaries) == 1 else "files"
        print(f"Skipped {len(binaries)} binary {noun}: {shown}", file=sys.stderr)


def _locate(name, root):
    path = name if os.path.isabs(name) else os.path.join(root, name)
    if not os.path.exists(path) and not os.path.isabs(name) and os.path.exists(name):
        path = name  # relative to the current folder
    return os.path.abspath(path)


def file_lines(path):
    with open(path, "rb") as f:
        data = f.read()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def read_file_list(source, root, selector, exclude):
    """Entries named in SOURCE (- for stdin), one per line, relative to ROOT (or the current
    folder) or absolute, kept in the given order, as (rel, ranges, marked, removed).
    `path:START-END[,START-END...]` prints part of a file, `+START-END` marks lines and `-N`
    says lines were removed after line N (a name that is itself an existing file is always
    taken whole). Only exclusions and binary checks apply."""
    try:
        text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    except OSError as e:
        raise ValueError(f"cannot read --files-from {source}: {e.strerror}")
    selected, seen, problems = [], set(), []
    for line in text.splitlines():
        name = line.strip()
        if not name:
            continue
        path, spec = _locate(name, root), ((), (), ())
        if not os.path.isfile(path):
            base, *wanted = parse_spec(name)
            if any(wanted) and os.path.isfile(_locate(base, root)):
                path = _locate(base, root)
                try:
                    *spec, note = resolve_spec(*wanted, file_lines(path))
                    spec = tuple(spec)
                except ValueError as e:
                    problems.append(f"{name}: {e}")
                    continue
                if note:
                    print(f"Note: {name}: {note}", file=sys.stderr)
        rel = rel_path(path, root)
        if not os.path.isfile(path):
            problems.append(f"not a file: {name}")
        elif is_outside(rel):
            problems.append(f"outside {root}: {name}")
        elif (rel, spec) not in seen:
            seen.add((rel, spec))
            if (os.path.realpath(path) in exclude or selector.excluded(rel.split("/"))
                    or skip_binary(path, root, selector)):
                continue
            selected.append((rel, *spec))
    if problems:
        raise ValueError("--files-from: " + "; ".join(problems))
    return selected


class SourceInfo:
    def __init__(self, summary, files):
        self.summary = summary  # e.g. "from commit 7afaa74 (main)"; "" outside git
        self.files = files      # rel path -> "last changed 2026-10-08" / "uncommitted changes" / "modified ..."


def _git(root, *args):
    result = subprocess.run(["git", "-C", root, "-c", "core.quotePath=false", *args],
                            capture_output=True, encoding="utf-8", errors="replace")
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
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace")
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
        import version
        fc_list = version.fc_list_command()
    present = []
    for name, probe, ranges in CJK_SCRIPTS:
        if any(lo <= ord(ch) <= hi for text in texts for ch in text if ord(ch) >= 0x1100 for lo, hi in ranges):
            present.append((name, probe))
    if not present or not fc_list:
        return []
    missing = []
    for name, probe in present:
        try:
            found = subprocess.run([fc_list, f":charset={probe}", "family"], capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=20).stdout.strip()
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
    if sys.platform == "win32":
        print(f"Warning: the files contain {'/'.join(missing)} text, but no installed font has those characters,\n"
              f"  so they will print as empty boxes. Add the language in Windows' settings (Time & language,\n"
              f"  Language & region, Add a language), which installs its fonts, then convert again.", file=sys.stderr)
        return (f"Warning: {'/'.join(missing)} text printed as empty boxes (no font for it). "
                f"Fix: add the language in Windows' settings, then convert again.")
    setup = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup_cjk_fonts.sh")
    print(f"Warning: the files contain {'/'.join(missing)} text, but no installed font has those characters,\n"
          f"  so they will print as empty boxes. Install a CJK font, then convert again:\n"
          f"    without sudo: {setup}   (~26 MB, into ~/.local/share/fonts)\n"
          f"    with sudo:    sudo apt install fonts-noto-cjk", file=sys.stderr)
    return (f"Warning: {'/'.join(missing)} text printed as empty boxes (no CJK font installed). "
            f"Fix: {setup}, then convert again.")


def count_lines(source):
    return source.count("\n") + (1 if source and not source.endswith("\n") else 0)


def build_sections(entries, theme, info, sources=None, first_index=0, marked_as="marked"):
    """One <section> per file. Returns (sections, groups, total_lines, style_defs), where groups is
    group_by_folder() for the contents page; indexes start at FIRST_INDEX."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from code_to_pdf import lexer_for, read_source

    formatter = HtmlFormatter(style=theme.style, linespans="L", cssclass="highlight")
    sections = []
    total_lines = 0
    entries = [Entry(*entry) for entry in entries]
    for i, (rel, path, ranges, marked, removed) in enumerate(entries, first_index):
        source = sources[path] if sources and path in sources else read_source(path)
        lexer = lexer_for(rel, source)
        lines = count_lines(source)
        folder, name = os.path.split(rel)
        code = highlight(source, lexer, formatter).replace('id="L-', f'id="f{i}-L-')
        folder_html = f'<div class="dir">{html.escape(folder)}/</div>' if folder else ""
        language = "Plain text" if lexer.name == "Text only" else lexer.name
        if marked or removed:
            code = mark_html(code, i, marked, removed)
        every = marked == ((1, lines),)
        if ranges == ((1, lines),) and (marked or removed):  # all of it, with marks: a whole file
            ranges = ()
        if ranges:
            code = excerpt_html(code, i, ranges, lines)
            details = f"{language}, {excerpt_label(ranges, lines)}"
            lines = sum(end - start + 1 for start, end in ranges)
        else:
            details = f"{language}, {lines:,} line{'s' if lines != 1 else ''}"
        if marked:
            details += f", all {marked_as}" if every else f", {marked_label(marked, marked_as)}"
        total_lines += lines
        if info.files.get(rel):
            details += f", {info.files[rel]}"
        sections.append(
            f'<section class="file"><header>{folder_html}'
            f'<h1 id="f{i}" data-path="{html.escape(rel)}">{html.escape(name)}</h1>'
            f'<div class="meta">{html.escape(details)}</div></header>{code}</section>')
    groups = group_by_folder(contents_labels(entries, marked_as, sources), first_index)
    return sections, groups, total_lines, formatter.get_style_defs(".highlight")


def contents_labels(entries, marked_as="marked", sources=None):
    """Paths as the contents page lists them: 'sub/c.js (lines 2–3)' for part of a file,
    'app.py (lines 2–30, 4 lines marked)' with marks ('all 14 lines changed' for a new file,
    when SOURCES says how long it is)."""
    labels = []
    for entry in (Entry(*e) for e in entries):
        total = count_lines(sources[entry.path]) if sources and entry.path in sources else None
        ranges = entry.ranges
        if ranges == ((1, total),) and (entry.marked or entry.removed):  # all of it: a whole file
            ranges = ()
        if entry.marked and not ranges and entry.marked == ((1, total),):
            mark = f"all {marked_label(entry.marked, marked_as)}"
        else:
            mark = marked_label(entry.marked, marked_as)
        notes = ([excerpt_label(ranges)] if ranges else []) + ([mark] if entry.marked else [])
        labels.append(entry.rel + (f" ({', '.join(notes)})" if notes else ""))
    return labels


def printed_sources(entries, sources):
    """What each entry prints: the whole source, or only its line ranges."""
    return [excerpt_source(sources[e.path], e.ranges) if e.ranges else sources[e.path]
            for e in (Entry(*e) for e in entries)]


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


def build_contents(project, file_count, total_lines, printed, info, groups, page_numbers=None, summary=None,
                   legend=None):
    """The contents page. Without PAGE_NUMBERS, entries link to #f<i> and WeasyPrint fills in the
    numbers; with {index: page}, the numbers are written in and links use the placeholder
    code2pdf:f<i>, which parts.py rewires once the parts are joined. SUMMARY (--summary) says what
    the document is; LEGEND explains the marks (--changed)."""
    def entry(i, name):
        if page_numbers is None:
            return f'<li><a href="#f{i}">{html.escape(name)}</a></li>'
        return f'<li><a href="code2pdf:f{i}" data-page="{page_numbers[i]}">{html.escape(name)}</a></li>'

    toc = "".join(
        f'<h2>{html.escape((folder or project) + "/")}</h2><ol>{"".join(entry(i, n) for i, n in items)}</ol>'
        for folder, items in groups)
    printed_line = f"Printed {printed}" + (f" {info.summary}" if info.summary else "")
    lede = f'<p class="lede">{html.escape(summary)}</p>' if summary else ""
    counts = (f'{file_count:,} file{"s" if file_count != 1 else ""}, '
              f'{total_lines:,} line{"s" if total_lines != 1 else ""}' + (f"; {legend}" if legend else ""))
    return (f'<nav class="toc"><h1>{html.escape(project)}</h1>{lede}'
            f'<p class="summary">{html.escape(counts)}</p>'
            f'<p class="summary">{html.escape(printed_line)}</p>{toc}</nav>')


def wrap_document(title, printed_moment, css, body, description=None):
    # DESCRIPTION (--summary) becomes the PDF's Subject
    description_meta = f'\n<meta name="description" content="{html.escape(description)}">' if description else ""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<meta name="generator" content="code2pdf">{description_meta}
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


def build_html(entries, theme, project, printed_moment, info, contents=True, sources=None, summary=None,
               legend=None, marked_as="marked"):
    """The whole document in one HTML string (single-pass rendering).
    entries: [(display path, absolute path)]; info: SourceInfo keyed by display path;
    sources: optional {absolute path: text} already read by the caller."""
    import theme as themes

    printed = printed_moment.date().isoformat()
    sections, groups, total_lines, style_defs = build_sections(entries, theme, info, sources, marked_as=marked_as)
    nav = build_contents(project, len(entries), total_lines, printed, info, groups, summary=summary,
                         legend=legend) if contents else ""
    if summary and not contents and sections:  # one file: the summary goes under its name
        sections[0] = sections[0].replace("</header>", f'<p class="lede">{html.escape(summary)}</p></header>', 1)
    title = project or (Entry(*entries[0]).rel if entries else "code2pdf")
    css = themes.font_face_css() + style_defs + themes.page_css(theme, header_right(project, printed))
    return wrap_document(title, printed_moment, css, nav + "".join(sections), description=summary)


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
                    quiet=True, jobs=None, summary=None, legend=None, warn_cut=True, marked_as="marked"):
    """Render [(display path, absolute path)] into OUTPUT. Raises ValueError for an unknown theme.
    Unless QUIET, reports progress on stderr. SUMMARY and LEGEND go on the contents page;
    WARN_CUT=False keeps quiet about ranges that stop inside a block (--changed makes those);
    MARKED_AS names what marks mean in labels ('4 lines changed')."""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    from code_to_pdf import read_source
    import progress as progress_report
    import theme as themes

    theme = themes.resolve_theme(theme_name)
    entries = [Entry(*entry) for entry in entries]
    sources = {e.path: read_source(e.path) for e in entries}
    printed = printed_sources(entries, sources)
    cjk_reminder = warn_missing_cjk_fonts(printed + [e.rel for e in entries])
    cut_warnings = cut_block_warnings(entries, sources) if warn_cut else []
    for line in cut_warnings:
        print(line, file=sys.stderr)
    progress = progress_report.Progress(
        sys.stderr, files=len(entries), lines=sum(count_lines(text) for text in printed),
        estimated_pages=progress_report.estimate_pages(printed, contents=contents), quiet=quiet)
    if root is None:  # single file: dates come from its own folder
        rel, path = entries[0].rel, entries[0].path
        single = source_info(os.path.dirname(path), [os.path.basename(path)])
        info = SourceInfo(single.summary, {rel: single.files[os.path.basename(path)]})
    else:
        info = source_info(root, list(dict.fromkeys(e.rel for e in entries)))

    moment = printed_at()
    out_dir = os.path.dirname(os.path.abspath(output))
    estimates = [progress_report.estimate_pages([text]) for text in printed]
    import parts as parts_mode
    big = contents and root is not None and sum(estimates) > 2 * parts_mode.part_pages()
    if big and not parts_mode.available():
        if not quiet:
            print("  (pypdf is not installed, so this big document is rendered in one pass; "
                  "install pypdf to use less memory)", file=sys.stderr)
        big = False
    if big:
        tmp = new_temp_pdf(out_dir)
        try:
            pages = parts_mode.render_in_parts(entries, tmp, theme, project, moment, info, sources, estimates,
                                               progress, root, jobs=jobs, summary=summary, legend=legend,
                                               marked_as=marked_as)
            os.replace(tmp, output)
        except BaseException:
            progress.abort()
            raise
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        progress.done(pages=pages, output=output)
        for line in cut_warnings + ([cjk_reminder] if cjk_reminder else []):
            print(line, file=sys.stderr)
        return

    document = build_html(entries, theme, project, moment, info, contents=contents, sources=sources,
                          summary=summary, legend=legend, marked_as=marked_as)
    tmp = new_temp_pdf(out_dir)
    try:
        with _WeasyPrintProgress(progress):
            rendered = HTML(string=document, base_url=root or out_dir).render(font_config=FontConfiguration())
            rendered.write_pdf(tmp, finisher=themes.drop_apple_cid_tables)
        os.replace(tmp, output)
    except BaseException:
        progress.abort()
        raise
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    progress.done(pages=len(rendered.pages), output=output)
    for line in cut_warnings + ([cjk_reminder] if cjk_reminder else []):  # again, after "Done:"
        print(line, file=sys.stderr)


def exit_on_signals():
    """End the run on SIGTERM or SIGHUP (a command timeout, a closed terminal) the way Ctrl-C
    does, so `finally` removes the temp files and parts workers are stopped."""
    def stop(signum, frame):
        raise KeyboardInterrupt(signal.Signals(signum).name)
    for name in ("SIGTERM", "SIGHUP"):  # Windows has no SIGHUP
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)


def exit_now(code):
    """Exit with CODE once the PDF is written, without freeing every object first: the laid-out
    pages of a 500-page document take ~5 GB and several seconds to free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError):
            pass
    os._exit(code)


def new_temp_pdf(out_dir):
    """A temporary PDF next to the output, for os.replace. mkstemp makes files private (0600),
    so it gets the permissions a new file normally has (0644 with the usual umask)."""
    fd, tmp = tempfile.mkstemp(prefix=".code2pdf-", suffix=".pdf", dir=out_dir)
    os.close(fd)
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(tmp, 0o666 & ~umask)
    return tmp


def utf8_stdio():
    """On Windows, stdin, stdout and stderr in a pipe use the ANSI code page (cp1252, say), which
    has no "→" and no Chinese: read and write UTF-8 there, as on macOS and Linux."""
    if sys.platform == "win32":
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):  # not a text stream, or closed
                pass


def run_main(main, *args):
    """sys.exit(main(*args)), with an interruption reported in one line instead of a traceback."""
    utf8_stdio()
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
    parser.add_argument("--changed")
    parser.add_argument("--summary")
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
    if args.files_from and args.changed:
        print("Error: use --changed or --files-from, not both (`--changed REV --list-files` prints "
              "a list you can edit and pass to --files-from)", file=sys.stderr)
        return 1
    for given in ("files_from", "changed"):
        if getattr(args, given) and args.include:
            print(f"Error: --include has no effect with --{given.replace('_', '-')} "
                  "(it chooses the files itself)", file=sys.stderr)
            return 1

    legend = None
    try:
        selector = Selector(args, root)
        exclude = {os.path.realpath(output)}
        if args.files_from:
            files = read_file_list(args.files_from, root, selector, exclude)
        elif args.changed:
            import changes

            def keep(rel, path):
                return not (os.path.realpath(path) in exclude or selector.excluded(rel.split("/"))
                            or skip_binary(path, root, selector))
            files, legend, notes = changes.changed_entries(root, args.changed, keep)
            for note in notes:
                print(f"Note: --changed {args.changed}: {note}", file=sys.stderr)
        else:
            files = [(rel, (), (), ()) for rel in collect_files(root, selector, exclude)]
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    report_binaries(selector.binaries)
    for option, text in selector.unused_patterns():
        print(f"Warning: {option} {text!r} matched nothing", file=sys.stderr)
    if args.list_files:
        listed = [Entry(rel, os.path.join(root, rel), *spec) for rel, *spec in files if spec[0]]
        texts = {e.path: open(e.path, encoding="utf-8", errors="replace").read() for e in listed}
        for line in cut_block_warnings(listed, texts) if not args.changed else ():
            print(line, file=sys.stderr)
        print("\n".join(range_spec(rel, *spec) for rel, *spec in files))
        return 0
    if not files:
        if args.changed:
            print(f"Error: nothing to print: no file changed since {args.changed}", file=sys.stderr)
        else:
            print(f"Error: no matching files in {root}", file=sys.stderr)
        return 1

    entries = [Entry(rel, os.path.join(root, rel), *spec) for rel, *spec in files]
    os.makedirs(os.path.dirname(output), exist_ok=True)
    try:
        render_document(entries, output, theme_name=args.theme, project=os.path.basename(root),
                        contents=True, root=root, quiet=args.quiet, jobs=args.jobs,
                        summary=args.summary, legend=legend, warn_cut=not args.changed,
                        marked_as="changed" if args.changed else "marked")
    except ValueError as e:
        hint = "; run `code2pdf --list-themes` to see the names" if "theme" in str(e) else ""
        print(f"Error: {e}{hint}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    exit_now(run_main(main))
