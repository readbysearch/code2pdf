"""--changed REV: the files changed between REV and the working tree, as list entries.

Each change becomes a piece of its file: the changed lines, grown to the enclosing block while
that block is small (a whole function rather than three lines of it), else with a few lines of
context. The changed lines are marked, and a marker shows where lines were removed. Only
indentation is read, as in dir_to_pdf.cut_blocks, so it works for any language.
"""

import os
import re
import subprocess

BLOCK_LIMIT = 40   # a piece grows to its enclosing block while the block has at most this many lines
CONTEXT = 3        # otherwise it gets this many lines on each side
MERGE_GAP = 3      # pieces fewer than this many lines apart join up
WHOLE_SHARE = 0.8  # a file whose pieces cover this much of it is printed whole
HEADERS = True     # also print the header lines of the blocks a piece is in (`def f():`), as git does

_CLOSER = re.compile(r"[}\])]|end\b")
_LEAD_IN = re.compile(r"(@|#|//|/\*|\*|--|;)")  # decorators and comments that belong to the next line
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class GitMissing(ValueError):
    pass


def _git(root, *args):
    try:
        result = subprocess.run(["git", "-C", root, "-c", "core.quotePath=false", *args],
                                capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        raise GitMissing("--changed needs git, which isn't installed") from None
    if result.returncode != 0:
        raise ValueError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "git failed")
    return result.stdout


def _unquote(name):
    """git's C-style quoting, for names with tabs, newlines, quotes or backslashes."""
    if not (name.startswith('"') and name.endswith('"')):
        return name
    return bytes(name[1:-1], "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")


