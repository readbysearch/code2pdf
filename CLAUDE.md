# CLAUDE.md

Guidance for working on this repository. **User-facing behaviour (installing, options, examples,
fonts) is documented in README.md — keep it there, not here.** This file holds what you can't
learn from the README or quickly from the code: how the pieces fit, conventions that must hold,
and lessons that were expensive to learn.

## What it is

- `code2pdf`: source code → PDF (contents page, syntax highlighting, line numbers, git dates,
  bundled IBM Plex fonts, CJK). Pipeline: Pygments → one HTML document → WeasyPrint → PDF.
- `code2txt`: a directory → one Markdown text file for LLM context (pure bash, no Python).

## How a run flows

- `bin/code2pdf` parses options, resolves its install directory, checks dependencies, then:
  - `-s FILE` → `scripts/print_single_file_to_pdf.sh` → `code_to_pdf.py` → `dir_to_pdf.render_document(contents=False)`
  - `-a DIR` → `scripts/print_all.sh` (validates DIR, refuses the pre-v3.8 vimrc argument) → `dir_to_pdf.py`
- `dir_to_pdf.py`: `Selector` + `collect_files` choose files (depth-first, sorted by name, hidden
  entries skipped, symlink loops cut, the output file and binary files never included), or
  `read_file_list` takes them from `--files-from`; `source_info` gets git dates;
  `build_sections`/`build_contents`/`wrap_document` build the HTML; `render_document`
  renders it, or hands big documents to `parts.py`.
- Selection precedence: `--exclude` > `--include` > default rules (built-in lists, `--ignore-*`,
  `--include-types`). `Pattern.may_reach` decides whether to enter a normally skipped folder:
  only a literal glob segment may name one, so `*`/`**` never pull in `node_modules` or `.git`.
  Contents-page groups are consecutive runs of one folder (`group_by_folder`), never merged.
- `bin/code2pdf` rejects unknown options and options without a value; list options add up when
  repeated. Agents depend on these errors to notice a mistyped option.
- `theme.py`: themes (`paper`, `mono`, any Pygments style), `@font-face` for `fonts/`, page CSS.
  `progress.py`: page estimate and the [1/3]–[3/3] display. `version.py`: `--version`.
- Default file selection lives in `bin/code2pdf` (`DEFAULT_*`); `print_all.sh` passes the same
  positional arguments as `dir_to_pdf.py` minus OUTPUT (it writes `ROOT/merged.pdf`).

## Conventions that must hold

- **Launchers find their install from their own real path** (following symlinks), or
  `$CODE2PDF_HOME` (set by the Homebrew formula). `scripts/print_all.sh` is the marker file that
  proves an install is real. `fonts/` and `VERSION` are found next to `scripts/`.
- **Scripts call plain `python3`.** The launcher puts a private env first on PATH: `venv/`
  (install.sh), `.venv/` (a checkout); Homebrew does the same via its wrapper. So
  `./bin/code2pdf` always tests the working tree; `code2pdf` on PATH is the installed copy.
- **`version.py` uses only the standard library** and runs before the dependency check, so
  `--version` works on broken installs.
- **Never touch `/tmp`**: output is written to a temp file next to the target and renamed into
  place; code2txt skips its own output file by real path.
