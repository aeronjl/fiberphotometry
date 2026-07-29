# Formative usability study v0.1 — materials only

> **This study has not been run.** Zero participant sessions have taken place and
> no results exist. Everything below is the frozen study *design*.

The study is intended to ask whether a practicing photometry scientist can
correctly interpret FiberPhotometry's evidence report without help. It would be a
product test, not an evaluation of the participant and not evidence that the
underlying synthetic scientific result is true.

## Study package

- [`protocol-v0.1.md`](protocol-v0.1.md): recruitment, procedure, measures, and
  frozen success criteria.
- [`moderator-guide-v0.1.md`](moderator-guide-v0.1.md): neutral script and task
  prompts.
- [`response-sheet-v0.1.md`](response-sheet-v0.1.md): one copy per participant.
- [`scoring-key-v0.1.md`](scoring-key-v0.1.md): expected answers and error coding;
  keep this hidden during sessions.
- [`https://github.com/aeronjl/fiberphotometry/blob/main/examples/grouped_multiverse_report.py`](https://github.com/aeronjl/fiberphotometry/blob/main/examples/grouped_multiverse_report.py):
  deterministic illustrative stimulus generator.

Generate the frozen stimulus from the repository root:

```bash
uv run python examples/grouped_multiverse_report.py
```

This writes `usability-study-report.html` into the working directory. The frozen
copy committed to the repository is
[`docs/usability/usability-study-stimulus.html`](../../docs/usability/usability-study-stimulus.html);
it is the *stimulus*, not a report of study findings. Its outcomes are fixed
interface fixtures, not results from a scientific benchmark. Give participants only
the HTML stimulus, not the source, protocol, or scoring key. Record the current
commit and SHA-256 of the HTML in each response sheet so every session is traceable
to the exact stimulus.

The materials being complete does **not** complete the roadmap usability review.
That milestone requires sessions with practicing photometry scientists and a
published, de-identified synthesis including retained failures. Neither has
happened.
