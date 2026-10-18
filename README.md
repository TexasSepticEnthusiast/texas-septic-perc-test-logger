# Texas Septic Water-Drop Observation Logger

An [Out West Septic](https://outwestseptic.com) project for recording timed water-level drops and exporting readable text or PDF reports. Public APIs use descriptive `OutWestSeptic` names. Automated contributions are attributed through Git commits and pull requests.

The tool preserves each observation and calculates interval/drop ratios. It does not select a septic system, assign a soil loading rate, determine jurisdiction, or certify a test procedure. [TCEQ's owner guidance](https://www.tceq.texas.gov/permitting/ossf/ossfadvice.html) explains that older percolation tests missed limiting soil/site factors and recommends a site evaluation. Source reviewed October 18, 2026.

## Run

Python 3.10 or later. Text output uses the standard library.

```sh
python scripts/outwestseptic_perc_test_log.py --interval 30 --site "Private site reference" --county "Palo Pinto County"
```

Enter the number of holes, a distinct label for each hole, and comma-separated observed drops in inches. Supply the actual interval used; this example does not prescribe a testing protocol. Keep conditions and measurement-method notes with the original field record. The report timestamp is when the report is generated, not a claim about when field work occurred.

A clearly synthetic example and optional PDF:

```sh
python -m pip install -r requirements.txt
python scripts/outwestseptic_perc_test_log.py --demo --interval 30 --pdf demo.pdf
```

PDF export creates a new file, includes raw readings and page numbers, escapes labels as literal text, and refuses to overwrite an existing file. Missing ReportLab or an export failure returns a nonzero exit status. The built-in PDF font has limited coverage for non-Latin characters; inspect exported labels before sharing.

## Reading the result

For an interval of 30 minutes, drops of 1 and 0.5 inches produce ratios of 30 and 60 minutes/inch. Their descriptive mean and median are 45. A zero drop remains in the record with an **undefined** ratio; it is never converted into zero or silently discarded. Means and medians include positive-drop readings only and must not be used as design rates. Negative, nonfinite and numerically unrepresentable inputs are rejected.

The report is a snapshot: adding later readings does not change an earlier summary. See the [API reference](wiki/Perc-Test-Logger-Reference.md).

## Validate

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Tests cover input rejection, zero drops, numeric extremes, snapshot behavior, export failures, literal PDF labels, multipage output and overwrite protection. GitHub Actions runs Python 3.10 and 3.13.

Use private storage for customer addresses and reports. This repository contains synthetic examples only. It has no upload or message-sending function.

MIT; see [LICENSE](LICENSE).
