"""Harder cases on real repositories at pinned release tags: hundreds of files, real naming
conventions, and code2pdf's default rules hitting real layouts (Gymnasium's envs/ package is
dropped by the env* rule; Alamofire's default selection is mostly generated HTML docs).

Projects are downloaded once into ~/.cache/code2pdf-evals (GitHub tarballs, never executed)
and copied into each run's folder as a git repository. `expected` is a function of the
project root, applying the rule the request states; `run.py check` verifies every case.
"""

import os
import shutil
import subprocess
import tarfile
import urllib.request

CACHE = os.path.expanduser("~/.cache/code2pdf-evals")

REPOS = {
    "gymnasium": ("Farama-Foundation/Gymnasium", "v1.0.0"),
    "alamofire": ("Alamofire/Alamofire", "5.9.1"),
    "gin": ("gin-gonic/gin", "v1.10.0"),
    "express": ("expressjs/express", "4.21.0"),
    "flask": ("pallets/flask", "3.0.3"),
    "flask-3.0.2": ("pallets/flask", "3.0.2"),
}


def fetch(key):
    repo, tag = REPOS[key]
    dest = os.path.join(CACHE, f"{repo.split('/')[1]}-{tag}")
    if not os.path.isdir(dest):
        os.makedirs(CACHE, exist_ok=True)
        archive = dest + ".tar.gz"
        urllib.request.urlretrieve(f"https://codeload.github.com/{repo}/tar.gz/refs/tags/{tag}", archive)
        tmp = dest + ".partial"
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
        (top,) = os.listdir(tmp)
        os.rename(os.path.join(tmp, top), dest)
        os.rmdir(tmp)
        os.remove(archive)
    return dest


def _git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev", GIT_AUTHOR_EMAIL="dev@example.com",
               GIT_COMMITTER_NAME="Dev", GIT_COMMITTER_EMAIL="dev@example.com",
               GIT_AUTHOR_DATE="2026-09-01T10:00:00", GIT_COMMITTER_DATE="2026-09-01T10:00:00")
    subprocess.run(["git", "-C", root, "-c", "init.defaultBranch=main", *args],
                   check=True, capture_output=True, env=env)


def build(name, root, setup=None):
    """Copy the pinned tree to ROOT as a git repository. setup={"previous": key} commits that
    release first, so the last commit is the release diff."""
    first = (setup or {}).get("previous")
    shutil.copytree(fetch(first or name), root, symlinks=True)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", REPOS[first or name][1])
    if first:
        for entry in os.listdir(root):
            if entry != ".git":
                path = os.path.join(root, entry)
                shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
        shutil.copytree(fetch(name), root, symlinks=True, dirs_exist_ok=True)
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", REPOS[name][1])


# --- rules for expected files --------------------------------------------------------------

def files(root, under=""):
    out = []
    for folder, dirs, names in os.walk(os.path.join(root, under)):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names):
            out.append(os.path.relpath(os.path.join(folder, name), root))
    return sorted(out)


def is_text(root, rel):
    with open(os.path.join(root, rel), "rb") as f:
        return b"\0" not in f.read(8192)


def git_lines(root, *args):
    return subprocess.run(["git", "-C", root, "-c", "core.quotePath=false", *args],
                          capture_output=True, text=True, check=True).stdout.splitlines()


IMAGE = (".png", ".gif", ".jpg", ".jpeg", ".svg", ".ico", ".webp")


def toctree(root, index):
    """Entries of the first toctree in an .rst file, as paths next to it."""
    folder = os.path.dirname(index)
    entries, inside = [], False
    for line in open(os.path.join(root, index), encoding="utf-8"):
        if line.startswith(".. toctree::"):
            inside = True
            continue
        if inside:
            text = line.strip()
            if not text or text.startswith(":"):
                if entries and not text:
                    break
                continue
            if not line.startswith((" ", "\t")):
                break
            entries.append(os.path.join(folder, text + ".rst"))
    return entries


def _gin_root(r):
    return [f for f in files(r) if "/" not in f and f.endswith(".go") and not f.endswith("_test.go")]


def _default(r, *extra):
    """code2pdf's own default selection (what `code2pdf -a .` lists), plus EXTRA folders."""
    env = dict(os.environ, CODE2PDF_QUIET="1")
    cmd = [os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "bin", "code2pdf"), "-a", r, "--list-files"]
    for folder in extra:
        cmd += ["--include", folder]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=True).stdout.split("\n")[:-1]


