# Observation logger reference

`OutWestSepticPercTestLogger(county)` stores observations. Call `add_reading(hole_id, drop_inches)`, then `hole_summary(hole_id, interval_minutes)` or `all_summaries(interval_minutes)`.

`OutWestSepticPercHoleSummary` contains immutable tuples of raw drops and ratios, plus descriptive positive-drop mean and median. Its constructor snapshots the raw observations and recomputes all derived values; legacy supplied ratios/statistics are not trusted. Zero drops have a ratio of `None`; if every drop is zero, mean and median are also `None`.

`OutWestSepticPercReport` renders the record as text. `_export_pdf(report, path)` is an internal export helper that raises on failure and refuses to overwrite files. The CLI reports failures with exit code 2; cancellation returns 130.

`PercHoleSummary` and `PercReport` remain aliases. The old `classify()` method now raises a migration error because its soil/system categories were unsupported. Old pass/fail thresholds and default observation interval were removed. Supply the actual interval explicitly.

Example:

```python
from scripts.outwestseptic_perc_test_log import OutWestSepticPercTestLogger

logger = OutWestSepticPercTestLogger("Palo Pinto County")
logger.add_reading("Synthetic A", 1.0)
logger.add_reading("Synthetic A", 0.0)
summary = logger.hole_summary("Synthetic A", 30)
assert summary.rates_min_per_in == (30.0, None)
```

These are observations, not a soil/site evaluation. Read [TCEQ's owner guidance](https://www.tceq.texas.gov/permitting/ossf/ossfadvice.html) and the [current OSSF rules index](https://www.tceq.texas.gov/rules/indxpdf.html). Follow the applicable authority and qualified evaluator's requirements.

Project affiliation: [Out West Septic](https://outwestseptic.com). No government endorsement or business licensing assertion is implied.
