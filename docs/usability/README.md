# Formative usability study v0.1

This study asks whether a practicing photometry scientist can correctly interpret
FiberPhotometry's evidence report without help. It is a product test, not an
evaluation of the participant and not evidence that the underlying synthetic
scientific result is true.

## Study package

- [`protocol-v0.1.md`](protocol-v0.1.md): recruitment, procedure, measures, and
  frozen success criteria.
- [`moderator-guide-v0.1.md`](moderator-guide-v0.1.md): neutral script and task
  prompts.
- [`response-sheet-v0.1.md`](response-sheet-v0.1.md): one copy per participant.
- [`scoring-key-v0.1.md`](scoring-key-v0.1.md): expected answers and error coding;
  keep this hidden during sessions.
- [`../../examples/grouped_multiverse_report.py`](../../examples/grouped_multiverse_report.py):
  deterministic illustrative stimulus generator.

Generate the frozen stimulus from the repository root:

```bash
uv run python examples/grouped_multiverse_report.py
```

This writes `usability-study-report.html`. Its outcomes are fixed interface
fixtures, not results from a scientific benchmark. Give participants only the HTML report,
not the source, protocol, or scoring key. Record the current commit and SHA-256 of
the HTML in each response sheet so every session is traceable to the exact stimulus.

The materials being complete does **not** complete the roadmap usability review.
That milestone requires sessions with practicing photometry scientists and a
published, de-identified synthesis including retained failures.
