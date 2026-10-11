# Results, 2026-10-10

What the agent-selection eval found on code2pdf 3.9 (commit 1b5e0c3 and later). The method is
in [README.md](README.md). Scores are pass rates with 95% bootstrap confidence intervals over
cases; n is the number of runs.

## Scores

| Set | Haiku | Sonnet | Opus (high effort) |
|-----|-------|--------|--------------------|
| fixtures (27 cases) | 99% [96–100], n=81 | 99% [96–100], n=81 | 100%, n=54 |
| real repositories (15 cases) | 100%, n=45 | 100%, n=45 | 100%, n=30 |
| scale, renders of 1–6 minutes (2 cases) | 6/6, plus 3/3 on the reworded case | 6/6 | – |
| cost per run | $0.004 | $0.063 | $0.15 |

**The same 42 cases with code2pdf 3.8, Sonnet: 57% [43–71], n=84.**

## What this means

1. **Choosing files is easy for agents with 3.9, even for Haiku.** The eval saturates: all three
   models sit at 99–100%, so it can't rank models or guide quality improvements. Its use now is
   as a regression check.
2. **The eval can tell a weaker tool from a stronger one.** On identical cases and agent, 3.8
   scores 57% and 3.9 scores 99%. Under 3.8, agents copied files into a temporary folder to get
   a custom selection, so the PDF showed the wrong paths. They also couldn't name a hidden or
   skipped folder, or set an order.
3. **Agents mostly bypass the selection rules.** In 60–85% of runs, the final command is
   `find …` or `git …` piped into `code2pdf --files-from -`. Agents check the default selection
   against `find` (Haiku spotted the 71 Gymnasium `envs/` files the `env*` rule drops) and then
   pass the exact list. `--files-from` is the feature that makes the difference.
4. **Agents anticipate long renders.** In every scale run, Haiku and Sonnet set a 10-minute
   command timeout before converting (the default is 2 minutes). The longest render, Alamofire
   at 7,697 pages, took about 6 minutes.

## Topic requests ("the code that handles sessions")

Five judgement cases ask by topic: Flask sessions, gin middleware, gin JSON rendering, Express
routing, Alamofire retries. They are still graded programmatically. Each has a required set
backed by the code (Flask opens the session in `ctx.py` and saves it in `app.py`) and a set of
acceptable extras; anything else fails.

| | Haiku | Sonnet | Opus (high effort) |
|---|---|---|---|
| first wording | 40% | 40% | 80% |
| reworded, "whole files, as they are" | 87% | 87% | 100% |
| after fixing two gaps in the acceptable sets | **100%** | **100%** | **100%** |

None of the failures were the agents' fault:
- **Excerpts.** Asked for "the gin.Context methods that use them", Haiku and Sonnet cut the
  methods into new files with made-up names (`context_json.go`, `02_ctx_request_context.py`).
  That is a reasonable reading, so the requests now say "whole files".
- **Acceptable sets too narrow.** Opus included `ginS/gins.go`, whose `ginS.Use` also registers
  middleware. Haiku included `DataRequest`/`DownloadRequest`/`UploadRequest`, which do ask the
  Session for a retry. Both were right, and both are now acceptable.
- **`__pycache__`.** Agents that imported Flask to inspect it wrote `__pycache__/*.pyc` into the
  project. That is gitignored and harmless, so the grader now ignores bytecode caches (and only
  those).

**Product finding:** people and agents want to print *part* of a file. With no way to do it,
13 of the 40 first-wording runs made excerpt files, which loses the real path and the real
line numbers. That led to `path:START-END` (below).

## Printing part of a file (`path:START-END`)

Five excerpt cases ask for specific functions "each whole, with the file's real line numbers"
(gin's Context JSON methods, Flask's RequestContext.push and process_response, Express's
handle and dispatch, Alamofire's retry decision, CartPole's step and reset). The grader
requires the real paths as bookmarks, each function's first and last line printed with its
own number (the last line is found from indentation and braces), and that neighbouring lines
named as forbidden are absent. 3 repeats each.

| | v3.10.1 (no ranges) | with `path:START-END` | plus the cut-off warning |
|---|---|---|---|
| Haiku | 13% [0–40] | **100%**, n=15 | **100%**, n=30 |
| Sonnet | 47% [20–67], $0.19/run, 42 s | 80% [53–100], n=15, $0.08/run, 14 s | **100%**, n=30, $0.08/run, 13 s |
| held-out test (both models) | 0–50% | 100% | 100% |