# Scale: renders longer than an agent's default 2-minute command limit (Claude Code's Bash tool).
# The agent has to notice and wait (a longer timeout, or running it in the background).
SCALE_CASES = [
    dict(id="scale-alamofire", project="alamofire", scale=True,
         request="Print the whole Alamofire repository exactly as code2pdf selects files by "
                 "default, nothing added or removed (that includes the generated HTML docs). "
                 "Yes, it will be big.",
         expected=lambda r: _default(r),
         why_hard="~7,700 pages, ~6 minutes to render: three times the default command timeout.",
         source="production: whole-repository prints (ClaudeTerminal took 54 s for 563 pages)",
         reference="code2pdf -a . -o {out}"),
    dict(id="scale-gymnasium", project="gymnasium", scale=True,
         request="Print the whole Gymnasium repository the way code2pdf normally selects files, "
                 "and make sure gymnasium/envs is in it too (all of its files).",
         expected=lambda r: _default(r, "gymnasium/envs"),
         why_hard="Over the default command timeout, and env* drops gymnasium/envs.",
         source="production: whole-repository prints", reference="code2pdf -a . --include gymnasium/envs -o {out}"),
]

# Judgement: requests by topic ("the code that handles sessions"), as people often ask. The
# requests say "whole files": asked for "the methods that ...", Haiku and Sonnet cut excerpts
# into new files with made-up names, a reasonable reading that the first wording left open.
# `expected` is what must be in the PDF; `allowed` are defensible extras; anything else fails.
# Each required file is backed by the code (noted in why_hard), so experts would agree.
JUDGEMENT_CASES = [
    dict(id="flask-sessions", project="flask",
         request="From the flask package (src/flask), print the code that implements sessions: the "
                 "session classes and interface, plus the files where Flask opens and saves the "
                 "session during a request. Whole files, as they are; no tests, no docs.",
         expected=lambda r: ["src/flask/sessions.py", "src/flask/ctx.py", "src/flask/app.py"],
         allowed=["src/flask/json/tag.py", "src/flask/sansio/app.py", "src/flask/globals.py",
                  "src/flask/testing.py", "src/flask/helpers.py", "src/flask/__init__.py",
                  "src/flask/templating.py"],
         why_hard="Needs reading code: ctx.py opens the session (RequestContext.push), app.py saves "
                  "it (process_response); 12 files mention sessions.",
         source="hand-written (topic request)",
         reference="printf 'src/flask/sessions.py\nsrc/flask/ctx.py\nsrc/flask/app.py\n' | code2pdf --files-from - -o {out}"),
    dict(id="gin-middleware", project="gin",
         request="Print gin's built-in middleware (the logger and the panic recovery) and the code "
                 "that registers middleware (the files with the Use functions). Whole files, as they are; "
                 "no tests.",
         expected=lambda r: ["logger.go", "recovery.go", "gin.go", "routergroup.go"],
         allowed=["context.go", "ginS/gins.go"],
         why_hard="Use is defined twice: Engine.Use in gin.go and RouterGroup.Use in routergroup.go "
                  "(ginS.Use wraps them; Opus found it, so it is allowed).",
         source="hand-written (topic request)",
         reference="printf 'logger.go\nrecovery.go\ngin.go\nroutergroup.go\n' | code2pdf --files-from - -o {out}"),
    dict(id="gin-json-render", project="gin",
         request="Print the code that renders JSON responses in gin: the JSON renderers and the "
                 "files with the gin.Context methods that use them. Whole files, as they are; no tests.",
         expected=lambda r: ["render/json.go", "context.go"],
         allowed=["render/render.go", "internal/json/json.go", "internal/json/go_json.go",
                  "internal/json/jsoniter.go", "internal/json/sonic.go"],
         why_hard="All JSON variants (JSONP, SecureJSON, AsciiJSON, PureJSON) live in one file; the "
                  "other renderers (XML, YAML, HTML, ...) must stay out.",
         source="hand-written (topic request)",
         reference="printf 'render/json.go\ncontext.go\n' | code2pdf --files-from - -o {out}"),
    dict(id="express-routing", project="express",
         request="Print Express's routing implementation from lib/ (the router, its routes and "
                 "layers) and the application file that sets the router up. Whole files, as they are; "
                 "no tests or examples.",
         expected=lambda r: ["lib/router/index.js", "lib/router/route.js", "lib/router/layer.js",
                             "lib/application.js"],
         allowed=["lib/express.js", "lib/middleware/init.js", "lib/middleware/query.js"],
         why_hard="request.js, response.js, view.js and utils.js are next to it and not routing.",
         source="hand-written (topic request)",
         reference="ls lib/router/*.js lib/application.js | code2pdf --files-from - -o {out}"),
    dict(id="alamo-retry", project="alamofire",
         request="Print the Alamofire source that decides whether and when a failed request is "
                 "retried: the retrier protocol, the built-in retry policy, and where Session asks "
                 "for a retry. Whole files, as they are; Source/ only.",
         expected=lambda r: ["Source/Features/RequestInterceptor.swift", "Source/Features/RetryPolicy.swift",
                             "Source/Core/Session.swift"],
         allowed=["Source/Features/AuthenticationInterceptor.swift", "Source/Core/AFError.swift",
                  "Source/Core/Request.swift",
                  # these ask the Session for a retry when response serialization fails (Haiku found it)
                  "Source/Core/DataRequest.swift", "Source/Core/DownloadRequest.swift",
                  "Source/Core/UploadRequest.swift"],
         why_hard="RequestRetrier is declared in RequestInterceptor.swift, not a file named after it; "
                  "Session.retryResult asks the retrier.",
         source="hand-written (topic request)",
         reference="printf 'Source/Features/RequestInterceptor.swift\nSource/Features/RetryPolicy.swift\n"
                   "Source/Core/Session.swift\n' | code2pdf --files-from - -o {out}"),
]