def diff_marks(root, rev):
    """({rel: (marked, removed)}, statuses, untracked) between REV and the working tree, with
    paths relative to ROOT. statuses is [(status letter, rel, old rel or None)]."""
    try:
        _git(root, "rev-parse", "--is-inside-work-tree")
    except GitMissing:
        raise
    except ValueError:
        raise ValueError(f"--changed needs a git repository, and {root} isn't in one")
    if ".." in rev:
        raise ValueError(f"--changed takes one revision and compares it with the files as they are "
                         f"now; {rev!r} is a range")
    try:
        _git(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    except ValueError:
        raise ValueError(f"--changed: unknown revision {rev!r}")
    fields = _git(root, "diff", "--relative", "-M", "--name-status", "-z", rev, "--").split("\0")
    statuses, i = [], 0
    while i < len(fields) - 1:
        status = fields[i]
        if status[:1] in "RC":
            statuses.append((status[0], fields[i + 2], fields[i + 1]))
            i += 3
        else:
            statuses.append((status[:1], fields[i + 1], None))
            i += 2
    marks, current = {}, None
    for line in _git(root, "diff", "--relative", "-M", "-U0", "--no-color", "--no-ext-diff",
                     "--no-prefix", rev, "--").split("\n"):
        if line.startswith("+++ "):
            name = _unquote(line[4:])
            current = None if name == "/dev/null" else name
            if current is not None:
                marks.setdefault(current, ([], []))
        elif current is not None and line.startswith("@@"):
            match = _HUNK.match(line)
            start, count = int(match.group(1)), int(match.group(2) or 1)
            if count:
                marks[current][0].append((start, start + count - 1))
            else:
                marks[current][1].append(start)  # lines removed after line START
    untracked = [name for name in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if name]
    return marks, statuses, untracked


def _indent(text):
    return len(text) - len(text.lstrip())


def _blank(lines, n):
    return not lines[n - 1].strip()


def _block_end(lines, head, after):
    """The last line of the block headed by line HEAD, looking from line AFTER on: lines
    indented deeper than HEAD, then a closing } ) ] or `end` at HEAD's indent."""
    base, last = _indent(lines[head - 1]), after
    for n in range(after + 1, len(lines) + 1):
        if _blank(lines, n):
            continue
        if _indent(lines[n - 1]) > base:
            last = n
            continue
        if _indent(lines[n - 1]) == base and _CLOSER.match(lines[n - 1].lstrip()):
            last = n
        break
    return last


def _header_above(lines, lo, hi):
    """The nearest line above LO indented less than every line in LO..HI: the line that opens
    the block they are in."""
    body = [_indent(lines[n - 1]) for n in range(lo, hi + 1) if not _blank(lines, n)]
    if not body:
        return None
    level = min(body)
    for n in range(lo - 1, 0, -1):
        if not _blank(lines, n) and _indent(lines[n - 1]) < level:
            # `) -> None:` or `) error {` ends a statement that starts higher up (a signature
            # over several lines): the header is the line that opened it
            while n > 1 and _CLOSER.match(lines[n - 1].lstrip()):
                n = next((m for m in range(n - 1, 0, -1) if not _blank(lines, m)
                          and _indent(lines[m - 1]) <= _indent(lines[n - 1])), 1)
            return n
    return None


def _lead_in(lines, head):
    """HEAD, moved up over the decorators and comments directly above it at its indent."""
    base = _indent(lines[head - 1])
    while head > 1 and not _blank(lines, head - 1) and _indent(lines[head - 2]) == base \
            and _LEAD_IN.match(lines[head - 2].lstrip()):
        head -= 1
    return head


def piece(lines, lo, hi):
    """The lines to print around changed lines LO..HI."""
    total = len(lines)
    first = next((n for n in range(lo, hi + 1) if not _blank(lines, n)), lo)
    end = _block_end(lines, first, hi)  # a change that opens a block: finish the block
    if end - lo + 1 <= BLOCK_LIMIT:
        hi = end
    grown = False
    while True:
        head = _header_above(lines, lo, hi)
        if head is None:
            break
        end = _block_end(lines, head, hi)
        start = _lead_in(lines, head)
        if end - start + 1 > BLOCK_LIMIT:
            break
        lo, hi, grown = start, end, True
    if not grown:  # a few lines around it, not past a blank line (that starts the next block)
        for _ in range(CONTEXT):
            if lo == 1 or _blank(lines, lo - 1):
                break
            lo -= 1
        for _ in range(CONTEXT):
            if hi == total or _blank(lines, hi + 1):
                break
            hi += 1
    while lo < hi and _blank(lines, lo):
        lo += 1
    while hi > lo and _blank(lines, hi):
        hi -= 1
    return lo, hi


def _headers(lines, lo):
    """The header lines of the blocks line LO is in, up to the top level."""
    found = []
    while True:
        head = _header_above(lines, lo, lo)
        if head is None:
            return found
        found.append(head)
        lo = head


def pieces(source, marked, removed):
    """Merged (start, end) ranges to print for these marks, or () for the whole file."""
    lines = source.expandtabs(8).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    total = len(lines)
    spans = [(a, min(b, total)) for a, b in marked if a <= total]
    spans += [(max(1, n), max(1, min(total, n + 1))) for n in removed]
    found = [piece(lines, a, b) for a, b in spans if total]
    if HEADERS:
        found += [(h, h) for lo, _ in found for h in _headers(lines, lo)]
    found.sort()
    merged = []
    for a, b in found:
        if merged and a <= merged[-1][1] + MERGE_GAP + 1:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    if not merged or sum(b - a + 1 for a, b in merged) >= WHOLE_SHARE * total:
        return ()
    return tuple(merged)


def changed_entries(root, rev, keep):
    """[(rel, ranges, marked, removed)] for --changed REV in git order, a legend for the
    contents page, and notes for what isn't printed. KEEP(rel, path) says whether a file may
    be printed (exclusions, binary files, the output file)."""
    marks, statuses, untracked = diff_marks(root, rev)
    entries, deleted, unchanged_renames = [], [], []
    for status, rel, old in statuses:
        if status == "D":
            deleted.append(rel)
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        if not keep(rel, path):  # first: binary files have no hunks, but get reported
            continue
        marked, removed = marks.get(rel, ([], []))
        if not marked and not removed:
            if status == "R":
                unchanged_renames.append(f"{old} → {rel}")
            continue  # only the mode changed, or a rename without edits
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.read()
        total = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
        marked = tuple((a, min(b, total)) for a, b in marked if a <= total)
        removed = tuple(sorted({min(n, total) for n in removed}))
        shown = pieces(source, marked, removed) or ((1, total),)  # () from pieces(): all of it
        entries.append((rel, shown, marked, removed))
    short = _git(root, "rev-parse", "--short", f"{rev}^{{commit}}").strip()
    count = sum(b - a + 1 for _, _, marked, _ in entries for a, b in marked)
    since = rev if rev.startswith(short) else f"{rev} ({short})"
    legend = (f"bars in the margin mark the {count:,} line{'s' if count != 1 else ''} changed "
              f"since {since}")
    notes = []
    for what, names in (("deleted file{s}", deleted), ("file{s} renamed without changes", unchanged_renames)):
        if names:
            shown = ", ".join(names[:3]) + (", …" if len(names) > 3 else "")
            notes.append(f"{len(names)} {what.format(s='s' if len(names) != 1 else '')}, not printed: {shown}")
    if untracked:
        shown = ", ".join(untracked[:3]) + (", …" if len(untracked) > 3 else "")
        notes.append(f"{len(untracked)} untracked file{'s' if len(untracked) != 1 else ''} not included "
                     f"(git add them, or list them with --files-from): {shown}")
    return entries, legend, notes
