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
line numbers. A `path:START-END` form for `--files-from` (printed with its real path and line
numbers) would cover it. That is a design decision, so it's proposed, not built.

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
