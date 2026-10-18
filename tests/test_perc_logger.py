import builtins
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import outwestseptic_perc_test_log as perc


class ObservationTests(unittest.TestCase):
    def logger(self, drops=(1, 0.5, 0)):
        logger = perc.OutWestSepticPercTestLogger("Hood County")
        for drop in drops:
            logger.add_reading("H1", drop)
        return logger

    def report(self, drops=(1, 0.5, 0), site="Synthetic & <b>literal</b>"):
        logger = self.logger(drops)
        return perc.OutWestSepticPercReport(
            site, logger.county, datetime(2026, 1, 1, tzinfo=timezone.utc), 30,
            logger.all_summaries(30),
        )

    def test_raw_readings_and_descriptive_ratios(self):
        summary = self.logger().hole_summary("H1", 30)
        self.assertEqual(summary.readings_in, (1, 0.5, 0))
        self.assertEqual(summary.rates_min_per_in, (30, 60, None))
        self.assertEqual(summary.average_rate, 45)
        self.assertEqual(summary.median_rate, 45)
        self.assertEqual(summary.zero_drop_count, 1)

    def test_zero_only_retained_without_fabricated_rate(self):
        summary = self.logger((0, 0)).hole_summary("H1", 30)
        self.assertIsNone(summary.average_rate)
        self.assertIsNone(summary.median_rate)
        self.assertEqual(summary.zero_drop_count, 2)

    def test_invalid_drops_rejected_without_modifying_store(self):
        logger = self.logger()
        for value in (-1, float("nan"), float("inf"), True, "oops", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                logger.add_reading("H1", value)
        self.assertEqual(len(logger.holes["H1"]), 3)

    def test_invalid_intervals_rejected(self):
        for interval in (-1, 0, float("nan"), float("inf"), True):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                self.logger().hole_summary("H1", interval)

    def test_ratio_overflow_and_underflow_rejected(self):
        for drop, interval in ((1e-300, 1e300), (1e300, 1e-300)):
            with self.subTest(drop=drop), self.assertRaises(ValueError):
                self.logger((drop,)).hole_summary("H1", interval)

    def test_large_finite_median_does_not_overflow(self):
        summary = self.logger((1, 1)).hole_summary("H1", 1e308)
        self.assertEqual(summary.median_rate, 1e308)

    def test_summary_is_a_snapshot(self):
        logger = self.logger()
        summary = logger.hole_summary("H1", 30)
        logger.add_reading("H1", 4)
        self.assertEqual(summary.readings_in, (1, 0.5, 0))

    def test_legacy_list_constructor_is_immutable_and_recalculates(self):
        readings, ratios = [1.0], [99.0]
        summary = perc.PercHoleSummary("H1", 30, readings, ratios, 99, 99)
        report = perc.PercReport("Synthetic", "Hood", datetime.now(), 30, [summary])
        readings.append(0.5)
        ratios.append(60)
        self.assertEqual(summary.readings_in, (1.0,))
        self.assertEqual(summary.rates_min_per_in, (30.0,))
        self.assertEqual(summary.average_rate, 30.0)
        self.assertIn("Readings: 1", report.render_text())

    def test_direct_summary_rejects_invalid_raw_values(self):
        for readings in ([], [float("nan")], [-1], None):
            with self.subTest(readings=readings), self.assertRaises(ValueError):
                perc.PercHoleSummary("H1", 30, readings)

    def test_hole_labels_and_missing_readings(self):
        for label in ("", " ", "a\nb", "x" * 201):
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.logger().add_reading(label, 1)
        with self.assertRaises(ValueError):
            self.logger().hole_summary("unknown", 30)

    def test_legacy_names_and_classification_migration(self):
        self.assertIs(perc.PercHoleSummary, perc.OutWestSepticPercHoleSummary)
        self.assertIs(perc.PercReport, perc.OutWestSepticPercReport)
        with self.assertRaisesRegex(ValueError, "classification has been removed"):
            self.logger().classify(15)

    def test_text_records_actual_county_and_raw_readings(self):
        text = self.report().render_text()
        self.assertIn("County: Hood County", text)
        self.assertIn("3: drop 0 in; ratio undefined", text)
        self.assertIn("positive-drop readings only", text)
        self.assertNotIn("Palo Pinto", text)
        self.assertNotIn("PASS", text)

    def test_report_rejects_mixed_intervals(self):
        with self.assertRaisesRegex(ValueError, "Every hole"):
            perc.PercReport("Synthetic", "Hood", datetime.now(), 5, self.logger().all_summaries(30))

    def test_cli_rejects_bad_interval_and_required_interval(self):
        with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
            self.assertEqual(perc.main(["--demo", "--interval", "-10"]), 2)
            with self.assertRaises(SystemExit) as caught:
                perc.main(["--demo"])
        self.assertEqual(caught.exception.code, 2)

    def test_cli_demo_is_explicitly_synthetic(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(perc.main(["--demo", "--interval", "30"]), 0)
        self.assertIn("SYNTHETIC DEMO", output.getvalue())

    def test_missing_pdf_dependency_is_an_error(self):
        original_import = builtins.__import__
        def without_reportlab(name, *args, **kwargs):
            if name.startswith("reportlab"):
                raise ImportError("simulated missing optional dependency")
            return original_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "report.pdf"
            with patch("builtins.__import__", side_effect=without_reportlab):
                with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                    self.assertEqual(perc.main(["--demo", "--interval", "30", "--pdf", str(destination)]), 2)
            self.assertFalse(destination.exists())

    def test_cli_export_failure_is_nonzero(self):
        with patch.object(perc, "_export_pdf", side_effect=PermissionError("not writable")):
            with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                self.assertEqual(perc.main(["--demo", "--interval", "30", "--pdf", "anything.pdf"]), 2)

    def test_interactive_rejects_duplicate_holes(self):
        with patch("builtins.input", side_effect=["2", "H1", "1,0", "H1"]):
            with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                self.assertEqual(perc.main(["--interval", "30"]), 2)


class PdfTests(unittest.TestCase):
    logger = ObservationTests.logger
    report = ObservationTests.report
    # These integration checks require the documented dev dependencies.
    def test_pdf_preserves_literal_markup_and_all_pages(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "report.pdf"
            report = self.report((1,) * 180 + (0,), site='<img src="https://invalid.example/image"> & field')
            self.assertTrue(perc._export_pdf(report, destination))
            reader = PdfReader(destination)
            self.assertGreater(len(reader.pages), 3)
            text = "\n".join(page.extract_text() for page in reader.pages)
            self.assertIn('<img src="https://invalid.example/image"> & field', text)
            self.assertIn("Hood County", text)
            self.assertIn("undefined", text)
            self.assertIn("181", text)
            for number, page in enumerate(reader.pages, 1):
                self.assertIn(f"Observation record - page {number}", page.extract_text())

    def test_pdf_will_not_clobber_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing.pdf"
            destination.write_bytes(b"keep existing customer file")
            with self.assertRaises(FileExistsError):
                perc._export_pdf(self.report(), destination)
            self.assertEqual(destination.read_bytes(), b"keep existing customer file")

    def test_pdf_cli_creates_valid_file(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "demo.pdf"
            with redirect_stdout(StringIO()):
                result = perc.main(["--demo", "--interval", "30", "--pdf", str(destination)])
            self.assertEqual(result, 0)
            self.assertGreater(len(PdfReader(destination).pages), 0)


if __name__ == "__main__":
    unittest.main()
