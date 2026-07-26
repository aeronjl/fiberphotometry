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

## Local checks

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

