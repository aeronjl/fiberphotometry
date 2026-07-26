# Grouped multiverse report v0.1

Multiverse results can contain estimates with incompatible units. A subtractive
delta-F estimate and a divisive delta-F/F estimate may both be defensible, but their
magnitudes, medians, and direction fractions must not be pooled.

`MultiverseReportGroup` makes that boundary executable:

```python
from fiberphotometry import MultiverseReportGroup

groups = (
    MultiverseReportGroup.from_choice(
        result,
        name="Divisive normalization",
        units="ΔF/F",
        node="normalization_window",
        alternatives=("divide_standard", "divide_early", "divide_displaced_baseline"),
    ),
    MultiverseReportGroup.from_choice(
        result,
        name="Subtractive normalization",
        units="acquired fluorescence",
        node="normalization_window",
        alternatives=(
            "subtract_standard",
            "subtract_early",
            "subtract_displaced_baseline",
        ),
    ),
)
result.write_grouped_html("robustness.html", groups)
```

The renderer refuses to proceed unless every compatible universe belongs to
exactly one group. Overlaps, omissions, unknown IDs, and attempts to assign an
incompatible universe are errors. Each evidence lane calculates its own estimate
range and success/failure/blocked counts. No pooled multiverse summary is displayed.

Failed lanes receive an explicit empty state and amber limitation edge. Declared
incompatibilities remain in a separate ledger, while the complete compatible
ledger retains estimates, intervals, choices, failures, and blocking reasons.

The report is self-contained, accessible, printable, and follows the persistent
[interface system](../.interface-design/system.md).
