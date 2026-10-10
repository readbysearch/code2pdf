#!/usr/bin/env python3
"""Agent-selection eval: can a coding agent turn a plain-language request into the right PDF?

Each run builds a fresh fixture project in its own temporary folder, installs a copy of
code2pdf (no eval files, nothing pointing back to this repository), and asks a headless
Claude Code agent for the PDF. The grader is programmatic: the PDF's bookmarks (one per file,
labelled with its path) must equal the expected files, the PDF must be where the request
says, and the project must be unchanged.

  run.py check                              validate cases: files exist, references pass
  run.py run --label baseline [--model sonnet] [--effort high] [--repeats 3] [--split train]
  run.py report LABEL [LABEL...]            scores with 95% CIs, per case; writes report.html

Results go to results/LABEL/ (runs.jsonl, transcripts/); results/ is not committed.
Run with the repository's .venv python (the grader reads PDFs with pypdf).
"""

import argparse
import concurrent.futures
import datetime
import html
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import projects  # noqa: E402
import real_cases  # noqa: E402
from cases import CASES as FIXTURE_CASES  # noqa: E402

for _case in FIXTURE_CASES:
    _case["set"] = "fixtures"
for _case in real_cases.REAL_CASES:
    _case["set"] = "real"
CASES = FIXTURE_CASES + real_cases.REAL_CASES
BY_ID = {case["id"]: case for case in CASES}

RESULTS = os.path.join(HERE, "results")
SPLIT_SEED = 2026
TEST_FRACTION = 0.4
TIMEOUT = 600
PROMPT = """{request}

Use code2pdf (it's installed) and save the PDF as {output}. I'm not around to answer questions, \
so don't ask; just get it right. Don't change or add anything inside the project."""


# --- split -------------------------------------------------------------------------------

def split():
    """Fixed random train/test split, stratified by project so both sets cover every layout."""
    rng = random.Random(SPLIT_SEED)
    train, test = [], []
    for name in sorted({c["project"] for c in CASES}):
        ids = sorted(c["id"] for c in CASES if c["project"] == name)
        rng.shuffle(ids)
        n_test = round(len(ids) * TEST_FRACTION)
        test += ids[:n_test]
        train += ids[n_test:]
    return sorted(train), sorted(test)


def select(which, case_set="all"):
    train, test = split()
    ids = {"train": train, "test": test, "all": [c["id"] for c in CASES]}.get(which)
    if ids is None:
        return which.split(",")
    return [i for i in ids if case_set == "all" or BY_ID[i]["set"] == case_set]


# --- install a clean copy of code2pdf -----------------------------------------------------

def install_copy(dest):
    """bin/, scripts/, fonts/ and a copy of .venv, with nothing that names this repository."""
    os.makedirs(dest)
    for name in ("bin", "scripts", "fonts"):
        shutil.copytree(os.path.join(REPO, name), os.path.join(dest, name),
                        ignore=shutil.ignore_patterns("__pycache__"))
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    with open(os.path.join(dest, "VERSION"), "w") as f:
        f.write(f"v3.9-eval-g{commit}|{commit}|{datetime.date.today().isoformat()}\n")
    venv = os.path.join(dest, "venv")
    shutil.copytree(os.path.join(REPO, ".venv"), venv, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "activate*", "Activate*"))
    cfg = os.path.join(venv, "pyvenv.cfg")
    with open(cfg) as f:
        lines = [line for line in f if not line.startswith("command")]
    with open(cfg, "w") as f:
        f.writelines(lines)
    # Console scripts carry a #! line with the original venv path; the agent needs none of them
    for name in os.listdir(os.path.join(venv, "bin")):
        if not name.startswith("python"):
            os.remove(os.path.join(venv, "bin", name))
    leak = subprocess.run(["grep", "-rIl", REPO, dest], capture_output=True, text=True).stdout.strip()
    if leak:
        raise SystemExit(f"install copy still names {REPO}:\n{leak}")
    return os.path.join(dest, "bin")


def subject_env(bin_dir):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CODE2PDF_", "CLAUDE", "VIRTUAL_ENV"))}
    env["PATH"] = bin_dir + os.pathsep + "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    env["CODE2PDF_JOBS"] = "1"  # several runs render at once; keep each to ~1.3 GB
    return env


