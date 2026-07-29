# Report comprehension protocol v0.1

Status: frozen before the first participant session.

## Question

Can practicing fiber-photometry scientists use a standalone FiberPhotometry
robustness report to identify the scientific claim, unit boundaries, robustness,
failures, and provenance accurately and without moderator assistance?

## Participants

Recruit five formative participants who have independently analysed fiber
photometry data in the past two years. Seek variation in career stage, programming
experience, acquisition system, and preferred analysis workflow. A participant
must not have contributed to this report implementation. Five sessions identify
high-frequency comprehension failures; they do not establish population-level
usability or scientific validity.

Record only coarse, non-identifying background categories. Do not collect names,
institutions, unpublished results, or screen recordings unless separately needed
and explicitly consented to. Participation is voluntary and can stop at any time.

## Stimulus and setup

Use the frozen stimulus committed at
[`docs/usability/usability-study-stimulus.html`](../../docs/usability/usability-study-stimulus.html),
or regenerate it with the committed example, and record its Git commit and
SHA-256. The report contains deterministic illustrative outcomes so
the tested evidence states do not drift with analysis-engine changes; it is not a
scientific benchmark. Use a standard desktop browser at 100% zoom. The moderator
may explain that the data are synthetic, but must not explain report terminology,
navigation, colors, or intended conclusions before the tasks.

Use think-aloud observation. After each prompt, capture the answer, confidence on
a 1–5 scale, completion time, first location inspected, and any moderator help.
Do not correct an answer until all scored tasks are complete.

## Primary tasks

1. State the comparison, population aggregation unit, and analysis intent.
2. Decide whether the report supports a single pooled effect magnitude across all
   workflows, and explain why.
3. Describe whether the apparent direction is robust within each compatible unit
   family without claiming more than the report shows.
4. Find how many workflows succeeded, failed, were blocked, or were declared
   incompatible, then explain what happened to the failed workflow.
5. Recover the response-window and normalization choices for one named universe.

The moderator guide fixes the exact wording. The scoring key freezes acceptable
answers before data collection.

## Secondary task

Ask the participant what decision they would make next as the analyst and what
additional evidence they need. This is not scored for correctness; code responses
as requests for data/QC, unit-level evidence, method justification, inferential
evidence, or clearer report language.

## Measures and frozen success criteria

The v0.1 report passes formative review only if:

- at least four of five participants score at least 8/10 overall;
- all five reject pooling divisive and subtractive magnitudes;
- at least four correctly locate the failed and incompatible workflows;
- median unassisted completion time is at most eight minutes;
- no participant mistakes events or workflows for independent animals;
- no critical comprehension error recurs in two or more sessions.

A critical error is one that could reverse a scientific conclusion, pool
incommensurate units, hide a failed workflow, or misstate the population unit.
Moderator help makes that item assisted, even if the final answer is correct.

## Analysis and decision rule

Tabulate task-level accuracy, assistance, time, confidence, and observed path.
Report every critical error and all recurring non-critical errors. Do not average
confidence into accuracy. Qualitative comments may explain failure mechanisms but
cannot override the frozen thresholds.

If the report fails, create issues tied to observed errors, revise the interface,
increment the protocol/stimulus version, and repeat with new participants. Do not
silently change the stimulus or scoring key during a round. Publish a de-identified
summary whether the thresholds pass or fail.
