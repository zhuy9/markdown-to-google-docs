from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from docx import Document

from md2gdoc.parser import parse_markdown
from md2gdoc.renderer import render_docx
from md2gdoc.validator import validate_docx, validate_google


class ValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def test_valid_document_passes_and_literal_markdown_in_code_is_not_leakage(self):
        source = parse_markdown('# Title\n\n[Link](https://example.com/)\n\n```text\n![literal](image.png)\n```')
        output = self.directory / "valid.docx"
        render_docx(source, output, base_dir=self.directory)
        report = validate_docx(source, output)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["scope"], "local-docx")
        self.assertTrue(report["checks"]["code_formatting"])

    def test_missing_repeated_paragraph_is_detected(self):
        source = parse_markdown("Same paragraph\n\nSame paragraph")
        output = self.directory / "missing.docx"
        render_docx(source, output, base_dir=self.directory)
        document = Document(output)
        paragraph = document.paragraphs[-1]._p
        paragraph.getparent().remove(paragraph)
        document.save(output)
        self.assertFalse(validate_docx(source, output)["checks"]["text_preserved"])

    def test_lost_code_shading_is_detected(self):
        source = parse_markdown("```\ncode\n```")
        output = self.directory / "code.docx"
        render_docx(source, output, base_dir=self.directory)
        document = Document(output)
        shading = document.paragraphs[0]._p.xpath("./w:pPr/w:shd")[0]
        shading.getparent().remove(shading)
        document.save(output)
        self.assertFalse(validate_docx(source, output)["checks"]["code_formatting"])

    def test_missing_images_and_failed_mermaid_are_not_reported_as_success(self):
        source = parse_markdown("![Missing](missing.png)")
        output = self.directory / "image.docx"
        render_docx(source, output, base_dir=self.directory)
        report = validate_docx(source, output)
        self.assertFalse(report["ok"])
        self.assertEqual(report["counts"]["images"], {"expected": 1, "actual": 0})

    def test_google_readback_checks_actual_heading_and_links(self):
        source = parse_markdown("# Title\n\n[Link](https://example.com/)")
        body = {"content": [
            {"paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_1"}, "elements": [{"textRun": {"content": "Title\n"}}]}},
            {"paragraph": {"elements": [{"textRun": {"content": "Link\n", "textStyle": {"link": {"url": "https://example.com/"}}}}]}},
        ]}
        document = {"tabs": [{"documentTab": {"body": body}}]}
        self.assertTrue(validate_google(source, document)["ok"])
        body["content"][0]["paragraph"]["paragraphStyle"] = {}
        self.assertFalse(validate_google(source, document)["ok"])


if __name__ == "__main__":
    unittest.main()
