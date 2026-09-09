"""Persist publication identity and refuse ambiguous or conflicting replacements."""

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from .google_docs import build_update_body, create_document, import_docx, update_document
from .validator import validate_google


def state_path(source: Path) -> Path:
    source = source.resolve()
    return source.with_suffix(source.suffix + ".gdoc.json")


def document_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Use a raw Google document/folder ID, not a URL or name.")
    return value


def _fingerprint(remote: dict) -> str:
    stable = {key: value for key, value in remote.items() if key not in ("revisionId", "url", "documentId")}
    return sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _save(path: Path, state: dict):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


@contextmanager
def _lock(path: Path):
    # ponytail: local per-source lock; after a process crash, inspect pending state before removing it.
    lock = path.with_suffix(".lock")
    try:
        with lock.open("x"):
            pass
    except FileExistsError as error:
        raise ValueError(f"Publication is locked: {lock}. Inspect any pending operation before removing a stale lock.") from error
    try:
        yield
    finally:
        lock.unlink()


def publish_document(drive, docs, document, output: Path, title: str, source: Path, *,
                     native=False, update=None, new=False, expected_revision=None, folder_id=None) -> dict:
    path = state_path(source)
    with _lock(path):
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(previous, dict) or (previous and previous.get("source") != str(source.resolve())):
            raise ValueError("Publication state belongs to another source or is malformed; inspect it before publishing.")
        if previous.get("status") == "pending" and not (new or expected_revision):
            raise ValueError("Previous publication is unverified. Inspect its document; use --expected-revision after review, or --new.")
        if folder_id:
            document_id(folder_id)
            folder = drive.files().get(fileId=folder_id, fields="id,mimeType,trashed,capabilities(canAddChildren)",
                                       supportsAllDrives=True).execute()
            if folder.get("id") != folder_id or folder.get("mimeType") != "application/vnd.google-apps.folder" or \
                    folder.get("trashed") or not folder.get("capabilities", {}).get("canAddChildren"):
                raise ValueError("Destination is not an accessible, writable Drive folder.")
        state = {"source": str(source.resolve()), "status": "pending", "document_id": None}
        if update is not None:
            identifier = document_id(update or previous.get("document_id") or "")
            before = docs.documents().get(documentId=identifier, includeTabsContent=True).execute()
            if before.get("documentId") != identifier:
                raise ValueError("Google returned a different document ID; refusing replacement.")
            if not expected_revision and previous.get("document_id") == identifier and \
                    previous.get("fingerprint") != _fingerprint(before):
                raise ValueError("Google Doc changed since publication. Review it before replacing; "
                                 f"its current --expected-revision is {before.get('revisionId')}.")
            body = build_update_body(document, before, expected_revision)
            state.update(document_id=identifier, revision_id=before["revisionId"])
            _save(path, state)
            remote = update_document(docs, identifier, body)
        else:
            _save(path, state)  # A timed-out create can succeed remotely without returning an ID.

            def created(identifier):
                state["document_id"] = document_id(identifier)
                _save(path, state)

            remote = (create_document(docs, document, title, drive=drive, folder_id=folder_id, on_created=created)
                      if native else import_docx(drive, docs, output, title, folder_id=folder_id, on_created=created))
        if remote.get("documentId") != state["document_id"]:
            raise ValueError("Read-back document ID does not match the publication target.")
        report = validate_google(document, remote)
        report.update(google_url=f"https://docs.google.com/document/d/{state['document_id']}/edit",
                      document_id=state["document_id"], publication_state=str(path),
                      action="updated" if update is not None else "created")
        if report["ok"]:
            state.update(status="verified", revision_id=remote.get("revisionId"), fingerprint=_fingerprint(remote))
            _save(path, state)
        return report