# --- grading -----------------------------------------------------------------------------

def pdf_files(path):
    """File paths in the PDF, in order, from its bookmarks."""
    import pypdf
    reader = pypdf.PdfReader(path)
    titles = []

    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                titles.append(item.title)
    walk(reader.outline)
    return titles


def add_converted_folder(got, expected):
    """Bookmarks are relative to the folder given to -a (`-a backend` labels backend/app.py as
    app.py). Put back the one folder prefix that makes the most labels match."""
    if not got:
        return got
    prefixes = {""}
    for label in got:
        for path in expected:
            if path.endswith("/" + label):
                prefixes.add(path[:-len(label)])
    expected_set = set(expected)
    best = max(sorted(prefixes), key=lambda p: sum(p + g in expected_set for g in got))
    return [best + g for g in got]


def grade(case, output, before, after):
    result = {"pdf": os.path.exists(output), "missing": [], "extra": [], "order_ok": None,
              "project_changed": sorted(set(before) ^ set(after)
                                        | {p for p in before if p in after and before[p] != after[p]})}
    if result["pdf"]:
        try:
            got = pdf_files(output)
        except Exception as e:  # not a PDF, or no bookmarks
            got, result["pdf_error"] = [], str(e)
        expected = list(case["expected"])
        if case.get("match") == "basename":
            got = [os.path.basename(g) for g in got]
        else:
            got = add_converted_folder(got, expected)
        result["got"] = got
        result["missing"] = sorted(set(expected) - set(got))
        result["extra"] = sorted(set(got) - set(expected))
        duplicates = len(got) != len(set(got))
        result["order_ok"] = got == expected if case.get("ordered") else None
        result["files_ok"] = not result["missing"] and not result["extra"] and not duplicates
    else:
        result["files_ok"] = False
    result["pass"] = bool(result["pdf"] and result["files_ok"] and result["order_ok"] is not False
                          and not result["project_changed"])
    return result


# --- one run -------------------------------------------------------------------------------

def prepare(case, workdir):
    """Build the project; returns (project, output as given to the agent, output path, case with
    its expected files resolved)."""
    project = os.path.join(workdir, case["project"])
    if case["project"] in projects.PROJECTS:
        projects.build(case["project"], project, case.get("setup"))
    else:
        real_cases.build(case["project"], project, case.get("setup"))
    if callable(case["expected"]):
        case = dict(case, expected=case["expected"](project))
    output_rel = f"../out/{case['id']}.pdf"
    return project, output_rel, os.path.normpath(os.path.join(project, output_rel)), case