Without ranges, agents copied functions into new files (`src/context.go`,
`/tmp/c2p-work/src/Session.swift`), so the PDF showed made-up paths and line numbers starting
at 1.

With ranges, Sonnet's three failures were its own: it estimated where a function ends and
stopped a few lines short (`ctx.py:367-391` for a method ending at 394, `app.py:1260-1281`
for one ending at 1286, which left out its `save_session` call). code2pdf now warns about such
a range, judging only by indentation: `Warning: src/flask/app.py:1260-1281 stops inside a
block that goes on to line 1286; to print it whole, use src/flask/app.py:1260-1286`. The
warning comes before converting and again after `Done:`, because agents often keep only the
tail of the output.
- In the 30 Sonnet runs it fired in 3, all on short Flask ranges (`1260-1284`, `367-390`,
  ...). Each time Sonnet re-ran with the suggested range and passed. It never fired on a
  correct range.
- Over the 8,400 functions in the five repositories, it flags 20,195 of 20,205 ranges cut 1,
  2 or 5 lines short and none of the exact ranges. The 10 misses end in a multi-line string at
  column 0.

The re-run also found a bug. Haiku sometimes runs `code2pdf -s $PWD/context.go:975-1018`, and
`-s` labelled the file with the whole absolute path (`/private/var/folders/.../context.go`) in
the header and bookmark. A file inside the current folder is now labelled by its path there.
The grader accepts the project's own folder as a prefix (`gin/context.go`, from `-s` run one
level up), as it does for `-a backend`. That run at the earlier commit scores 87% (n=15) and
is kept as it was.

The Haiku regression pass over all 54 cases after these changes scores 96% [91–100] (n=54).
Its two failures are agent errors that don't involve ranges: it added
`.github/dependabot.yml` to "the CI workflow", and it saved one PDF inside the project.

Eval fixes in this round:
- The usage limit cut runs short ("You've hit your session limit"); they were re-run with
  `rerun-infra`.
- The grader rejected a file listed twice with two ranges, which is a valid way to do it.

## The skill: do agents find code2pdf when the request doesn't name it?

Every other set says "Use code2pdf (it's installed)". Real users say "make me a PDF of the
backend". `--prompt plain` drops that sentence, and `--skill` loads the code2pdf plugin
(`plugins/code2pdf`). That gives 47 cases (the five that name code2pdf and the two scale
cases left out), 1 run each. code2pdf is on the agent's PATH in both arms.

| | Haiku, no skill | Haiku, skill | Sonnet, no skill | Sonnet, skill |
|---|---|---|---|---|
| ran code2pdf | 0% | 98% | 0% | 100% |
| main grade (bookmarks name the right files) | 0% | **98%** [94–100] | 26% [13–38] | **100%** |
| right content in the PDF, however it was made | 87% | 98% | 91% | 100% |
| cost per run, median time | $0.010, 30 s | $0.005, 15 s | $0.090, 18 s | $0.078, 13 s |

- **Without the skill, no agent ever found code2pdf.** They made PDFs themselves:
  - a reportlab script (Haiku 27 runs, Sonnet 34);
  - macOS `cupsfilter` (6 and 10);
  - PDF bytes written by hand (Haiku 7).

  Most got the right code in (87–91%), but the results are plain text pages. Going by the
  scripts, a rough count: 28–33 runs per model added line numbers, 0–13 added bookmarks, and
  few had syntax highlighting or a contents page. The 12 Sonnet runs that pass the main grade
  wrote reportlab bookmarks named after the paths.
- **With the skill, agents use code2pdf and do better on every measure.** They pass the main
  grade 98–100%, at half the cost and time for Haiku and 13% less cost for Sonnet. The skill's
  description alone is enough sometimes. One Sonnet run ran `which code2pdf` and used it
  without opening the skill.
- **The one failure is a judgement call.** For "the tutorial (the .rst files in
  docs/tutorial) in reading order", Haiku rendered the tutorial as a formatted document, which
  the skill says it isn't for, so it didn't use the skill.
- **No regression when the request does name code2pdf.** The standard prompt with the skill
  installed scores 100% (n=52, Haiku), against 96% without it in the same week.

The content check is new for this comparison. It accepts every reference solution and rejects
the naive `-a .` in 26 of 27 fixtures (see README). Re-grading the stored runs with the changed
grader left every earlier score as it was.

