---
name: code2pdf
description: Print source code as a PDF, or bundle it into one text file for an LLM, with the code2pdf and code2txt command-line tools. Use this whenever someone wants code in a PDF or on paper, such as a whole repository, a folder, some files, what changed in a commit or branch (with the changed lines marked), or specific functions with their real line numbers, to read offline, review in print, annotate, hand in, archive or send as one file. Also use it for "all the code in one file" to paste into ChatGPT or Claude. Use it even when no tool is named ("make me a printout of the backend", "I need these two functions as a PDF for the meeting"). Not for rendering Markdown or HTML documents as formatted pages, or for editing existing PDFs.
---

# Printing code with code2pdf

code2pdf turns source files into one PDF made for reading and printing. It has a contents page,
syntax highlighting, the file's own line numbers, the path in every page header, a bookmark per
file, and git dates. code2txt comes with it and writes one Markdown text file instead, for an
LLM's context.

Use these rather than writing your own PDF script. A home-made script usually loses the
contents page, the real paths and the line numbers, and it takes longer to get right.

## 1. Check that it's installed

Run `code2pdf --version`. If the command isn't found, it can be installed with one of these:

- macOS, or Linux with Homebrew: `brew install readbysearch/tap/code2pdf`
- Ubuntu 24.04+ or Debian 13+:
  `curl -LO https://github.com/readbysearch/code2pdf/releases/latest/download/code2pdf_all.deb && sudo apt install ./code2pdf_all.deb`
- Other Linux, no sudo: `curl -sSL https://raw.githubusercontent.com/readbysearch/code2pdf/main/install.sh | bash -s -- --user`
- Windows, in PowerShell (no administrator rights):
  `Invoke-WebRequest https://github.com/readbysearch/code2pdf/releases/latest/download/code2pdf-windows-x64.zip -OutFile $env:TEMP\code2pdf.zip; Expand-Archive $env:TEMP\code2pdf.zip $env:LOCALAPPDATA\Programs -Force`,
  then run it as `$env:LOCALAPPDATA\Programs\code2pdf\code2pdf.exe`. code2txt isn't available on Windows.

A fresh Ubuntu desktop has `wget` but not `curl`: use `wget URL` instead of `curl -LO URL`, and
`wget -qO- URL` instead of `curl -sSL URL`.

Installing software changes the user's machine. Say which command you'll run and get their OK
first, unless they already asked you to install it.

## 2. Read `code2pdf --help`

It is short, and it is the authority on options. Options change between releases, so read it
instead of relying on memory. Unknown options are errors, not ignored.

## 3. Choose the files

Turn the request into a set of files, in one of three ways:

- **code2pdf's own selection**, adjusted with `--include` and `--exclude` globs. This suits
  "the project (or a folder), minus or plus some kinds of files".
- **Your own list**, piped in with `--files-from -`. This suits selections that come from git
  (`git diff --name-only HEAD~1`), from a search (`grep -rl SessionInterface src`), or that need
  a particular order. The list is used exactly as given, in that order.
- **What changed**, with `--changed REV` (a commit, tag or branch). It prints each change since
  REV with its enclosing block and marks the changed lines with a bar in the margin, so a
  reader sees what's new. It suits reviewing a commit (`--changed HEAD~1`), a branch
  (`--changed main`) or uncommitted work (`--changed HEAD`). Deleted and untracked files are
  left out with a note.

The default selection skips hidden folders, build output, vendored dependencies and some
non-code types such as JSON. Check whether the request needs any of those.

Before converting, add `--list-files` to the same command. It prints the files without
rendering anything. Compare the list with what was asked. If the user is around, show it to
them.

## 4. Print part of a file

For specific functions or a region, write `path:START-END` in the list, or after `-s`:

```bash
printf 'src/app.py:120-180\nsrc/util.py\n' | code2pdf --files-from - -o ~/Desktop/review.pdf
```

The PDF keeps the real path and the file's own line numbers. Find each range in the source:
`grep -n` for the definition, then read on to where it ends, rather than estimating.
If code2pdf warns that a range "stops inside a block", the function goes on past your end
line. Use the range it suggests. Don't copy code into new files to print it, because that
loses the real path and line numbers.

## 5. Convert

- `--summary "..."` puts one sentence under the title. Say what this is and what was left out,
  such as "The refund change: the files it touched, without tests". The reader, and the user
  weeks later, then know what they're holding.
- `-o PATH` sets where the PDF goes. Keep it outside the project unless asked, so the project
  stays unchanged and a later run doesn't print the PDF itself.
- A whole large repository can take several minutes. The first line of output estimates the
  page count. Give the command a long timeout, such as 10 minutes, rather than the usual 2.
- Read the warnings it prints and act on them. They cover globs that matched nothing, ranges
  cut short, and missing fonts for Chinese, Japanese or Korean text.

## 6. Report

Say where the PDF is, how many pages it has, and which files went in. If you left anything out,
say what and why.

## code2txt

When the user wants the code as text for an LLM rather than as a PDF, use code2txt. It takes
the same `--files-from` lists and `path:START-END` ranges, and writes Markdown with a contents
list:

```bash
git ls-files src | code2txt --files-from - -o src.md
code2pdf --changed HEAD~1 --list-files | code2txt --files-from - -o change.md
```

Its default selection and filter options differ from code2pdf's, so read `code2txt --help`.
