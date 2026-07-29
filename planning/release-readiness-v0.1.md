# v0.1 stabilization audit

Status: **internal stabilization passed; public-release gates remain** (26 July
2026).

## Boundary established

The package now distinguishes a small supported workflow surface from experimental
method families and merely importable internals. The primary scientist-facing JSON
is identified as `event_analysis_result` schema v1, nested coverage and time-course
records carry their own v1 markers, and the normative top-level JSON Schema ships
inside both wheel and source distributions.

The policy is prospective: compatibility commitments begin with the first
published `0.1.x` release. They do not retroactively call the current development
build stable or promote experimental preprocessing methods.

## Reproducibility and packaging audit

- Canonical bootstrap: `uv sync --all-extras --locked` on pinned Python 3.12.
- CI matrix: Python 3.11, 3.12, and 3.13 using the same lock and checks.
- Package build: hatchling produces wheel and source distribution.
- Installed contents: `py.typed` and the result JSON Schema occur in both release
  formats.
- Isolated wheel smoke test: import, installed version, packaged schema lookup, and
  `fiberphotometry --help` all execute outside the repository environment.
- Repository checks: Ruff lint/format, strict mypy, and the full pytest suite.
- Workflow syntax: `actionlint` passes.
- Secret history scan: Gitleaks scanned 151 commits with no findings.
- Locked dependency scan: OSV-Scanner found no known vulnerabilities.

The clean locked sync exposed and fixed one previously masked defect: importing a
pure cohort helper loaded the optional IBL client at module import time. The
optional dependency is now imported only by the script executable path, allowing
the core suite to run from its declared development environment.

## Tooling decisions

The existing uv lock, Ruff, mypy, pytest, hatchling, GitHub Actions, and colocated
Jujutsu/Git workflow are sufficient. This Python-only library does not need mise,
Node, containers, or another task runner. Adding them would duplicate native
dependency and command surfaces without improving reproducibility.

## Remaining public-release gates

1. Confirm the package name with likely users.
2. Run the five moderated usability sessions and address high-impact findings.
3. Exercise the supported API against the clean-release artifact during that
   study, then decide whether the prospective v0.1 boundary needs narrowing.
4. Publish the first beta and begin the documented deprecation clock.

External reproduction, contributor governance, and an archival DOI remain gates
for 1.0 rather than for an initial beta.
