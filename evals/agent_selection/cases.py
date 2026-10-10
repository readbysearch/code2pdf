"""Cases for the agent-selection eval: a user asks a coding agent, in plain words, for a PDF of
part of a project. The agent must produce the PDF with code2pdf.

Each case states everything the grader checks: which files end up in the PDF (and their order
when the request gives one), where the PDF goes, and that the project is left unchanged.
`expected` lists files relative to the project; `ordered` makes the order part of the check;
`match: "basename"` compares file names only (single-file PDFs are labelled with the path the
agent typed). `why_hard` says what a careful agent has to notice; `source` says where the case
comes from. `reference` is one working solution (run from the project folder; {out} is replaced
by the output path), used to prove each case is passable. It is never shown to the agent.
"""

SHOP_DEFAULT = [
    "Dockerfile", "Makefile", "README.md", "backend/api/__init__.py", "backend/api/auth.py",
    "backend/api/routes.py", "backend/api/routes_test.py", "backend/app.py",
    "backend/generated/orders_pb2.py", "backend/generated/products_pb2.py",
    "backend/migrations/001_init.sql", "backend/migrations/002_orders.sql",
    "backend/migrations/003_customers.sql", "backend/models.py", "backend/payments.py",
    "backend/tests/conftest.py", "backend/tests/test_models.py", "backend/tests/test_payments.py",
    "docker-compose.yml", "docs/api.md", "docs/design.md", "frontend/src/App.test.tsx",
    "frontend/src/App.tsx", "frontend/src/Cart.spec.tsx", "frontend/src/Cart.tsx",
    "frontend/src/api.ts", "frontend/src/styles.css", "frontend/vite.config.ts",
    "scripts/deploy.sh", "scripts/seed_db.py",
]
SHOP_TESTS = ["backend/api/routes_test.py", "backend/tests/conftest.py", "backend/tests/test_models.py",
              "backend/tests/test_payments.py", "frontend/src/App.test.tsx", "frontend/src/Cart.spec.tsx"]
SHOP_BACKEND = ["backend/api/__init__.py", "backend/api/auth.py", "backend/api/routes.py",
                "backend/app.py", "backend/models.py", "backend/payments.py"]

ORBIT_DEFAULT = [
    "Orbit/Bridge/Legacy.h", "Orbit/Bridge/Legacy.m", "Orbit/Models/OrbitMath.swift",
    "Orbit/Models/Satellite.swift", "Orbit/OrbitApp.swift", "Orbit/Services/TLEClient.swift",
    "Orbit/ViewModels/HomeViewModel.swift", "Orbit/ViewModels/SettingsViewModel.swift",
    "Orbit/ViewModels/TrackingViewModel.swift", "Orbit/Views/HomeView.swift",
    "Orbit/Views/SatelliteRow.swift", "Orbit/Views/SettingsView.swift",
    "OrbitTests/OrbitMathTests.swift", "OrbitTests/SatelliteTests.swift",
    "OrbitUITests/LaunchTests.swift", "Podfile", "README.md", "Scripts/lint.sh",
    "fastlane/Appfile", "fastlane/Fastfile",
]
ORBIT_SWIFT = [
    "Orbit/Models/OrbitMath.swift", "Orbit/Models/Satellite.swift", "Orbit/OrbitApp.swift",
    "Orbit/Services/TLEClient.swift", "Orbit/ViewModels/HomeViewModel.swift",
    "Orbit/ViewModels/SettingsViewModel.swift", "Orbit/ViewModels/TrackingViewModel.swift",
    "Orbit/Views/HomeView.swift", "Orbit/Views/SatelliteRow.swift", "Orbit/Views/SettingsView.swift",
]

RIDGE_PACKAGE = [
    "src/ridge/__init__.py", "src/ridge/envs/__init__.py", "src/ridge/envs/cartpole.py",
    "src/ridge/envs/gridworld.py", "src/ridge/metrics.py", "src/ridge/model.py",
    "src/ridge/train.py", "src/ridge/utils/io.py", "src/ridge/utils/seed.py",
]

