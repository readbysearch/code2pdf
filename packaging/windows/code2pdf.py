"""
code2pdf on Windows: what bin/code2pdf, print_all.sh and print_single_file_to_pdf.sh do on macOS
and Linux, in Python, for code2pdf.exe (built with PyInstaller by code2pdf.spec). The options,
defaults and error messages are the same as bin/code2pdf's.
"""

import multiprocessing
import os
import re
import sys

HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ROOT = HERE if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# The same defaults as bin/code2pdf
DEFAULT_BLACKLIST = ('["node_modules", ".git", "dist", "out", "build", "target", "DerivedData", "Pods", '
                     '"vendor", "__pycache__", "venv"]')
DEFAULT_BLACKLIST_PATTERN = "env*"
DEFAULT_WHITELIST_EXTENSIONS = (
    '["c", "h", "cc", "cpp", "cxx", "hh", "hpp", "m", "mm", "swift", "go", "rs", "zig", "java", "kt", '
    '"kts", "scala", "groovy", "gradle", "cs", "fs", "py", "rb", "php", "pl", "lua", "r", "jl", "dart", '
    '"ex", "exs", "erl", "hs", "ml", "clj", "js", "mjs", "cjs", "jsx", "ts", "tsx", "vue", "svelte", '
    '"html", "css", "scss", "sql", "proto", "graphql", "sh", "bash", "zsh", "fish", "ps1", "md", "rst", '
    '"yaml", "yml", "toml"]')
DEFAULT_WHITELIST_FILES = '["README", "LICENSE", "Makefile", "launch.json"]'

VALUE_OPTIONS = {"--theme", "-j", "--jobs", "-o", "--output", "--ignore-files", "--ignore-types",
                 "--ignore-folders", "--include-types", "--include", "--exclude", "--files-from",
                 "--changed", "--summary"}
ACTIONS = {"-s", "--single", "-a", "--all", "--list-themes", "-h", "--help", "-V", "--version"}


def help_text():
    """bin/code2pdf's help, read from it so the two can't differ."""
    with open(os.path.join(ROOT, "bin", "code2pdf"), encoding="utf-8") as f:
        text = f.read()
    return text.split("<<'HELP'\n", 1)[1].split("\nHELP\n", 1)[0]


def fail(message, code=1):
    print(f"Error: {message}", file=sys.stderr)
    return code


def main(argv):
    lists = {"--ignore-files": [], "--ignore-types": [], "--ignore-folders": [], "--include-types": []}
    select, args = [], []
    output = files_from = changed = summary = ""
    list_files = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in VALUE_OPTIONS:
            if i + 1 >= len(argv) or not argv[i + 1]:
                return fail(f"{arg} needs a value (see code2pdf --help)")
            value = argv[i + 1]
            i += 2
            if arg == "--theme":
                os.environ["CODE2PDF_THEME"] = value
            elif arg in ("-j", "--jobs"):
                os.environ["CODE2PDF_JOBS"] = value
            elif arg in ("-o", "--output"):
                output = value
            elif arg in lists:
                lists[arg].append(value)
            elif arg in ("--include", "--exclude"):
                select += [arg, value]
            elif arg == "--files-from":
                files_from = value
            elif arg == "--changed":
                changed = value
            else:
                summary = value
            continue
        i += 1
        if arg == "--dev":
            continue
        if arg in ("-q", "--quiet"):
            os.environ["CODE2PDF_QUIET"] = "1"
        elif arg == "--list-files":
            list_files = True
        elif arg in ACTIONS or not arg.startswith("-") or arg == "-":
            args.append(arg)
        else:
            return fail(f"unknown option {arg} (see code2pdf --help)")

    if (files_from or changed) and not args:
        args = ["-a", "."]
    if args and args[0] in ("-s", "--single", "-a", "--all") and len(args) > 2:
        return fail(f"{args[0]} takes one path; unexpected: {' '.join(args[2:])} (see code2pdf --help)")
    if (files_from or changed or list_files or select) and (not args or args[0] not in ("-a", "--all")):
        return fail("--files-from, --changed, --include, --exclude and --list-files work with -a DIR")

    action = args[0] if args else ""
    if action in ("-h", "--help"):
        print(help_text())
        return 0
    if action in ("-V", "--version"):
        import version
        print(version.report("code2pdf"))
        return 0
    if action not in ("-s", "--single", "-a", "--all", "--list-themes"):
        print(help_text())
        return 1

    import dir_to_pdf
    if action == "--list-themes":
        import theme
        print("\n".join(theme.list_themes()))
        return 0
    if action in ("-s", "--single"):
        return single(args[1] if len(args) > 1 else "", output, summary)

    root = args[1] if len(args) > 1 else "."
    if not os.path.isdir(root):
        return fail(f"directory not found: {root}")
    root = os.path.abspath(root)
    extra = list(select)
    if list_files:
        extra.append("--list-files")
    for option, value in (("--output", output), ("--files-from", files_from), ("--changed", changed),
                          ("--summary", summary)):
        if value:
            extra += [option, value]
    return dir_to_pdf.run_main(dir_to_pdf.main, [
        root, os.path.join(root, "merged.pdf"), DEFAULT_BLACKLIST, DEFAULT_BLACKLIST_PATTERN,
        DEFAULT_WHITELIST_EXTENSIONS, DEFAULT_WHITELIST_FILES, "true",
        *(",".join(lists[k]) for k in ("--ignore-files", "--ignore-types", "--ignore-folders", "--include-types")),
        *extra])


def single(spec, output, summary):
    """print_single_file_to_pdf.sh: FILE (or FILE:START-END) to <name>.pdf here, or to OUTPUT."""
    if not spec:
        return fail("No file path provided.")
    path = spec
    match = re.fullmatch(r"(.+):[-+0-9][-+0-9,]*", spec)
    if not os.path.isfile(path) and match and os.path.isfile(match.group(1)):
        path = match.group(1)
    if not os.path.isfile(path):
        print("File not found.", file=sys.stderr)
        return 1
    print(f"Converting to a PDF file for {spec}")
    name = os.path.splitext(os.path.basename(path))[0]
    if not output:
        output = os.path.join(os.getcwd(), f"{name}.pdf")
    elif os.path.isdir(output):
        output = os.path.join(output, f"{name}.pdf")
    import code_to_pdf
    import dir_to_pdf
    return dir_to_pdf.run_main(code_to_pdf.main, [spec, output, spec, *(["--summary", summary] if summary else [])])


if __name__ == "__main__":
    multiprocessing.freeze_support()  # parts mode renders in spawned copies of this program
    import dir_to_pdf
    dir_to_pdf.exit_now(main(sys.argv[1:]))
