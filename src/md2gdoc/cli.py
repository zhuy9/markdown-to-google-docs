"""Command-line conversion, optional upload, and explicit validation reports."""

import argparse
from dataclasses import asdict
from functools import partial
import json
from pathlib import Path
import sys

from .google_docs import build_requests, google_clients
from .mermaid import render_mermaid
from .parser import parse_markdown
from .publishing import document_id, publish_document, state_path
from .renderer import render_docx
from .validator import analyze_document, validate_docx


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown to DOCX or Google Docs requests.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--format", choices=("docx", "google-requests"), default="docx")
    parser.add_argument("--title", help="Title for an uploaded Google Doc (default: input filename).")
    parser.add_argument("--allow-remote-images", action="store_true", help="Allow downloading HTTP(S) image references.")
    parser.add_argument("--mermaid-scale", type=int, choices=range(1, 6), default=3,
                        metavar="{1..5}", help="Mermaid pixel density; higher is sharper (default: 3).")
    parser.add_argument("--upload", action="store_true", help="Publish to Google using your own OAuth account.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--new", action="store_true", help="Explicitly create a new Doc, including after an ambiguous previous run.")
    mode.add_argument("--update", nargs="?", const="", metavar="DOCUMENT_ID",
                      help="Replace a text/code Doc; omit the ID to use the source's saved publication identity.")
    parser.add_argument("--expected-revision", help="Explicitly replace this reviewed revision after a detected conflict.")
    parser.add_argument("--folder-id", help="Destination Drive folder for new documents.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without rendering, downloading, authenticating, or writing files.")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings and prevent upload when content degrades.")
    parser.add_argument("--credentials", type=Path, help="Google desktop OAuth client JSON for first sign-in.")
    parser.add_argument("--token", type=Path, default=Path.home() / ".config/md2gdoc/token.json")
    args = parser.parse_args(argv)
    if (args.new or args.update is not None or args.folder_id) and not args.upload:
        parser.error("--new, --update, and --folder-id require --upload (which is inert with --dry-run).")
    if args.expected_revision and args.update is None:
        parser.error("--expected-revision requires --update.")
    if args.update is not None and (args.folder_id or args.title):
        parser.error("Updates preserve the document's title and folder; omit --title and --folder-id.")
    suffix = ".docx" if args.format == "docx" else ".requests.json"
    output = args.output or Path("output") / (args.input.stem + suffix)
    report_path = output.with_suffix(".report.json")
    paths = [args.input.resolve(), output.resolve(), report_path.resolve(), state_path(args.input),
             state_path(args.input).with_suffix(".lock"), args.token.resolve()]
    if args.credentials:
        paths.append(args.credentials.resolve())
    if len(set(paths)) != len(paths):
        parser.error("Input, output, report, publication state, and credential paths must be different.")
    try:
        document = parse_markdown(args.input.read_text(encoding="utf-8-sig"))
        if args.update:
            document_id(args.update)
        if args.folder_id:
            document_id(args.folder_id)
        if args.dry_run:
            report, warnings = analyze_document(document, args.input.resolve().parent, args.allow_remote_images)
            report["dependencies"]["google_apis"] = ["Docs", "Drive"] if args.upload else []
            if args.upload:
                report["unchecked"].append("Google target identity, revision, and folder permissions")
            if args.format == "google-requests" or args.update is not None:
                try:
                    build_requests(document)
                except ValueError as error:
                    report.update(ok=False, error=str(error))
            report["warnings"] = [asdict(warning) for warning in warnings]
            report["ok"] &= not (args.strict and bool(warnings))
            print(json.dumps(report, indent=2))
            return 0 if report["ok"] else 1
        if args.update is not None:
            build_requests(document)  # Reject unsupported source before auth or any remote write.
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "docx":
            warnings = render_docx(document, output, base_dir=args.input.resolve().parent,
                                   mermaid_renderer=partial(render_mermaid, scale=args.mermaid_scale),
                                   allow_remote_images=args.allow_remote_images)
            report = validate_docx(document, output)
        else:
            output.write_text(json.dumps({"title": args.title or args.input.stem, "requests": build_requests(document)}, indent=2), encoding="utf-8")
            warnings = document.warnings
            report = {"scope": "google-request-plan", "ok": True}
        report["warnings"] = [asdict(warning) for warning in warnings]
        report["ok"] &= not (args.strict and bool(warnings))
        if args.upload and report["ok"]:
            report["local_validation"] = report.copy()
            try:
                drive, docs = google_clients(args.credentials, args.token)
                report.update(publish_document(drive, docs, document, output, args.title or args.input.stem,
                    args.input, native=args.format == "google-requests", update=args.update, new=args.new,
                    expected_revision=args.expected_revision, folder_id=args.folder_id))
            except Exception as error:
                report.update(ok=False, scope="google-upload-failed", error=str(error))
        report["output"] = str(output)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"md2gdoc: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