RELAY_DEFAULT = [
    "Makefile", "README.md", "api/relay.proto", "cmd/relay/main.go", "cmd/relayctl/main.go",
    "deploy/k8s/deployment.yaml", "deploy/k8s/service.yaml", "docs/adr/0001-use-grpc.md",
    "gen/relay.pb.go", "gen/relay_grpc.pb.go", "internal/legacy/v1.go", "internal/queue/queue.go",
    "internal/queue/queue_test.go", "internal/server/server.go", "internal/server/server_test.go",
    "lib/legacy/compat.go", "lib/retry/retry.go",
]
RELAY_GO = ["cmd/relay/main.go", "cmd/relayctl/main.go", "internal/legacy/v1.go",
            "internal/queue/queue.go", "internal/server/server.go", "lib/legacy/compat.go",
            "lib/retry/retry.go"]


def without(files, *removed):
    gone = {f for group in removed for f in ([group] if isinstance(group, str) else group)}
    return [f for f in files if f not in gone]


CASES = [
    # --- shop: Flask + React monorepo -------------------------------------------------------
    dict(id="shop-backend-code", project="shop",
         request="Print the backend's hand-written Python code: no tests and no generated code.",
         expected=SHOP_BACKEND,
         why_hard="Tests use two conventions (backend/tests/, *_test.py); generated protobuf code "
                  "lives in backend/generated/; the rest of the project must stay out.",
         source="hand-written", reference="code2pdf -a backend --include-types py --exclude tests "
                                           "--exclude '*_test.py' --exclude generated -o {out}"),
    dict(id="shop-trial", project="shop",
         request="Take code2pdf's normal selection for this project, but without any tests or "
                 "generated code, and skip the docs/ folder. I do want the CI workflow and the "
                 "files in config/ in there.",
         expected=without(SHOP_DEFAULT, SHOP_TESTS, "backend/generated/orders_pb2.py",
                          "backend/generated/products_pb2.py", "docs/api.md", "docs/design.md")
                  + [".github/workflows/ci.yml", "config/feature_flags.json", "config/settings.json"],
         why_hard="Tests use four conventions; the workflow is in a hidden folder; JSON is not a "
                  "default type; dependabot.yml is not a workflow.",
         source="agent trial (2026-10-10): JSON and folder includes were unclear from --help",
         reference="code2pdf -a . --exclude tests --exclude '*_test.py' --exclude '*.test.tsx' "
                   "--exclude '*.spec.tsx' --exclude generated --exclude docs "
                   "--include .github/workflows --include config -o {out}"),
    dict(id="shop-migrations", project="shop",
         request="Just the database migrations, oldest first.",
         expected=["backend/migrations/001_init.sql", "backend/migrations/002_orders.sql",
                   "backend/migrations/003_customers.sql"], ordered=True,
         why_hard="Order matters; nothing else may come along.",
         source="hand-written", reference="code2pdf -a backend/migrations -o {out}"),
    dict(id="shop-frontend", project="shop",
         request="The frontend: its source code plus package.json, tsconfig.json and vite.config.ts. "
                 "No tests, no node_modules, no images.",
         expected=["frontend/package.json", "frontend/src/App.tsx", "frontend/src/Cart.tsx",
                   "frontend/src/api.ts", "frontend/src/styles.css", "frontend/tsconfig.json",
                   "frontend/vite.config.ts"],
         why_hard="JSON is not a default type; tests use .test.tsx and .spec.tsx.",
         source="hand-written", reference="code2pdf -a frontend --include package.json --include "
                                           "tsconfig.json --exclude '*.test.tsx' --exclude '*.spec.tsx' -o {out}"),
    dict(id="shop-reading-order", project="shop",
         request="I want to read these in this order: backend/models.py, then backend/api/routes.py, "
                 "then frontend/src/api.ts, then frontend/src/Cart.tsx. Nothing else.",
         expected=["backend/models.py", "backend/api/routes.py", "frontend/src/api.ts",
                   "frontend/src/Cart.tsx"], ordered=True,
         why_hard="The order is not alphabetical, so the default walk can't produce it.",
         source="hand-written", reference="printf 'backend/models.py\\nbackend/api/routes.py\\n"
                                           "frontend/src/api.ts\\nfrontend/src/Cart.tsx\\n' | code2pdf --files-from - -o {out}"),
    dict(id="shop-last-commit", project="shop",
         setup={"commit": {"backend/payments.py": '"""Stripe payments, with refunds."""\n\n\ndef refund(order):\n    pass\n',
                           "backend/refunds.py": '"""Refund rules."""\n\nMAX_DAYS = 30\n',
                           "config/refund_policy.json": '{"max_days": 30}\n',
                           "docs/api.md": None,
                           "frontend/public/refund.png": b"\x89PNG\r\n\x1a\n\x00\x00"},
                "message": "Add refunds"},
         request="Print the files changed in the last commit. Skip images, and deleted files "
                 "obviously can't be printed.",
         expected=["backend/payments.py", "backend/refunds.py", "config/refund_policy.json"],
         why_hard="Needs git to find the files; the commit also deletes a file and adds an image; "
                  "JSON is not a default type.",
         source="hand-written (review a change on paper)",
         reference="git diff --name-only --diff-filter=d HEAD~1 HEAD | grep -v '\\.png$' | "
                   "code2pdf --files-from - -o {out}"),
    dict(id="shop-uncommitted", project="shop",
         setup={"edit": {"frontend/src/Cart.tsx": "export function Cart({ items }) {\n  return <ul>{items}</ul>\n}\n",
                         "frontend/src/Checkout.tsx": "export function Checkout() {\n  return <form />\n}\n",
                         "config/settings.json": '{"currency": "EUR", "tax_rate": 0.2}\n'}},
         request="Print what I'm working on: every file with uncommitted changes, including new "
                 "files I haven't added to git yet.",
         expected=["config/settings.json", "frontend/src/Cart.tsx", "frontend/src/Checkout.tsx"],
         why_hard="Needs git status, including untracked files; JSON is not a default type.",
         source="hand-written",
         reference="git status --porcelain | cut -c4- | code2pdf --files-from - -o {out}"),
    dict(id="shop-ops", project="shop",
         request="Print the ops files: the shell scripts, the Makefile, the Dockerfile, "
                 "docker-compose.yml and the GitHub Actions workflows.",
         expected=[".github/workflows/ci.yml", "Dockerfile", "Makefile", "docker-compose.yml",
                   "scripts/deploy.sh"],
         why_hard="Files of several types in several places, one in a hidden folder.",
         source="hand-written",
         reference="printf 'Dockerfile\\nMakefile\\ndocker-compose.yml\\nscripts/deploy.sh\\n.github/workflows/ci.yml\\n' "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="shop-dotfiles", project="shop",
         request="code2pdf's normal selection, plus the hidden config files at the top level "
                 "(.env.example and .editorconfig) and everything in .github.",
         expected=SHOP_DEFAULT + [".env.example", ".editorconfig", ".github/dependabot.yml",
                                  ".github/workflows/ci.yml"],
         why_hard="Hidden files and folders are skipped by default and must be named.",
         source="hand-written",
         reference="code2pdf -a . --include .env.example --include .editorconfig --include .github -o {out}"),
    dict(id="shop-json-config", project="shop",
         request="The backend's Python code (no tests, no generated code) together with the JSON "
                 "config files in config/.",
         expected=SHOP_BACKEND + ["config/feature_flags.json", "config/settings.json"],
         why_hard="Two folders; JSON is not a default type, so it silently goes missing.",
         source="agent trial (2026-10-10): JSON config silently left out",
         reference="{ code2pdf -a backend --include-types py --exclude tests --exclude '*_test.py' "
                   "--exclude generated --list-files | sed 's|^|backend/|'; ls config/*.json; } "
                   "| code2pdf --files-from - -o {out}"),

    # --- orbit: SwiftUI app -----------------------------------------------------------------
    dict(id="orbit-app-swift", project="orbit",
         request="Print the app's own Swift code, the Orbit/ folder, without tests, UI tests or CocoaPods.",
         expected=ORBIT_SWIFT,
         why_hard="The Objective-C bridge and Info.plist in Orbit/ must stay out.",
         source="production: ClaudeTerminal (Swift app) printed build output instead of its sources",
         reference="code2pdf -a Orbit --include-types swift -o {out}"),
    dict(id="orbit-build-scripts", project="orbit",
         request="Print the project as code2pdf normally would, but the scripts in Scripts/build "
                 "must be in it: they're ours, not build output. The top-level build/ folder is "
                 "real build output, so leave it out.",
         expected=ORBIT_DEFAULT + ["Scripts/build/bump_version.sh", "Scripts/build/export_archive.sh"],
         why_hard="Every folder named build is skipped by default; only one of the two is output.",
         source="production: default build/ skip added in v3.4 for Swift projects",
         reference="code2pdf -a . --include Scripts/build -o {out}"),
    dict(id="orbit-config", project="orbit",
         request="The Swift code in Orbit/, together with Orbit/Info.plist, the Podfile and the "
                 "fastlane files.",
         expected=ORBIT_SWIFT + ["Orbit/Info.plist", "Podfile", "fastlane/Appfile", "fastlane/Fastfile"],
         why_hard="plist is not a default type; Podfile.lock and the Objective-C files stay out.",
         source="hand-written",
         reference="{ find Orbit -name '*.swift'; echo Orbit/Info.plist; echo Podfile; ls fastlane/*; } "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="orbit-tests", project="orbit",
         request="Only the tests: unit tests and UI tests.",
         expected=["OrbitTests/OrbitMathTests.swift", "OrbitTests/SatelliteTests.swift",
                   "OrbitUITests/LaunchTests.swift"],
         why_hard="Two test folders.", source="hand-written",
         reference="find OrbitTests OrbitUITests -name '*.swift' | code2pdf --files-from - -o {out}"),
    dict(id="orbit-views", project="orbit",
         request="Everything under Orbit/Views, plus HomeViewModel.swift and SettingsViewModel.swift "
                 "(not TrackingViewModel).",
         expected=["Orbit/ViewModels/HomeViewModel.swift", "Orbit/ViewModels/SettingsViewModel.swift",
                   "Orbit/Views/HomeView.swift", "Orbit/Views/SatelliteRow.swift",
                   "Orbit/Views/SettingsView.swift"],
         why_hard="A folder plus two named files from another folder.", source="hand-written",
         reference="ls Orbit/Views/* Orbit/ViewModels/HomeViewModel.swift Orbit/ViewModels/SettingsViewModel.swift "
                   "| code2pdf --files-from - -o {out}"),

    # --- ridge: Python research repository --------------------------------------------------
    dict(id="ridge-package", project="ridge",
         request="Print the whole ridge package, src/ridge: every Python file in it.",
         expected=RIDGE_PACKAGE,
         why_hard="src/ridge/envs is skipped by the default env* folder rule, silently.",
         source="production: research repos with envs/ packages (med_mechanism_ridge style)",
         reference="code2pdf -a src/ridge --include envs -o {out}"),
    dict(id="ridge-python", project="ridge",
         request="All our Python code: src/, scripts/ and tests/, and nothing from venv/.",
         expected=RIDGE_PACKAGE + ["scripts/plot_results.py", "scripts/sweep.py",
                                   "tests/test_envs.py", "tests/test_model.py"],
         why_hard="env* skips src/ridge/envs; Markdown and YAML must stay out.",
         source="hand-written",
         reference="code2pdf -a . --include-types py --include src/ridge/envs --exclude venv -o {out}"),
    dict(id="ridge-experiments", project="ridge",
         request="The YAML configs in configs/ and the run script of every experiment, nothing else.",
         expected=["configs/base.yaml", "configs/large.yaml",
                   "experiments/2026-09-01-baseline/run.sh", "experiments/2026-09-15-large/run.sh"],
         why_hard="Notes next to the run scripts and the wandb config must stay out.",
         source="hand-written",
         reference="ls configs/*.yaml experiments/*/run.sh | code2pdf --files-from - -o {out}"),
    dict(id="ridge-notebooks", project="ridge",
         request="The package source (src/ridge) and the Jupyter notebooks.",
         expected=["notebooks/explore.ipynb", "notebooks/figures.ipynb"] + RIDGE_PACKAGE,
         why_hard="Notebooks are not a default type; env* skips src/ridge/envs.",
         source="hand-written",
         reference="{ find src/ridge -name '*.py'; ls notebooks/*.ipynb; } | code2pdf --files-from - -o {out}"),
    dict(id="ridge-mentions", project="ridge",
         request="Print every file that mentions ridge_penalty (code, configs, docs, anything) "
                 "except in venv/ and wandb/.",
         expected=["configs/base.yaml", "configs/large.yaml", "gen/report.md", "scripts/sweep.py",
                   "src/ridge/model.py", "src/ridge/train.py"],
         why_hard="Content search, then an exact file list.", source="hand-written",
         reference="grep -rl ridge_penalty --exclude-dir=venv --exclude-dir=wandb --exclude-dir=.git . "
                   "| code2pdf --files-from - -o {out}"),
    dict(id="ridge-one-file", project="ridge",
         request="Make a PDF of just src/ridge/envs/cartpole.py.",
         expected=["cartpole.py"], match="basename",
         why_hard="Single-file mode; the file has Chinese comments.", source="hand-written",
         reference="code2pdf -s src/ridge/envs/cartpole.py -o {out}"),

    # --- relay: Go service ------------------------------------------------------------------
    dict(id="relay-go-code", project="relay",
         request="All the Go code we wrote: no tests, nothing from vendor/, and no generated .pb.go files.",
         expected=RELAY_GO,
         why_hard="Three kinds of exclusion; vendor/ is skipped by default anyway.", source="hand-written",
         reference="code2pdf -a . --include-types go --exclude '*_test.go' --exclude '*.pb.go' -o {out}"),
    dict(id="relay-legacy", project="relay",
         request="code2pdf's normal selection, but leave out internal/legacy. Keep lib/legacy: "
                 "that one is still used.",
         expected=without(RELAY_DEFAULT, "internal/legacy/v1.go"),
         why_hard="--ignore-folders legacy would drop both folders of that name.",
         source="hand-written (motivated the path-aware --exclude in v3.9)",
         reference="code2pdf -a . --exclude internal/legacy -o {out}"),
    dict(id="relay-go-mod", project="relay",
         request="Our Go code (not vendor/, no tests, no generated files), plus go.mod and the proto file.",
         expected=RELAY_GO + ["api/relay.proto", "go.mod"],
         why_hard="go.mod is not a default type.", source="hand-written",
         reference="code2pdf -a . --include-types go,proto --include go.mod --exclude '*_test.go' "
                   "--exclude '*.pb.go' -o {out}"),
    dict(id="relay-deploy", project="relay",
         request="Only the deployment config: the Kubernetes manifests, the Terraform file and the Makefile.",
         expected=["Makefile", "deploy/k8s/deployment.yaml", "deploy/k8s/service.yaml",
                   "deploy/terraform/main.tf"],
         why_hard="Terraform (.tf) is not a default type.", source="hand-written",
         reference="{ echo Makefile; find deploy -type f; } | code2pdf --files-from - -o {out}"),
    dict(id="relay-order", project="relay",
         request="The Go files in internal/ and cmd/, without tests: all of internal/ first, then "
                 "cmd/, each in the usual sorted order.",
         expected=["internal/legacy/v1.go", "internal/queue/queue.go", "internal/server/server.go",
                   "cmd/relay/main.go", "cmd/relayctl/main.go"], ordered=True,
         why_hard="cmd/ sorts before internal/, so the default order is wrong.", source="hand-written",
         reference="{ code2pdf -a internal --exclude '*_test.go' --list-files | sed 's|^|internal/|'; "
                   "code2pdf -a cmd --list-files | sed 's|^|cmd/|'; } | code2pdf --files-from - -o {out}"),
    dict(id="relay-vendor-fork", project="relay",
         request="code2pdf's normal selection plus our vendored fork in vendor/github.com/acme/retry, "
                 "but no other vendored code.",
         expected=RELAY_DEFAULT + ["vendor/github.com/acme/retry/backoff.go",
                                   "vendor/github.com/acme/retry/retry.go"],
         why_hard="vendor/ is skipped by default; only one subfolder may come in.", source="hand-written",
         reference="code2pdf -a . --include vendor/github.com/acme/retry -o {out}"),
]

BY_ID = {case["id"]: case for case in CASES}
