import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from md2gdoc.cli import main


class CLITests(unittest.TestCase):
    def test_dry_run_analyzes_without_side_effects(self):
        self.input.write_text('# Title\n\n```mermaid\ngraph LR\n A --> B\n```\n\n![missing](missing.png)')
        with patch("md2gdoc.cli.render_docx", side_effect=AssertionError("render")), \
             patch("md2gdoc.cli.google_clients", side_effect=AssertionError("auth")), \
             patch("md2gdoc.images.urlopen", side_effect=AssertionError("download")), \
             redirect_stdout(io.StringIO()) as stdout:
            status = main([str(self.input), '--dry-run', '--upload', '-o', str(self.output)])
        report = json.loads(stdout.getvalue())
        self.assertEqual(status, 1)
        self.assertEqual(report['scope'], 'source-analysis')
        self.assertEqual(report['counts']['mermaid'], 1)
        self.assertEqual(report['dependencies']['google_apis'], ['Docs', 'Drive'])
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.iterdir()), [self.input])

    def test_strict_warnings_block_upload_but_default_stays_compatible(self):
        self.input.write_text('<details>Literal</details>')
        with patch('md2gdoc.cli.google_clients', side_effect=AssertionError('auth')), redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.input), '-o', str(self.output), '--strict', '--upload']), 1)
        self.assertTrue(self.output.exists())
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.run_cli('--dry-run', '--strict').returncode, 1)

    def test_dry_run_remote_images_are_not_fetched_even_with_opt_in(self):
        self.input.write_text('![image](https://example.com/image.png)')
        with patch('md2gdoc.images.urlopen', side_effect=AssertionError('download')), redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main([str(self.input), '--dry-run', '--allow-remote-images']), 0)
        self.assertEqual(json.loads(stdout.getvalue())['dependencies']['remote_images'], 1)

    def test_update_rejects_complex_source_before_authentication(self):
        self.input.write_text('- List')
        with patch('md2gdoc.cli.google_clients', side_effect=AssertionError('auth')):
            self.assertEqual(main([str(self.input), '--upload', '--update', 'target-id']), 2)
        self.assertFalse(self.output.exists())

    def test_publication_and_credentials_cannot_be_overwritten_by_output(self):
        self.input.write_text('Keep')
        for name in ('source.md.gdoc.json', 'token.json'):
            target = self.directory / name
            target.write_text('Do not overwrite')
            self.output = target
            result = self.run_cli('--token', str(self.directory / 'token.json'))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), 'Do not overwrite')

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

    def test_mermaid_scale_reaches_the_renderer(self):
        self.input.write_text("# Title\n", encoding="utf-8")
        with patch("md2gdoc.cli.render_docx", return_value=()) as render:
            with patch("md2gdoc.cli.validate_docx", return_value={"ok": True}):
                main([str(self.input), "-o", str(self.output), "--mermaid-scale", "5"])
        self.assertEqual(render.call_args.kwargs["mermaid_renderer"].keywords, {"scale": 5})

    def test_mermaid_scale_rejects_values_the_cli_cannot_render(self):
        self.input.write_text("# Title\n", encoding="utf-8")
        result = self.run_cli("--mermaid-scale", "9")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--mermaid-scale", result.stderr)

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
