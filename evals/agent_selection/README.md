# Agent-selection eval

Can a coding agent turn a plain-language request ("the backend without tests, but with the
JSON config") into the right PDF with code2pdf? This eval measures that, and is used to
improve the parts of code2pdf an agent learns from: `--help`, warnings and error messages.

The design follows [Automating eval design and hillclimbing](https://claude.dev/blog/automating-eval-design-and-hillclimbing/).

## Cases

Six sets, 62 cases in all (`--set fixtures|real|scale|judgement|excerpt|changes`, or several
separated by commas):

- **fixtures** (`cases.py`, `projects.py`): 27 requests over four small projects built fresh
  for every run: a Flask + React monorepo (`shop`), a SwiftUI app (`orbit`), a Python research
  repository (`ridge`) and a Go service (`relay`). Each is a git repository with one commit;
  some cases add a commit or uncommitted edits. This set **saturated**: Haiku, Sonnet and Opus
  all scored 99–100%, so it is a regression check, not something to climb.
- **real** (`real_cases.py`): 15 requests over real repositories at pinned tags: Gymnasium
  v1.0.0, Alamofire 5.9.1, gin v1.10.0, Express 4.21.0, Flask 3.0.3 (one case commits 3.0.2
  first and asks for the release diff). Tarballs are cached in `~/.cache/code2pdf-evals` and
  never executed. Expected files are computed from the tree by the rule the request states.
- **judgement** (`real_cases.JUDGEMENT_CASES`): 5 requests by topic ("the code that implements
  sessions"). A required set backed by the code plus `allowed` extras; anything else fails.
- **excerpt** (`real_cases.EXCERPT_CASES`): 5 requests for specific functions with real line
  numbers. Graded with `pdftotext`: each function's first and last line printed with its own
  number, forbidden neighbours absent, real paths as bookmarks.
- **changes** (`cases.CHANGE_CASES`, `real_cases.CHANGE_CASES`): 8 requests to review a commit,
  a release or uncommitted work with the changed lines marked (2 fixtures, 6 on Flask, Express
  and gin releases). Graded against the true `git diff`: every changed line printed with its
  number, the marked count close to the changed one, big files not printed whole. `check`
  also proves two decoys fail (no marks; every line marked).
- **pieces** (`pieces_eval.py`, no agents): `--changed`'s piece rules on real release diffs, by
  whether each changed line's block header and top-level definition are printed, and at what
  length. Train: Flask and gin releases; test: Express and Alamofire releases.
- **scale** (`real_cases.SCALE_CASES`): 2 whole-repository prints (Alamofire, ~7,700 pages in
  ~6 minutes; Gymnasium plus its `envs/`) that outlast an agent's 2-minute default command
  timeout. They run one at a time with code2pdf's normal parallelism.

- **Tasks mirror use.** They are the kinds of selection people ask for: one part of a
  project, no tests or generated code, extra config files, files changed in the last
  commit, files in a given order, or files that mention a name.
- **Every case says why it is hard** (`why_hard`) and where it comes from (`source`). The hard
  parts come from real failures, not from whatever today's model gets wrong:
  - JSON, plist, `.tf`, `go.mod` and notebooks are not default types;
  - hidden folders are skipped;
  - the default `build` and `env*` folder rules drop real source (`Scripts/build`, `src/ridge/envs`);
  - two folders share a name (`internal/legacy`, `lib/legacy`);
  - a vendored fork lives in a skipped folder;
  - the order isn't alphabetical;
  - the selection needs git.
- **Everything the grader checks is stated in the request**: which files, the order when one
  is asked for, where the PDF goes, and that the project must not change.

`run.py check` proves each case is sound:
- every expected file exists and is text;
- the case's reference solution passes;
- the grader gives the same verdict twice;
- the naive `code2pdf -a .` fails.

## Grader

Programmatic, no LLM judge. The PDF's bookmarks (one per file, labelled with its path) must
equal the expected files. The order counts when the request gives one. A `-a backend` style
folder prefix is allowed, and so is the project's own folder name (`gin/context.go` from
`code2pdf -s` run one level up). The PDF must be at the requested path, and the project must
be unchanged byte for byte (`.git` and Python bytecode caches aside). `report` re-grades
stored runs with the current grader, so grader fixes apply to old runs too.

## Subjects

Headless Claude Code (`claude -p`) with Bash/Read/Glob/Grep, `--setting-sources project`
(no user plugins or hooks), run in the project folder. The `--prompt plain` and `--skill`
arms also allow the Skill tool, and `--skill` loads the plugin with `--plugin-dir` (see
[Finding the tool](#finding-the-tool-the-skill)). The prompt is the request, plus
where to save the PDF and that nobody can answer questions. code2pdf is a fresh copy with
no eval files and nothing pointing back to this repository, so the answers are out of
reach. Runs with an API error or timeout are reported as infrastructure errors and kept
out of the score.

## Tools

`--tool code2pdf` (the default) or `--tool code2txt`. With code2txt the agent is asked for a
text file, graded from its contents list. Only the tool being measured is installed: with
both installed, agents let code2pdf pick the files for code2txt. Single-file cases, scale
cases and cases phrased "code2pdf's normal selection" don't apply to code2txt.

## Finding the tool (the skill)

The prompt normally says "Use code2pdf (it's installed)". `--prompt plain` leaves that out, as a
user who doesn't know code2pdf would; cases whose request names code2pdf are skipped.
`--skill` loads a copy of the plugin (`plugins/code2pdf`) with `--plugin-dir`, and both arms
may use the Skill tool. Reported per arm:

- **used the tool**: the share of runs that ran code2pdf at all;
- **skill**: the share that invoked the code2pdf skill;
- **right content**: the right code is in the PDF, however it was made. Agents without
  code2pdf print with `cupsfilter` or a script of their own, which has no bookmarks, so the
  main grade fails them. This check reads the PDF's text instead. A file counts as printed when
  most of its distinctive lines are in it: lines of 12–70 characters that occur in no other
  file. An extra file needs three such lines that occur nowhere else, not even inside other
  lines, because LICENSE text recurs in source headers. Excerpt cases use the line-number
  check. Order isn't checked. `check` confirms that every reference solution passes it. The
  naive `-a .` fails it in 26 of 27 fixtures; in relay-legacy its one extra file is too small
  to confirm.

## Running

```bash
.venv/bin/python evals/agent_selection/run.py check
.venv/bin/python evals/agent_selection/run.py run --label base-sonnet --model sonnet --repeats 3
.venv/bin/python evals/agent_selection/run.py run --label opus --model opus --effort high --split test
.venv/bin/python evals/agent_selection/run.py run --label v38 --ref v3.8      # an older release
.venv/bin/python evals/agent_selection/run.py run --label txt --tool code2txt
.venv/bin/python evals/agent_selection/run.py rerun-infra txt                  # re-judge flagged runs alone
.venv/bin/python evals/agent_selection/run.py run --label plain --prompt plain          # without naming the tool
.venv/bin/python evals/agent_selection/run.py run --label skill --prompt plain --skill  # ... with the skill
.venv/bin/python evals/agent_selection/run.py report base-sonnet opus
```

Scores come with 95% confidence intervals from a bootstrap over cases (the repeats of a case
move together). `results/LABEL/` holds `runs.jsonl` (every command the agent ran, its
answer, cost, verdict) and `report.html`; results are not committed.

## Hillclimbing

The surface is the text an agent reads: `--help`, warnings, errors. These are cheap to
change and revert, and a change in score traces back to them. CLI behaviour changes are
allowed when a failure shows a real gap, and they get unit tests like any other change.

- The split is frozen in `split.json` (made with seed 2026, stratified by project): 37 train
  cases, 25 test cases as of v3.12. New cases are added to one side explicitly, never
  reshuffled; `split.json`'s note says when each was added.
  Read train transcripts only.
- Each round makes one change aimed at a root cause, then runs train and test with 3 repeats.
  - Keep it if train goes up and test doesn't go down.
  - Revert it if test goes down, or if train goes up while test stays flat on a change made
    for a train case.
- Never paste case wording or file names into code2pdf's text. Examples in `--help` must be
  generic.
- When two or three rounds stall, sort every remaining failure by cause (agent error, unclear
  tool text, ambiguous case, grader bug) before changing anything.
