import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class CLITests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.input = self.directory / "source.md"
        self.output = self.directory / "output.docx"

    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "md2gdoc", str(self.input), "-o", str(self.output), *arguments],
                              capture_output=True, text=True)

    def test_docx_and_machine_readable_report(self):
        self.input.write_text("# CLI test\n\n**Bold** text.", encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.output.is_file())
        report = json.loads(self.output.with_suffix(".report.json").read_text())
        self.assertTrue(report["ok"])
        self.assertEqual(report["scope"], "local-docx")
        self.assertNotIn("google_url", report)

    def test_missing_asset_writes_artifact_but_exits_nonzero(self):
        self.input.write_text("![missing](missing.png)")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.output.with_suffix(".report.json").read_text())
        self.assertFalse(report["ok"])
        self.assertEqual(report["warnings"][0]["code"], "image_unavailable")

    def test_input_cannot_be_overwritten(self):
        self.input.write_text("Keep this source")
        self.output = self.input
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.input.read_text(), "Keep this source")

    def test_google_plan_is_not_claimed_as_live_validation(self):
        self.input.write_text("# Heading")
        self.output = self.directory / "requests.json"
        result = self.run_cli("--format", "google-requests")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(self.output.read_text())
        self.assertIn("requests", plan)
        report = json.loads(self.output.with_suffix(".report.json").read_text())
        self.assertEqual(report["scope"], "google-request-plan")


if __name__ == "__main__":
    unittest.main()
