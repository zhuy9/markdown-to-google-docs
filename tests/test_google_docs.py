import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from md2gdoc.google_docs import DOCX_MIME, GOOGLE_DOC_MIME, build_requests, create_document, import_docx, utf16_length
from md2gdoc.parser import parse_markdown


class GoogleDocsTests(unittest.TestCase):
    def test_failed_formatting_keeps_id_and_does_not_retry(self):
        service = Mock()
        documents = service.documents.return_value
        documents.create.return_value.execute.return_value = {"documentId": "synthetic-id"}
        documents.batchUpdate.return_value.execute.side_effect = RuntimeError("timeout")
        with self.assertRaisesRegex(RuntimeError, "synthetic-id"):
            create_document(service, parse_markdown("text"), "Title")
        documents.create.assert_called_once()
        documents.get.assert_not_called()

    def test_import_checks_capability_before_upload(self):
        drive = Mock()
        drive.about.return_value.get.return_value.execute.return_value = {"importFormats": {}}
        with self.assertRaisesRegex(ValueError, "does not advertise"):
            import_docx(drive, Mock(), Path("unused.docx"), "Title")
        drive.files.assert_not_called()

    @patch("googleapiclient.http.MediaFileUpload")
    def test_import_uses_binary_media_and_reads_returned_id(self, media):
        drive, docs = Mock(), Mock()
        drive.about.return_value.get.return_value.execute.return_value = {"importFormats": {DOCX_MIME: [GOOGLE_DOC_MIME]}}
        drive.files.return_value.create.return_value.execute.return_value = {"id": "imported-id"}
        docs.documents.return_value.get.return_value.execute.side_effect = RuntimeError("timeout")
        with self.assertRaisesRegex(RuntimeError, "imported-id.*read-back failed"):
            import_docx(drive, docs, Path("fixture.docx"), "Title")
        media.assert_called_once_with("fixture.docx", mimetype=DOCX_MIME)
        drive.files.return_value.create.assert_called_once_with(
            body={"name": "Title", "mimeType": GOOGLE_DOC_MIME}, media_body=media.return_value, fields="id")

    def test_utf16_and_heading_ranges(self):
        document = parse_markdown("# 😀\n\n**bold** and [link](https://example.com/)")
        requests = build_requests(document)
        self.assertEqual(requests[0], {"insertText": {"location": {"index": 1}, "text": "😀\nbold and link\n"}})
        self.assertEqual(utf16_length("A😀B"), 4)
        heading = next(request["updateParagraphStyle"] for request in requests if "updateParagraphStyle" in request)
        self.assertEqual(heading["range"], {"startIndex": 1, "endIndex": 4})
        self.assertEqual(heading["paragraphStyle"]["namedStyleType"], "HEADING_1")
        bold = next(request["updateTextStyle"] for request in requests if request.get("updateTextStyle", {}).get("textStyle", {}).get("bold"))
        self.assertEqual(bold["range"], {"startIndex": 4, "endIndex": 8})
        link = next(request["updateTextStyle"] for request in requests if request.get("updateTextStyle", {}).get("textStyle", {}).get("link"))
        self.assertEqual(link["range"], {"startIndex": 13, "endIndex": 17})
        self.assertEqual(link["textStyle"]["link"]["url"], "https://example.com/")

    def test_empty_document_has_no_empty_insert(self):
        self.assertEqual(build_requests(parse_markdown("")), [])

    def test_complex_documents_use_docx_import_before_any_mutation(self):
        service = Mock()
        with self.assertRaisesRegex(ValueError, "DOCX"):
            create_document(service, parse_markdown("| H |\n| --- |\n| C |"), "Table")
        service.documents.assert_not_called()

    def test_create_applies_plan_and_reads_back_without_retries(self):
        service = Mock()
        documents = service.documents.return_value
        documents.create.return_value.execute.return_value = {"documentId": "synthetic-id"}
        documents.get.return_value.execute.return_value = {"documentId": "synthetic-id", "tabs": []}
        result = create_document(service, parse_markdown("# Title"), "Title")
        self.assertEqual(result["documentId"], "synthetic-id")
        documents.create.assert_called_once_with(body={"title": "Title"})
        documents.batchUpdate.assert_called_once()
        documents.get.assert_called_once_with(documentId="synthetic-id", includeTabsContent=True)


if __name__ == "__main__":
    unittest.main()
