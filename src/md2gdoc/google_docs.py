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
            text = ("\u000b" if inline.hard else " ") if isinstance(inline, ir.LineBreak) else inline.text
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
    # Applying a named paragraph style can reset inline formatting in Google Docs.
    requests.sort(key=lambda request: "updateTextStyle" in request)
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


def create_document(service, document: ir.Document, title: str, *, drive=None, folder_id=None, on_created=None) -> dict:
    requests = build_requests(document)
    if folder_id:
        identifier = drive.files().create(body={"name": title, "mimeType": GOOGLE_DOC_MIME,
                                               "parents": [folder_id]}, fields="id", supportsAllDrives=True).execute()["id"]
    else:
        identifier = service.documents().create(body={"title": title}).execute()["documentId"]
    try:
        if on_created:
            on_created(identifier)
        if requests:
            service.documents().batchUpdate(documentId=identifier, body={"requests": requests}).execute()
    except Exception as error:
        raise RuntimeError(f"Created Google Doc {identifier}, but formatting failed; inspect it before retrying: {error}") from error
    return _read_created(service, identifier)


def import_docx(drive, docs, path: Path, title: str, *, folder_id=None, on_created=None) -> dict:
    from googleapiclient.http import MediaFileUpload

    formats = drive.about().get(fields="importFormats").execute().get("importFormats", {})
    if GOOGLE_DOC_MIME not in formats.get(DOCX_MIME, []):
        raise ValueError("This Drive connection does not advertise DOCX-to-Google-Docs import.")
    body = {"name": title, "mimeType": GOOGLE_DOC_MIME}
    if folder_id:
        body["parents"] = [folder_id]
    uploaded = drive.files().create(
        body=body,
        media_body=MediaFileUpload(str(path), mimetype=DOCX_MIME),
        fields="id",
        **({"supportsAllDrives": True} if folder_id else {}),
    ).execute()
    if on_created:
        try:
            on_created(uploaded["id"])
        except OSError as error:
            raise RuntimeError(f"Created Google Doc {uploaded['id']}, but recording its ID failed: {error}") from error
    return _read_created(docs, uploaded["id"])


def _has_suggestions(value):
    if isinstance(value, dict):
        return any((key.startswith("suggested") and item) or _has_suggestions(item) for key, item in value.items())
    return isinstance(value, list) and any(_has_suggestions(item) for item in value)


def build_update_body(document: ir.Document, current: dict, expected_revision: str | None = None) -> dict:
    """Replace a single text-only body atomically; never use unguarded DOCX overwrite."""
    requests = build_requests(document)
    revision = current.get("revisionId")
    if not revision or (expected_revision is not None and revision != expected_revision):
        raise ValueError("Missing or changed Google revision; read and review the document again.")
    tabs = current.get("tabs") or []
    if len(tabs) > 1 or any(tab.get("childTabs") for tab in tabs):
        raise ValueError("Updates require a single-tab document.")
    context = tabs[0].get("documentTab", tabs[0]) if tabs else current
    tab_id = (tabs[0].get("tabProperties", {}).get("tabId") or tabs[0].get("tabId")) if tabs else None
    if tabs and not tab_id:
        raise ValueError("Missing target tab ID.")
    content = (context.get("body") or {}).get("content", [])
    if not content or not isinstance(content[-1].get("endIndex"), int):
        raise ValueError("Missing document body indexes; refusing replacement.")
    if _has_suggestions(current) or any(context.get(key) for key in
            ("headers", "footers", "footnotes", "inlineObjects", "positionedObjects")):
        raise ValueError("Updates cannot replace documents containing assets, headers, footnotes, or suggestions.")
    for element in content:
        if "sectionBreak" in element and element.get("endIndex") == 1:
            continue
        paragraph = element.get("paragraph")
        if paragraph is None or "bullet" in paragraph or any("textRun" not in e for e in paragraph.get("elements", [])):
            raise ValueError("Updates support existing text/code documents only; create a new Doc for structural content.")
    end = content[-1]["endIndex"] - 1
    if end < 1:
        raise ValueError("Invalid document body end index.")
    prefix = [{"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end}}}] if end > 1 else []
    # Reset the surviving final paragraph before insertion so old styles cannot leak.
    prefix.extend([
        {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 2}, "textStyle": {}, "fields": "*"}},
        {"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": 2},
                                  "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "*"}},
    ])
    requests = prefix + requests
    if tab_id:
        for request in requests:
            operation = next(iter(request.values()))
            operation.get("range", operation.get("location"))["tabId"] = tab_id
    return {"requests": requests, "writeControl": {"requiredRevisionId": revision}}


def update_document(service, identifier: str, body: dict) -> dict:
    if not body.get("writeControl", {}).get("requiredRevisionId"):
        raise ValueError("Updates require a requiredRevisionId guard.")
    try:
        result = service.documents().batchUpdate(documentId=identifier, body=body).execute()
        remote = service.documents().get(documentId=identifier, includeTabsContent=True).execute()
        revision = result.get("writeControl", {}).get("requiredRevisionId")
        if not revision or remote.get("revisionId") != revision:
            raise ValueError("Document changed before read-back, or the write revision is missing.")
        return remote
    except Exception as error:
        raise RuntimeError(f"Update of Google Doc {identifier} was not verified; inspect it before retrying: {error}") from error


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