REAL_CASES = [
    dict(id="gym-package", project="gymnasium",
         request="Print the gymnasium package (the gymnasium/ folder): every Python file in it.",
         expected=lambda r: [f for f in files(r, "gymnasium") if f.endswith(".py")],
         why_hard="136 files; the env* default silently drops gymnasium/envs (the environments, "
                  "~60 files) and only a careful look at --list-files shows it; --include envs would "
                  "also bring its 30 MuJoCo XML files (a folder include takes every type).",
         source="production: env* folder rule vs. RL code (real Gymnasium layout)",
         reference="code2pdf -a gymnasium --include-types py --include 'envs/**/*.py' -o {out}"),
    dict(id="gym-classic-control", project="gymnasium",
         request="The classic-control environments (the Python files in gymnasium/envs/classic_control) "
                 "and gymnasium/envs/registration.py, nothing else.",
         expected=lambda r: [f for f in files(r, "gymnasium/envs/classic_control") if f.endswith(".py")]
                            + ["gymnasium/envs/registration.py"],
         why_hard="The folder is inside a skipped envs/ folder.", source="hand-written",
         reference="{ ls gymnasium/envs/classic_control/*.py; echo gymnasium/envs/registration.py; } "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="gym-python-no-tests", project="gymnasium",
         request="Every Python file in the repository except those in tests/ and docs/.",
         expected=lambda r: [f for f in files(r) if f.endswith(".py")
                             and not f.startswith(("tests/", "docs/"))],
         why_hard="env* drops gymnasium/envs; Markdown, YAML and the docs scripts must stay out.",
         source="hand-written",
         reference="find . -name '*.py' -not -path './tests/*' -not -path './docs/*' -not -path './.git/*' "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="gym-docker", project="gymnasium",
         request="The two Dockerfiles in bin/ and the docker entrypoint script there.",
         expected=lambda r: ["bin/all-py.Dockerfile", "bin/docker_entrypoint", "bin/necessary-py.Dockerfile"],
         why_hard="*.Dockerfile is not a default type (only extensionless Dockerfile is).",
         source="hand-written", reference="code2pdf -a bin --include '*.Dockerfile' -o {out}"),

    dict(id="alamo-source", project="alamofire",
         request="Alamofire's library source: every Swift file in Source/, plus the package manifests "
                 "(Package.swift and the Package@swift-*.swift variants). Nothing else.",
         expected=lambda r: [f for f in files(r, "Source") if f.endswith(".swift")]
                            + [f for f in files(r) if "/" not in f and f.startswith("Package") and f.endswith(".swift")],
         why_hard="The default selection is dominated by 328 generated HTML pages in docs/.",
         source="production: generated docs swamp a Swift package's selection",
         reference="{ find Source -name '*.swift'; ls Package*.swift; } | code2pdf --files-from - -o {out}"),
    dict(id="alamo-all-swift", project="alamofire",
         request="All the Swift code in the repository (library, tests and both example apps), but "
                 "nothing from the generated docs/ folder.",
         expected=lambda r: [f for f in files(r) if f.endswith(".swift") and not f.startswith("docs/")],
         why_hard="Folder names with spaces (watchOS Example); a hidden .swiftpm folder holds no Swift.",
         source="hand-written",
         reference="code2pdf -a . --include-types swift --exclude docs -o {out}"),
    dict(id="alamo-test-plans", project="alamofire",
         request="The Xcode test plans (the .xctestplan files) and the Swift files in Tests/.",
         expected=lambda r: [f for f in files(r) if f.endswith(".xctestplan")]
                            + [f for f in files(r, "Tests") if f.endswith(".swift")],
         why_hard="xctestplan is not a default type and lives in 'Tests/Test Plans' (a space).",
         source="hand-written",
         reference="code2pdf -a . --include-types swift,xctestplan --exclude Source --exclude Example "
                   "--exclude 'watchOS Example' --exclude docs --exclude 'Package*' --exclude '*.xcodeproj' -o {out}"),

    dict(id="gin-root-package", project="gin",
         request="gin's top-level package only: the .go files directly in the repository root, "
                 "without tests. No subpackages.",
         expected=_gin_root,
         why_hard="No depth option: subfolders (binding/, render/, internal/, ginS/) must be cut.",
         source="hand-written",
         reference="ls *.go | grep -v '_test.go$' | code2pdf --files-from - -o {out}"),
    dict(id="gin-no-tests", project="gin",
         request="All the Go code except tests (*_test.go) and except anything in testdata/.",
         expected=lambda r: [f for f in files(r) if f.endswith(".go") and not f.endswith("_test.go")
                             and not f.startswith("testdata/")],
         why_hard="Generated protobuf in testdata/ must go; markdown and yml must stay out.",
         source="hand-written",
         reference="code2pdf -a . --include-types go --exclude '*_test.go' --exclude testdata -o {out}"),
    dict(id="gin-render-binding", project="gin",
         request="The render and binding packages including their tests, plus the templates in testdata/template.",
         expected=lambda r: files(r, "binding") + files(r, "render") + files(r, "testdata/template"),
         why_hard=".tmpl is not a default type; three folders.", source="hand-written",
         reference="find binding render testdata/template -type f | code2pdf --files-from - -o {out}"),

    dict(id="express-examples-js", project="express",
         request="Every .js file under examples/, including the browser scripts in public/ folders, "
                 "and nothing else.",
         expected=lambda r: [f for f in files(r, "examples") if f.endswith(".js")],
         why_hard="Views (.ejs, .hbs, .html), CSS, Markdown and text files sit next to the code.",
         source="hand-written", reference="code2pdf -a examples --include-types js -o {out}"),
    dict(id="express-lib-router", project="express",
         request="lib/ first, in the usual sorted order, then test/Router.js and test/Route.js, in that order.",
         expected=lambda r: [f for f in files(r, "lib") if f.endswith(".js")] + ["test/Router.js", "test/Route.js"],
         ordered=True, why_hard="An order the directory walk can't give.", source="hand-written",
         reference="{ code2pdf -a lib --list-files | sed 's|^|lib/|'; echo test/Router.js; echo test/Route.js; } "
                   "| code2pdf --files-from - -o {out}"),

    dict(id="flask-tutorial-order", project="flask",
         request="The tutorial (the .rst files in docs/tutorial) in reading order: docs/tutorial/index.rst "
                 "first, then the chapters in the order of its table of contents.",
         expected=lambda r: ["docs/tutorial/index.rst"] + toctree(r, "docs/tutorial/index.rst"),
         ordered=True, why_hard="The order comes from reading index.rst's toctree.",
         source="hand-written (reading docs on paper)",
         reference="{ echo docs/tutorial/index.rst; sed -n '/toctree/,$p' docs/tutorial/index.rst | "
                   "grep -E '^ +[a-z]+$' | sed 's|^ *|docs/tutorial/|; s|$|.rst|'; } | code2pdf --files-from - -o {out}"),
    dict(id="flask-release-diff", project="flask", setup={"previous": "flask-3.0.2"},
         request="Print the files changed in the last commit (it is the 3.0.3 release). Leave out "
                 "images, and deleted files obviously can't be printed.",
         expected=lambda r: [f for f in git_lines(r, "diff", "--name-only", "--diff-filter=d", "HEAD~1", "HEAD")
                             if not f.lower().endswith(IMAGE) and is_text(r, f)],
         why_hard="Many changed files, several hidden (.github, .devcontainer, .editorconfig), "
                  "renames and deletions.", source="hand-written (review a release on paper)",
         reference="git diff --name-only --diff-filter=d HEAD~1 HEAD | grep -viE '\\.(png|gif|jpe?g|svg|ico)$' "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="flask-package-tests", project="flask",
         request="The Python code of the flask package (src/flask) and every Python file under tests/, "
                 "nothing else.",
         expected=lambda r: [f for f in files(r, "src/flask") if f.endswith(".py")]
                            + [f for f in files(r, "tests") if f.endswith(".py")],
         why_hard="Markdown, py.typed, templates and static files sit in the same folders.",
         source="hand-written",
         reference="find src/flask tests -name '*.py' | code2pdf --files-from - -o {out}"),
]