- **Every feature works in all four install kinds**: Homebrew, `.deb` (Ubuntu's own packages),
  `install.sh` (venv or conda-forge), git checkout. Check all of them when changing paths,
  dependencies or what gets copied (install.sh copy list, `build-deb.sh`, formula `prefix.install`).

## Rendering notes

- Layout: one block `<span>` per code line (Pygments `linespans`) with `::before` counters gives
  margin line numbers and hanging wrapped lines; it costs ~60% more render time than inline line
  numbers. Contents page uses `target-counter()`; file `<h1>`s set the page header (`string-set`)
  and PDF bookmarks.
- Dates: `Printed <date> from commit <hash> (<branch>)` on the contents page; per file `last
  changed` (one streamed `git log --relative`), `uncommitted changes` (`git status`) or `modified`
  (mtime). `$SOURCE_DATE_EPOCH` fixes the printing date.
- Progress follows WeasyPrint's `weasyprint.progress` log (Step 1, per-page Step 5, Step 6); the
  page estimate assumes 89 columns and 59 rows per page. A ticker thread keeps the two silent stages moving.
- **Parts mode** (`parts.py`, documents over 2 × `$CODE2PDF_PART_PAGES`, default 100): WeasyPrint
  holds every page in memory (~0.6 GB + ~6.5 MB/page), so ~100-page parts of whole files render in
  spawned children (no headers, no contents); the parent renders the contents page with written-in
  numbers (links `code2pdf:f<i>`, rewired to `/Dest` later) and an overlay of empty pages carrying
  headers/footers, then joins with pypdf. Output is text- and pixel-identical to a single pass.
  `-j`/`$CODE2PDF_JOBS` (default 3 with ≥16 GB RAM, 2 with ≥8 GB, else 1).
  `$CODE2PDF_DEBUG_TIMING` prints per-stage timings.
- CJK: Plex has none, so CJK comes from system fonts (`CJK_MONO_FALLBACK` for code, `CJK_FALLBACK`
  for titles). `missing_cjk_fonts` probes `fc-list :charset=` (中 あ 한) and warns before and after
  converting.

## Lessons (don't relearn these)

- **CJK without a font prints as empty boxes but the PDF text stays correct**, so text-based
  tests pass. Check fonts (`pdffonts`) or render pages to images.
- WeasyPrint < 62 ignores `calc()` in the code-line indent: use plain lengths (Ubuntu 24.04 ships 61).
- pypdf: use `add_page`, not `append` (it imports one named destination per code line: 10× slower,
  6× bigger); after `merge_page` call `compress_content_streams`; stamp overlays with `over=False`
  so text order matches a single pass.
- Minimal Ubuntu has no `rev` or `file`; macOS has bash 3.2 (no `${x^^}`, no `case` inside `$( )`).
- `install.sh`: `python3 -m venv --help` works without `ensurepip`, so test `import ensurepip`;
  a non-interactive shell's PATH lacks `~/.local/bin` even when `~/.profile` adds it, so look in
  the shell files before appending.
- `VERSION` is filled in by git export-subst in GitHub tarballs (`%(describe:tags)` works there);
  CI checkouts have no `.git` and no tags. raw.githubusercontent.com caches files for 5 minutes.
- With `pipefail`, `cmd | grep -q` fails when grep exits early (SIGPIPE): capture output first.
- Agents run code2pdf under command timeouts. Launchers `exec` down to Python so signals reach
  it; `run_main` turns SIGTERM/SIGHUP into KeyboardInterrupt so `finally` removes temp files;
  parts mode terminates its workers on abort (`shutdown()` alone waits for each part).
  `tests/test_interrupt.py` covers it.

## Testing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-test.txt
.venv/bin/pytest -q                       # tests using ghostscript or poppler skip when those are missing
```

- Tests run the working tree via `bin/` and `scripts/`; `tests/test_install_sh.py` sources
  `install.sh` with `CODE2PDF_INSTALL_SOURCED=1` to call single functions.
- **Before tagging, run the suite on an exact CI replica**: `git archive HEAD` unpacked into
  `ubuntu:24.04` and `ubuntu:26.04` containers with Ubuntu's `weasyprint python3-pygments
  python3-pypdf fonts-noto-cjk python3-pytest poppler-utils ghostscript git`. v3.7's release
  failed on assumptions that only hold on macOS or in a git checkout. Start the container as
  GitHub does (`docker run -d … tail -f /dev/null`, then `docker exec`): its PID 1 never reaps
  orphans, which `bash -c` does (v3.10 failed on a zombie only that setup shows).
- `packaging/deb/test-deb.sh DEB` installs, uses and removes the `.deb` in a fresh container.
- **Agent eval** (`evals/agent_selection/`, see its README and RESULTS): headless agents turn
  plain-language requests into PDFs; it needs the `claude` CLI and costs money, so it is not part
  of pytest. Before releasing a change to selection, help text or messages, run the Haiku pass
  (~$0.30, ~15 min) and compare with RESULTS.md (99–100%):
  `.venv/bin/python evals/agent_selection/run.py run --label pre-vX.Y --model haiku --repeats 1 --set fixtures`
  (add `--set real` for the real repositories, `--tool code2txt` for code2txt).

## Releasing

Canonical repo `readbysearch/code2pdf`; Homebrew tap `readbysearch/homebrew-tap`
(`brew install readbysearch/tap/code2pdf`). Push to GitHub as the `readbysearch` account
(it has the `workflow` scope; the `waleking` fork is archived).

1. Push `main`, then an annotated tag `vX.Y.Z`. `.github/workflows/release-deb.yml` builds the
   `.deb` (lintian), runs the unit and install tests on Ubuntu 24.04 and 26.04, and creates the
   GitHub release with `code2pdf_X.Y.Z_all.deb` and `code2pdf_all.deb` (stable latest link).
2. In the tap, update `code2pdf.rb` `url` and `sha256`
   (`curl -sL https://github.com/readbysearch/code2pdf/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256`),
   keep `prefix.install` in sync with what the tarball contains, run
   `brew audit --strict --online readbysearch/tap/code2pdf`, push, then `brew upgrade` and `brew test`.
3. `install.sh` installs the latest release by default, so pushing `main` alone changes only the
   installer itself.
