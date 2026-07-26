# Contributing

FiberPhotometry is pre-alpha. Contributions are welcome, but additions to the
scientific API require more than a working implementation.

## Scientific method checklist

A proposed method should include:

1. a citation and a concise statement of its assumptions;
2. an explicit description of the estimand or transformation;
3. synthetic tests with known ground truth and at least one failure case;
4. comparison with an independent implementation where one exists;
5. preservation of inputs and a machine-readable provenance record;
6. documentation of the experimental unit and valid resampling level.

Methods with unresolved evidence can be included behind an experimental label,
but they should not become defaults.

## Decision transparency

Consequential choices about recommended methods, defaults, estimands, benchmark
interpretation and deprecation require a scientific decision record. See
[`docs/decisions/README.md`](docs/decisions/README.md) and start from its template.
Working proposals belong in `docs/drafts/`; they are not normative. Freeze benchmark
protocols separately before aggregate execution, then retain complete results even
when acceptance criteria fail.

## Local checks

```bash
uv sync --all-extras --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

`uv sync --all-extras --locked` is the canonical bootstrap command. CI runs the
same locked environment and non-mutating checks on Python 3.11–3.13. Before
changing a supported name or serialized field, read
[`docs/api-stability-v0.1.md`](docs/api-stability-v0.1.md) and
[`docs/artifact-schemas-v0.1.md`](docs/artifact-schemas-v0.1.md).