def run_one(case, rep, args, bin_dir, transcripts):
    workdir = tempfile.mkdtemp(prefix="c2p-eval-")
    try:
        project, output_rel, output, case = prepare(case, workdir)
        before = projects.snapshot(project)
        prompt = PROMPT.format(request=case["request"], output=output_rel)
        cmd = ["claude", "-p", prompt, "--model", args.model, "--setting-sources", "project",
               "--permission-mode", "dontAsk", "--allowedTools", "Bash", "Read", "Glob", "Grep",
               "--output-format", "stream-json", "--verbose", "--no-session-persistence",
               "--max-budget-usd", str(args.max_budget)]
        if args.effort:
            cmd += ["--effort", args.effort]
        started = time.time()
        infra = None
        try:
            env = subject_env(bin_dir)
            env["TMPDIR"] = os.path.join(workdir, "tmp")  # mktemp stays private to this run
            os.makedirs(env["TMPDIR"])
            proc = subprocess.run(cmd, cwd=project, env=env, capture_output=True,
                                  text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
            stream, code = proc.stdout, proc.returncode
            if code != 0:
                infra = f"claude exited {code}: {proc.stderr.strip()[-300:]}"
        except subprocess.TimeoutExpired as e:
            stream = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            infra = f"timeout after {TIMEOUT}s"
        elapsed = time.time() - started
        with open(os.path.join(transcripts, f"{case['id']}-{rep}.jsonl"), "w") as f:
            f.write(stream)
        stats = transcript_stats(stream)
        if stats.get("api_error"):
            infra = infra or stats["api_error"]
        result = grade(case, output, before, projects.snapshot(project))
        # Runs share the machine's /tmp: a fixed name like /tmp/files.txt can be overwritten
        # by a concurrent run, which is the eval's fault, not the agent's
        if not result["pass"] and not infra and any(re.search(r"(?<![\w.])/tmp/[\w.-]+", c)
                                                    for c in stats["commands"]):
            infra = "suspected collision: used a fixed /tmp file while other runs were going"
        return {"case": case["id"], "rep": rep, "model": args.model, "effort": args.effort,
                "seconds": round(elapsed, 1), "infra_error": infra, **stats, **result}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def transcript_stats(stream):
    commands, final, cost, turns, api_error = [], None, None, None, None
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    commands.append(block.get("input", {}).get("command", ""))
        elif event.get("type") == "result":
            final, cost, turns = event.get("result"), event.get("total_cost_usd"), event.get("num_turns")
            if event.get("is_error") and event.get("subtype") != "success":
                api_error = f"result {event.get('subtype')}: {str(final)[:200]}"
    code2pdf = [c for c in commands if "code2pdf" in c]
    return {"commands": commands, "final": final, "cost_usd": cost, "turns": turns,
            "code2pdf_calls": len(code2pdf), "used_list_files": any("--list-files" in c for c in code2pdf),
            "read_help": any("--help" in c or " -h" in c for c in code2pdf), "api_error": api_error}


def cmd_run(args):
    ids = select(args.split, args.set)
    out_dir = os.path.join(RESULTS, args.label)
    transcripts = os.path.join(out_dir, "transcripts")
    os.makedirs(transcripts, exist_ok=True)
    install = tempfile.mkdtemp(prefix="c2p-install-")
    bin_dir = install_copy(os.path.join(install, "code2pdf"))
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump({"label": args.label, "model": args.model, "effort": args.effort, "repeats": args.repeats,
                   "cases": ids, "split": args.split, "started": datetime.datetime.now().isoformat(),
                   "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                                            capture_output=True, text=True).stdout.strip(),
                   "dirty": bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain", "bin", "scripts"],
                                                capture_output=True, text=True).stdout.strip())}, f, indent=1)
    jobs = [(BY_ID[i], rep) for rep in range(args.repeats) for i in ids]
    print(f"{args.label}: {len(ids)} cases x {args.repeats} repeats = {len(jobs)} runs, "
          f"model {args.model}{' effort ' + args.effort if args.effort else ''}, {args.jobs} at a time")
    lock = threading.Lock()
    done = 0
    with open(os.path.join(out_dir, "runs.jsonl"), "a") as log, \
            concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        futures = [pool.submit(run_one, case, rep, args, bin_dir, transcripts) for case, rep in jobs]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            with lock:
                done += 1
                log.write(json.dumps(record) + "\n")
                log.flush()
                mark = "PASS" if record["pass"] else ("INFRA" if record["infra_error"] else "fail")
                detail = "" if record["pass"] else describe_failure(record)
                print(f"[{done}/{len(jobs)}] {mark:5} {record['case']}#{record['rep']} "
                      f"{record['seconds']}s ${record['cost_usd'] or 0:.3f} {detail}", flush=True)
    shutil.rmtree(install, ignore_errors=True)
    report([args.label])


def describe_failure(r):
    parts = []
    if r.get("infra_error"):
        parts.append(r["infra_error"][:120])
    if not r["pdf"]:
        parts.append("no PDF at the requested path")
    if r["missing"]:
        parts.append("missing " + ",".join(r["missing"][:4]) + ("…" if len(r["missing"]) > 4 else ""))
    if r["extra"]:
        parts.append("extra " + ",".join(r["extra"][:4]) + ("…" if len(r["extra"]) > 4 else ""))
    if r["order_ok"] is False:
        parts.append("wrong order")
    if r["project_changed"]:
        parts.append("changed project: " + ",".join(r["project_changed"][:3]))
    return "; ".join(parts)


# --- check -------------------------------------------------------------------------------

