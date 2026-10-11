"""How well --changed's piece rules serve a reader, measured on real release diffs (no agents).

For each changed, non-blank line of source code:
- near: the header of the block the line is in (the nearest line above it with less indent,
  such as an `if` or a `def`) is printed, so the reader sees the line's immediate context;
- outer: the top-level header it belongs to (`def`, `func`, `class`, at no indent) is printed,
  so the reader knows which function or type changed. Lines at the top level count as covered.
And the cost: lines printed per changed line, and pages (~59 code lines each).

Diffs: train = Flask 3.0.2 -> 3.0.3 and gin v1.9.1 -> v1.10.0; test = Express 4.19.2 -> 4.20.0 and
Alamofire 5.8.1 -> 5.9.0. Tune on train, report test once.

    .venv/bin/python evals/agent_selection/pieces_eval.py [--limit 40] [--context 3] [--headers]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import changes  # noqa: E402
import real_cases  # noqa: E402

# (project at its pinned tag, the release before it). Test was first 4.20.0 -> 4.21.0 and
# 5.9.0 -> 5.9.1: only 5 changed source lines between them, too few to tell anything.
DIFFS = {"train": [("flask", "flask-3.0.2"), ("gin", "gin-v1.9.1")],
         "test": [("express-4.20.0", "express-4.19.2"), ("alamofire-5.9.0", "alamofire-5.8.1")]}
CODE = (".py", ".go", ".js", ".swift")
SKIP = ("docs/", "vendor/", "node_modules/", "Example/", "Tests/")  # generated docs, vendored code


def file_marks(root):
    """{rel: (marked, removed)} for source files changed by the last commit."""
    marks, _, _ = changes.diff_marks(root, "HEAD~1")
    return {rel: (tuple(m), tuple(r)) for rel, (m, r) in marks.items()
            if rel.endswith(CODE) and not rel.startswith(SKIP) and os.path.exists(os.path.join(root, rel))}


def chain(lines, n):
    """Header lines above line N, nearest first, up to the top level."""
    found, lo = [], n
    while True:
        head = changes._header_above(lines, lo, lo)
        if head is None:
            return found
        found.append(head)
        lo = head


def measure(root):
    near = outer = total = printed = 0
    for rel, (marked, removed) in file_marks(root).items():
        source = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
        lines = source.expandtabs(8).split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        shown_ranges = changes.pieces(source, marked, removed) or ((1, len(lines)),)
        shown = {n for a, b in shown_ranges for n in range(a, b + 1)}
        printed += len(shown)
        for a, b in marked:
            for n in range(a, min(b, len(lines)) + 1):
                if not lines[n - 1].strip():
                    continue
                total += 1
                heads = chain(lines, n)
                near += not heads or heads[0] in shown
                outer += not heads or heads[-1] in shown
    return {"lines": total, "near": near, "outer": outer, "printed": printed}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=changes.BLOCK_LIMIT)
    p.add_argument("--context", type=int, default=changes.CONTEXT)
    p.add_argument("--headers", action="store_true", help="also print the headers of the blocks a piece is in")
    p.add_argument("--split", default="train", choices=["train", "test"])
    args = p.parse_args()
    changes.BLOCK_LIMIT, changes.CONTEXT, changes.HEADERS = args.limit, args.context, args.headers
    sums = {"lines": 0, "near": 0, "outer": 0, "printed": 0}
    for name, previous in DIFFS[args.split]:
        root = os.path.join(tempfile.gettempdir(), f"c2p-pieces-{name}")
        if not os.path.isdir(os.path.join(root, ".git")):
            real_cases.build(name, root, {"previous": previous})
        m = measure(root)
        for k in sums:
            sums[k] += m[k]
        print(f"  {name:10} {m['lines']:5} changed lines  near {m['near'] / m['lines']:6.1%}  outer "
              f"{m['outer'] / m['lines']:6.1%}  printed {m['printed']:6} ({m['printed'] / m['lines']:.1f} per changed line)")
    print(f"{args.split}: limit {args.limit}, context {args.context}, headers {args.headers}: "
          f"near {sums['near'] / sums['lines']:.1%}, outer {sums['outer'] / sums['lines']:.1%}, "
          f"{sums['printed'] / sums['lines']:.1f} lines per changed line, ~{sums['printed'] / 59:.0f} pages")


if __name__ == "__main__":
    main()
