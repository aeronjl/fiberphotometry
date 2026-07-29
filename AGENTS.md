# Repository instructions

## Purpose

FiberPhotometry is a Python library for fiber photometry analysis. Scientific validity
and a small stable API take priority over method count. The core path is:

    ingest -> preprocess -> dF/F -> align -> summarise -> infer

Everything else is optional and must justify its place against that path.

## Workflow

- Use `uv` for Python, environments, dependencies, tools, and lockfiles.
- Support Python 3.11 and newer; keep `[tool.mypy] python_version` aligned with the
  minimum supported version, not the development one.
- Add dependencies with `uv add` or `uv add --dev` and commit `uv.lock`.
- Do not commit, push, publish, or configure a remote unless the user explicitly asks.

## Architecture

- Keep reusable library code in `src/fiberphotometry/`.
- Keep acquisition adapters optional; NWB, TDT, Doric, DANDI and pose formats are extras,
  never core dependencies.
- Prefer an established package over a reimplementation. Before writing pose handling,
  statistics, HMM inference, DDM fitting, file IO or posterior diagnostics, name the
  package that already does it and state why it is unsuitable.
- Emit and consume the community NWB data model (`ndx-fiber-photometry`). Do not invent
  a private schema, and never encode structured metadata into a free-text field.
- Keep paper-specific analyses outside `src/` and outside `docs/`.

## Hard rules

- **Every public name is classified `supported` or `experimental`.** There is no third
  state. CI fails if any `__all__` entry is unclassified.
- **A method is not done until it has all three of:** a runnable documentation example
  using data a reader can actually obtain; a correctness test against known ground truth,
  an analytic result, or a reference implementation; and an entry in the capability
  matrix. Features missing any of the three do not merge.
- **Self-consistency is not validation.** Numerical claims are checked against a reference
  implementation where one exists (statsmodels, scipy, pybaselines, GuPPy, PASTa, fastFMM).
  A test that asserts a function agrees with itself, or with a constant the code wrote,
  does not count.
- **Silent data loss is a bug.** Any operation that drops samples, events, trials or
  sessions records the count in the provenance record and warns.
- **No documentation filename carries a version suffix.** Version inside the document;
  history lives in git. Published URLs are stable.
- **Internal artefacts are not user documentation.** Decision records, drafts, roadmaps,
  release-readiness notes and one-off results write-ups live outside the published site.
- **Claims match code.** If a navigation label, README sentence or stability policy
  promises a capability, a test demonstrates it. Retract rather than soften.

## Scientific requirements

- Preserve the animal as the experimental unit in every aggregate estimate.
- Distinguish dF/F, baseline z-score and robust z explicitly; record which was used and
  name the units on every output.
- Keep preprocessing choices declared and replaceable rather than defaulted and hidden.
- Report failed gates and retain failed benchmarks. Never quietly reclassify a failure.
- Do not report an uncertainty interval whose coverage has not been measured.

## Validation

Before handing off changes, run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv build
```

CI additionally enforces: a core-dependencies-only import job, `--cov-fail-under`,
`-W error`, and a documentation build that fails on pages orphaned from the navigation.