def cmd_check(args):
    """Every expected file exists and is text; every reference solution passes the grader;
    the grader gives the same verdict twice."""
    install = tempfile.mkdtemp(prefix="c2p-install-")
    bin_dir = install_copy(os.path.join(install, "code2pdf"))
    env = subject_env(bin_dir)
    env["CODE2PDF_QUIET"] = "1"
    train, test = split()
    print(f"split (seed {SPLIT_SEED}): {len(train)} train, {len(test)} test")
    print("  test:", ", ".join(test))
    bad = 0
    for case in CASES:
        if args.cases and case["id"] not in args.cases.split(","):
            continue
        if args.set != "all" and case["set"] != args.set:
            continue
        workdir = tempfile.mkdtemp(prefix="c2p-check-")
        try:
            project, output_rel, output, case = prepare(case, workdir)
            problems = []
            if case.get("match") != "basename":
                for rel in case["expected"]:
                    path = os.path.join(project, rel)
                    if not os.path.isfile(path):
                        problems.append(f"expected file missing: {rel}")
                    elif b"\0" in open(path, "rb").read(8192):
                        problems.append(f"expected file is binary: {rel}")
            before = projects.snapshot(project)
            ref = case["reference"].replace("{out}", f"'{output_rel}'")
            proc = subprocess.run(["bash", "-c", ref], cwd=project, env=env, capture_output=True, text=True)
            first = grade(case, output, before, projects.snapshot(project))
            second = grade(case, output, before, projects.snapshot(project))
            if first != second:
                problems.append("grader verdict changed between two runs")
            if not first["pass"]:
                problems.append(f"reference fails: {describe_failure(first)} {proc.stderr.strip()[-200:]}")
            # A naive answer (`code2pdf -a .`) must fail, or the case tests nothing; its file
            # list decides that without rendering a whole repository
            naive = subprocess.run(["code2pdf", "-a", ".", "--list-files"], cwd=project, env=env,
                                   capture_output=True, text=True).stdout.split("\n")
            naive = [line for line in naive if line]
            if (naive == case["expected"] if case.get("ordered") else sorted(naive) == sorted(case["expected"])):
                problems.append("the naive `code2pdf -a .` passes")
            status = "ok " if not problems else "BAD"
            bad += bool(problems)
            print(f"{status} {case['id']:22} {len(case['expected']):3} files"
                  + "".join(f"\n      {p}" for p in problems))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    shutil.rmtree(install, ignore_errors=True)
    return 1 if bad else 0


# --- report ------------------------------------------------------------------------------

def load(label):
    with open(os.path.join(RESULTS, label, "runs.jsonl")) as f:
        return [json.loads(line) for line in f if line.strip()]


def bootstrap_ci(runs, n=4000, seed=1):
    """95% CI of the pass rate, resampling cases (clusters of repeats) with replacement."""
    by_case = {}
    for r in runs:
        by_case.setdefault(r["case"], []).append(1.0 if r["pass"] else 0.0)
    cases = list(by_case.values())
    if not cases:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        sample = [rng.choice(cases) for _ in cases]
        means.append(sum(sum(c) for c in sample) / sum(len(c) for c in sample))
    means.sort()
    point = sum(sum(c) for c in cases) / sum(len(c) for c in cases)
    return point, means[int(0.025 * n)], means[int(0.975 * n)]


def summarize(runs):
    graded = [r for r in runs if not r["infra_error"]]
    point, lo, hi = bootstrap_ci(graded)
    costs = [r["cost_usd"] for r in graded if r["cost_usd"] is not None]
    secs = [r["seconds"] for r in graded]
    return {"runs": len(runs), "infra": len(runs) - len(graded), "pass": point, "lo": lo, "hi": hi,
            "cost": statistics.mean(costs) if costs else 0, "seconds": statistics.median(secs) if secs else 0,
            "list_files": statistics.mean([r["used_list_files"] for r in graded]) if graded else 0}


