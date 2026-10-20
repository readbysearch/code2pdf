"""
Checks code2pdf.exe on Windows: python check.py EXE OUTDIR. Prints with it the way the VS Code
extension does (stdout and stderr through pipes) and checks each PDF with pypdf: pages, text
(including Chinese, Japanese and Korean) and fonts. Exits 1 if any check failed.
"""

import os
import subprocess
import sys
import textwrap
import time

from pypdf import PdfReader

EXE, OUT = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)
failures = []


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run(label, args, cwd, stdin="", env=None, expect=0):
    started = time.monotonic()
    result = subprocess.run([EXE, *args], cwd=cwd, input=stdin.encode(), capture_output=True,
                            env={**os.environ, **(env or {})})
    seconds = time.monotonic() - started
    try:
        out, err = result.stdout.decode("utf-8"), result.stderr.decode("utf-8")
    except UnicodeDecodeError as e:
        failures.append(f"{label}: output isn't UTF-8 ({e})")
        out, err = result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace")
    print(f"\n== {label}: exit {result.returncode}, {seconds:.1f} s\n$ code2pdf {' '.join(args)}")
    print(textwrap.indent((out + err).strip()[-3000:], "  "))
    if result.returncode != expect:
        failures.append(f"{label}: exit {result.returncode}, expected {expect}")
    return out, err


def pdf(label, path, must_contain=(), min_pages=1, header=None):
    if not os.path.exists(path):
        failures.append(f"{label}: no PDF at {path}")
        return
    reader = PdfReader(path)
    text = "".join(page.extract_text() or "" for page in reader.pages)
    fonts = set()
    for page in reader.pages:
        for font in (page.get("/Resources", {}).get("/Font", {}) or {}).values():
            font = font.get_object()
            fonts.add(str(font.get("/BaseFont", "?")))
    print(f"  {label}: {len(reader.pages)} pages, fonts: {', '.join(sorted(fonts))}")
    if len(reader.pages) < min_pages:
        failures.append(f"{label}: {len(reader.pages)} pages, expected at least {min_pages}")
    if header and header not in text:
        failures.append(f"{label}: no page header {header!r} (paths are shown with /)")
    for wanted in must_contain:
        if wanted not in text.replace("\n", "").replace(" ", ""):
            failures.append(f"{label}: {wanted!r} isn't in the PDF's text")


# A project with Chinese, Japanese and Korean text, and a folder name with a space and Chinese
proj = os.path.join(OUT, "proj")
write(os.path.join(proj, "app.py"), "".join(
    ["# 中文注释：打印测试\n", "# 日本語のコメント\n", "# 한국어 주석\n", "def greet(name):\n", "    return f'hello {name}'\n"]
    + [f"value_{i} = {i}  # line {i}\n" for i in range(6, 41)]))
write(os.path.join(proj, "README.md"), "# 项目说明\n\nA test project → printed on Windows.\n")
write(os.path.join(proj, "数据 dir", "笔记.md"), "# 笔记\n\n第一行。\n")
write(os.path.join(proj, "src", "util.js"), "export const add = (a, b) => a + b;\n")

out, _ = run("version", ["--version"], OUT)
if "Windows build" not in out or "CJK font: Microsoft YaHei" not in out:
    failures.append("version: expected a Windows build that finds Microsoft YaHei")
out, _ = run("help", ["--help"], OUT)
if "Usage: code2pdf" not in out:
    failures.append("help: no usage text")
run("list files", ["-a", proj, "--list-files"], OUT)
run("folder", ["-a", proj, "-o", os.path.join(OUT, "folder.pdf")], OUT)
pdf("folder", os.path.join(OUT, "folder.pdf"), ["中文注释", "日本語のコメント", "한국어주석", "项目说明", "笔记.md", "第一行"],
    header="数据 dir/笔记.md")
run("files-from stdin, a range", ["--files-from", "-", "-o", os.path.join(OUT, "list.pdf")], proj,
    stdin="app.py:4-10\n数据 dir/笔记.md\n")
pdf("files-from", os.path.join(OUT, "list.pdf"), ["defgreet", "笔记.md"])
run("one file, a range", ["-s", "app.py:1-5", "-o", os.path.join(OUT, "single.pdf")], proj)
pdf("single", os.path.join(OUT, "single.pdf"), ["中文注释"])
run("theme mono", ["-s", "app.py", "--theme", "mono", "-o", os.path.join(OUT, "mono.pdf")], proj)
run("unknown option", ["--nope"], OUT, expect=1)

# Parts mode: spawned worker processes, each a copy of code2pdf.exe
big = os.path.join(OUT, "big")
for n in range(24):
    write(os.path.join(big, f"m{n:02}.py"), "".join(f"x_{i} = {i}  # 第{i}行\n" for i in range(1, 121)))
run("parts mode", ["-a", big, "-o", os.path.join(OUT, "parts.pdf")], OUT, env={"CODE2PDF_PART_PAGES": "10"})
pdf("parts", os.path.join(OUT, "parts.pdf"), ["m00.py", "m23.py", "第120行"], min_pages=24)

# git: --changed, and the dates on the contents page
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=proj, check=True)
for args in (["add", "."], ["-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "first"]):
    subprocess.run(["git", *args], cwd=proj, check=True)
with open(os.path.join(proj, "app.py"), "a", encoding="utf-8", newline="\n") as f:
    f.write("changed = '已修改'\n")
run("changed", ["--changed", "HEAD", "-o", os.path.join(OUT, "changed.pdf")], proj)
pdf("changed", os.path.join(OUT, "changed.pdf"), ["已修改"])

# Stopped the way the extension stops it on Windows (TerminateProcess): what's left behind?
child = subprocess.Popen([EXE, "-a", big, "-o", os.path.join(OUT, "stopped.pdf")], cwd=OUT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6)
child.terminate()
child.wait()
time.sleep(2)
left = [n for n in os.listdir(OUT) if n.startswith(".code2pdf-") or n == "stopped.pdf"]
print(f"\n== stopped after 6 s: exit {child.returncode}; left in the output folder: {left or 'nothing'}")

print("\n" + ("\n".join(f"FAILED: {f}" for f in failures) if failures else "All checks passed."))
sys.exit(1 if failures else 0)
