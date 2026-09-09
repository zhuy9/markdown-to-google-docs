"""Google-specific request indexes, optional OAuth, and DOCX import."""

from pathlib import Path
import os

from . import models as ir


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def build_requests(document: ir.Document) -> list[dict]:
    """Build a new-document batch; use DOCX import for structural/asset content."""
    text_parts = []
    requests = []
    position = 1
    for block in document.blocks:
        if not isinstance(block, (ir.Heading, ir.Paragraph, ir.CodeBlock)):
            raise ValueError(f"Use DOCX import for {type(block).__name__} content.")
        inlines = (ir.TextSpan(block.text, code=True),) if isinstance(block, ir.CodeBlock) else block.inlines
        start = position
        for inline in inlines:
            if isinstance(inline, ir.Image):
                raise ValueError("Use DOCX import to embed images without public hosting.")
            text = ("\n" if inline.hard else " ") if isinstance(inline, ir.LineBreak) else inline.text
            end = position + utf16_length(text)
            style = {} if isinstance(inline, ir.LineBreak) else _text_style(inline)
            if style and end > position:
                requests.append({"updateTextStyle": {
                    "range": {"startIndex": position, "endIndex": end},
                    "textStyle": style, "fields": ",".join(style),
                }})
            text_parts.append(text)
            position = end
        text_parts.append("\n")
        position += 1
        requests.append({"updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": position},
            "paragraphStyle": {"namedStyleType": f"HEADING_{block.level}" if isinstance(block, ir.Heading) else "NORMAL_TEXT"},
            "fields": "namedStyleType",
        }})
    if not text_parts:
        return []
    return [{"insertText": {"location": {"index": 1}, "text": "".join(text_parts)}}] + requests


def _text_style(span: ir.TextSpan) -> dict:
    style = {}
    if span.bold:
        style["bold"] = True
    if span.italic:
        style["italic"] = True
    if span.link:
        style["link"] = {"url": span.link}
    if span.code:
        style["weightedFontFamily"] = {"fontFamily": "Courier New"}
        style["backgroundColor"] = {"color": {"rgbColor": {"red": 0.95, "green": 0.96, "blue": 0.97}}}
    return style


def _read_created(service, identifier: str) -> dict:
    try:
        return service.documents().get(documentId=identifier, includeTabsContent=True).execute()
    except Exception as error:
        raise RuntimeError(f"Created Google Doc {identifier}, but read-back failed; do not blindly retry creation: {error}") from error


def create_document(service, document: ir.Document, title: str) -> dict:
    requests = build_requests(document)
    created = service.documents().create(body={"title": title}).execute()
    identifier = created["documentId"]
    try:
        if requests:
            service.documents().batchUpdate(documentId=identifier, body={"requests": requests}).execute()
    except Exception as error:
        raise RuntimeError(f"Created Google Doc {identifier}, but formatting failed; inspect it before retrying: {error}") from error
    return _read_created(service, identifier)


def import_docx(drive, docs, path: Path, title: str) -> dict:
    from googleapiclient.http import MediaFileUpload

    formats = drive.about().get(fields="importFormats").execute().get("importFormats", {})
    if GOOGLE_DOC_MIME not in formats.get(DOCX_MIME, []):
        raise ValueError("This Drive connection does not advertise DOCX-to-Google-Docs import.")
    uploaded = drive.files().create(
        body={"name": title, "mimeType": GOOGLE_DOC_MIME},
        media_body=MediaFileUpload(str(path), mimetype=DOCX_MIME),
        fields="id",
    ).execute()
    return _read_created(docs, uploaded["id"])


def google_clients(credentials_path: Path | None, token_path: Path):
    """Authenticate only on explicit upload; keep each user's token local."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    credentials = Credentials.from_authorized_user_file(str(token_path), scopes) if token_path.is_file() else None
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if credentials_path is None:
                raise ValueError("First upload requires --credentials pointing to your Google desktop OAuth client JSON.")
            credentials = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes).run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(credentials.to_json())
    return (build("drive", "v3", credentials=credentials, cache_discovery=False),
            build("docs", "v1", credentials=credentials, cache_discovery=False))