def report(labels):
    train, test = split()
    rows, per_case = [], {}
    for label in labels:
        runs = load(label)
        line = {"label": label}
        for name, ids in (("all", None), ("train", train), ("test", test)):
            subset = [r for r in runs if ids is None or r["case"] in ids]
            if subset:
                line[name] = summarize(subset)
        rows.append(line)
        for r in runs:
            per_case.setdefault(r["case"], {}).setdefault(label, []).append(r)
    for line in rows:
        parts = []
        for name in ("all", "train", "test"):
            if name in line:
                s = line[name]
                parts.append(f"{name} {s['pass']:.0%} [{s['lo']:.0%}, {s['hi']:.0%}] (n={s['runs'] - s['infra']})")
        s = line.get("all") or {}
        print(f"{line['label']:28} " + "  ".join(parts)
              + f"  ${s.get('cost', 0):.3f}/run, {s.get('seconds', 0):.0f}s median, "
                f"--list-files {s.get('list_files', 0):.0%}, infra errors {s.get('infra', 0)}")
    print()
    print(f"{'case':24}" + "".join(f"{lab[:14]:>16}" for lab in labels))
    for case in CASES:
        cid = case["id"]
        if cid not in per_case:
            continue
        cells = []
        for label in labels:
            runs = per_case[cid].get(label, [])
            cells.append(f"{sum(r['pass'] for r in runs)}/{len(runs)}" if runs else "-")
        print(f"{cid + (' (test)' if cid in test else ''):24}" + "".join(f"{c:>16}" for c in cells))
    write_html(labels, rows, per_case, test)


def write_html(labels, rows, per_case, test):
    out = os.path.join(RESULTS, labels[-1], "report.html")
    esc = html.escape
    parts = ["<!doctype html><meta charset=utf-8><title>code2pdf agent-selection eval</title>",
             "<style>body{font:14px/1.45 -apple-system,sans-serif;margin:2em;max-width:1100px}"
             "table{border-collapse:collapse}td,th{padding:3px 8px;border-bottom:1px solid #ddd;text-align:left}"
             ".p{color:#1a7f37}.f{color:#cf222e}details{margin:2px 0}pre{white-space:pre-wrap;"
             "background:#f6f8fa;padding:6px;font-size:12px}</style>",
             "<h1>code2pdf agent-selection eval</h1><table><tr><th>run</th><th>all</th><th>train</th><th>test</th>"
             "<th>$/run</th><th>median s</th></tr>"]
    for line in rows:
        cells = []
        for name in ("all", "train", "test"):
            s = line.get(name)
            cells.append(f"{s['pass']:.0%} [{s['lo']:.0%}–{s['hi']:.0%}]" if s else "")
        s = line.get("all", {})
        parts.append(f"<tr><td>{esc(line['label'])}</td>" + "".join(f"<td>{c}</td>" for c in cells)
                     + f"<td>{s.get('cost', 0):.3f}</td><td>{s.get('seconds', 0):.0f}</td></tr>")
    parts.append("</table><h2>Cases</h2>")
    for case in CASES:
        cid = case["id"]
        if cid not in per_case:
            continue
        parts.append(f"<h3>{esc(cid)}{' (test)' if cid in test else ''}</h3><p>{esc(case['request'])}<br>"
                     f"<i>Why hard:</i> {esc(case['why_hard'])}</p>")
        for label in labels:
            for r in sorted(per_case[cid].get(label, []), key=lambda r: r["rep"]):
                cls = "p" if r["pass"] else "f"
                summary = "pass" if r["pass"] else esc(describe_failure(r))
                parts.append(f"<details><summary class={cls}>{esc(label)} #{r['rep']}: {summary}</summary><pre>"
                             + esc("\n".join(r["commands"])) + "\n\n" + esc(str(r.get("final"))) + "</pre></details>")
    with open(out, "w") as f:
        f.write("\n".join(parts))
    print(f"\nreport: {out}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check")
    p.add_argument("--cases", default="")
    p.add_argument("--set", default="all")
    p = sub.add_parser("run")
    p.add_argument("--label", required=True)
    p.add_argument("--model", default="sonnet")
    p.add_argument("--effort", default=None)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--split", default="all", help="train, test, all, or comma-separated case ids")
    p.add_argument("--set", default="all", help="fixtures, real or all")
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--max-budget", type=float, default=1.0)
    p = sub.add_parser("report")
    p.add_argument("labels", nargs="+")
    args = parser.parse_args()
    if args.command == "check":
        return cmd_check(args)
    if args.command == "run":
        return cmd_run(args)
    report(args.labels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