## Printing what changed (`--changed REV`, marks, `--summary`), code2pdf 3.12

### Cases and grader

The "changes" set has 8 cases. Two are small fixtures (review the last commit, review
uncommitted work). Six use real repositories at pinned tags:

- Flask 3.0.3 release: the Python code; only `app.py` and `blueprints.py`; the release while
  an uncommitted edit sits in the working tree.
- Express 4.21.0 release: one changed line in a 1,179-line file.
- Express 4.20.0 release (added later and held out).
- gin: uncommitted work, without the tests.

The grader works from the true `git diff`. For each expected file:
1. the bookmark names it;
2. every changed line is printed with its own line number;
3. the marked-line count lies between the non-blank changed lines and the changed lines plus
   max(2, 25%);
4. a file over 150 lines with a small change isn't printed whole.

`check` proves that every reference solution passes and that the naive `-a .` fails. It also
proves that two decoys fail: the right files whole without marks, and every line marked.

### Results

| | n | pass |
|---|---|---|
| code2pdf **3.11** (ablation), Sonnet | 14 | **0%** |
| Haiku, tool not named in the prompt, **no skill** | 14 | **0%** (reportlab scripts, 49 s median) |
| Haiku | 21 → 24 | 100% → 100% |
| Sonnet | 21 → 24 | 100% → 100% |
| Opus (high effort) | 7 | 100% |
| Haiku, tool not named, with the skill | 21 → 24 | 95% → 100% |
| Haiku regression pass, all other sets (52 cases) | 52 | 100% (96% before) |

The arrows go from round 1 to round 2. With 3.11, agents printed `git diff -U9999` output as if
it were a source file, or copied files to staging folders: wrong paths, no marks. 34 of 72
round-2 runs piped `--changed --list-files` through `grep` into `--files-from`. Both layers get
used together.

### Round 1: what changed and why

- **A mark alone now prints only its lines.** The one round-1 failure was Haiku (with the
  skill) writing `src/flask/app.py:+244-253` and getting whole files, under the first rule
  ("with only marks, the whole file is printed"). Sonnet had written the same kind of list in
  a training case, where it passed only because the file was small. The rule is now "every
  range is printed, and a `+` range is also marked", like `app.py:244-253`. The whole file with
  marks is `app.py:1-,+244-253`.

  The failing run was a test case, which the method says not to read. The same pattern in a
  training case is the basis for the change, and a new held-out case was added after it.
  Round 2 has no marks-only list, so the score doesn't show whether the fix helped; the reason
  for it is consistency.
- **Header lines.** `pieces_eval.py` measures the piece rules on real release diffs, with no
  agents. For each changed line, it checks whether the line that opens its block (`near`) and
  its top-level `def`/`func`/`class` (`outer`) are printed. Train: Flask 3.0.2 → 3.0.3, gin
  v1.9.1 → v1.10.0. Test: Express 4.19.2 → 4.20.0, Alamofire 5.8.1 → 5.9.0.

  | rule | train near / outer | test near / outer | lines per changed line (train, test) |
  |---|---|---|---|
  | block ≤ 40, 3 lines of context | 96.3% / 89.0% | 98.3% / 93.8% | 2.3, 1.5 |
  | the same, plus header lines | **100% / 100%** | **100% / 100%** | 2.4, 1.5 |

  Block limits of 20, 60 and 80, and 1 or 5 lines of context, only traded context for length.
  Header lines got full context for about 1 page in 35. Express gained most: its code sits in
  large top-level blocks, and only 49% of its changed lines showed their function before.

  Two notes on this measure. First, 100% is guaranteed by construction once header lines are
  printed; what it shows is that the cost is small. Second, looking at a page found a flaw in
  it: the "header" of a change in Flask's `__init__` was `):`, the end of a multi-line
  signature, and it still counted as context. The header finder now climbs to the line that
  opened the statement, and the numbers above are with that fix.

  The first test diffs (Express 4.21.0, Alamofire 5.9.1) had only 5 changed source lines
  between them, so they were replaced before any tuning on them.

### `--summary`

No request asked for it, and all 70 round-1 runs on the current code passed one. 70 named the
revision or scope ("Flask 3.0.3 release commit (86bf4d5, diffed against 3.0.2 / 6ab73fe)"), and
60 said what was left out ("Excludes the uncommitted edit to src/flask/helpers.py"). This is
measured, not graded.

