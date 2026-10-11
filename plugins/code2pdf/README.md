# code2pdf skill for Claude Code

This plugin adds one skill, `code2pdf`. It lets Claude print source code as a PDF, or bundle it
into one text file for an LLM, with the [code2pdf](https://github.com/readbysearch/code2pdf)
command-line tools. The PDF has a contents page, syntax highlighting, the files' own line
numbers and a bookmark per file.

Claude uses the skill when you ask for code in a PDF or on paper, even if you don't name the
tool. For example, "make me a PDF of the backend for tomorrow's review" or "print these two
functions with their real line numbers". The skill tells Claude:

- how to check that code2pdf is installed, and how to install it (with your OK);
- to read `code2pdf --help` for the options;
- to choose the files, show you the list before converting, and print only parts of files
  when that's what you asked for;
- to save the PDF outside your project and tell you what went in.

## Install

```bash
claude plugin install code2pdf --marketplace readbysearch/code2pdf
```

The skill needs the code2pdf tools themselves: `brew install readbysearch/tap/code2pdf` on
macOS. For Linux, see the [code2pdf README](https://github.com/readbysearch/code2pdf#installation).

## License

AGPL-3.0-only, like code2pdf.