### What this eval doesn't cover

The change cases saturated again on the current code (100% for every model), so the agent
eval can't rank the piece rules; `pieces_eval.py` does that. The marks are checked by count,
not by position (a PDF's text doesn't show the bars).

## Hillclimbing code2txt

code2txt was the part of the solution without the 3.9 options, so it had room to climb. It was
measured alone: only code2txt was installed, on the 36 cases that apply to it, 2 repeats each.

| code2txt | all | train | test | $/run | median time |
|---|---|---|---|---|---|
| Haiku, before | 92% [83–97] | 95% | 86% | 0.005 | 14 s |
| Haiku, with `--files-from` | **100%** | 100% | **100%** | 0.004 | 11 s |
| Sonnet, before | 97% [93–100] | 98% | 96% | 0.075 | 13 s |
| Sonnet, with `--files-from` | **100%** | 100% | **100%** | **0.064** | 10 s |

Every failure before the change was a case that needs a given order or an exact list
(relay-order, flask-tutorial-order, express-lib-router, the Flask release diff). The
workarounds failed in recognisable ways: files copied into staging folders, renamed to
`01-index.rst` to force an order, or a contents list written by hand. Train and test both went
up, so the change was kept (commit "code2txt --files-from"). A second round has no headroom
left.

The reflection step found that five cases phrased "code2pdf's normal selection" can't be
answered with code2txt alone. In every such run the agent used code2txt's own defaults, which
differ (they include `.tf`, `go.mod` and other types). Those cases are left out for code2txt in
both arms.

## Bugs found and fixed

In code2pdf:
- **A killed conversion left processes and temp files behind.** Agents run commands under
  timeouts.
  - A SIGTERM sent to `code2pdf` left Python and its parts workers running, because the
    launcher didn't `exec`.
  - A SIGTERM sent to the process group left `.code2pdf-*.pdf` and `.code2pdf-parts-*` in the
    output folder.
  - Ctrl-C waited for every running part to finish.

  The fix is in d68c582, with `tests/test_interrupt.py`.
- **A folder `--include` printed one line per skipped binary**: 80 lines for Gymnasium's
  `envs/`. It now prints one summary line.

In the eval itself (each would have produced wrong scores):
- The grader rejected `-a backend` runs, whose bookmarks are relative to `backend/`. It now
  allows the converted folder as a prefix.
- Runs at the same time shared `/tmp`, so a fixed name like `/tmp/files.txt` was overwritten
  by another case. Each run now gets its own `TMPDIR`.
- My first fix flagged every failing run that used `/tmp` as an infrastructure error. That hid
  10 genuine 3.8 failures out of 12 flagged. Flagged runs are now re-run one at a time
  (`rerun-infra`) and judged on that run.
- One reference solution, `--include-types py --include envs`, was wrong: a folder include
  takes every type, so it also pulled in 30 MuJoCo XML files. The correct form is
  `--include 'envs/**/*.py'`. An agent could make the same mistake, which makes the case
  harder.
- The wording "generated docs included" was ambiguous: one Haiku run reasonably added the docs'
  SVG and JSON files. The case was reworded.
- Adding cases reshuffled the seeded train/test split. The split is now frozen in `split.json`.
- **The tools leaked into each other's evals.** With code2pdf installed next to code2txt, 18 of
  164 code2txt runs had code2pdf pick the files (`code2pdf --include … --list-files`), and one
  read code2txt's source and wrapped bash with `dotglob` to get hidden files. The agents'
  PATH also held this machine's Homebrew code2pdf. The 3.8 ablation was checked and is clean:
  no run used Homebrew's copy or a 3.9-only option. Each eval now installs only the tool it
  measures, and the PATH leaves out Homebrew.

## Not done, and why

- **No quality hillclimb on code2pdf.** At 99–100% there is no headroom; the blog post advises
  against climbing a saturated eval. code2txt was climbed instead (above), and it is now
  saturated too.
- **No cost hillclimb.** Runs take about 3.6 turns (read help, check, convert, answer), and most
  of the cost is the agent's own fixed prompt. code2pdf's help text is about 1k tokens. Any
  saving would be inside the noise.
- **Next useful cases** are ones where agents still fail. Two candidates: requests that need
  judgement ("the files a new backend developer should read"), which needs an LLM judge and a
  rubric; and agents without shell tools.
