"""Command-line conversion, optional upload, and explicit validation reports."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .google_docs import build_requests, create_document, google_clients, import_docx
from .parser import parse_markdown
from .renderer import render_docx
from .validator import validate_docx, validate_google


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown to DOCX or Google Docs requests.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--format", choices=("docx", "google-requests"), default="docx")
    parser.add_argument("--title", help="Title for an uploaded Google Doc (default: input filename).")
    parser.add_argument("--allow-remote-images", action="store_true", help="Allow downloading HTTP(S) image references.")
    parser.add_argument("--upload", action="store_true", help="Create a new Google Doc using your own OAuth account.")
    parser.add_argument("--credentials", type=Path, help="Google desktop OAuth client JSON for first sign-in.")
    parser.add_argument("--token", type=Path, default=Path.home() / ".config/md2gdoc/token.json")
    args = parser.parse_args(argv)
    suffix = ".docx" if args.format == "docx" else ".requests.json"
    output = args.output or Path("output") / (args.input.stem + suffix)
    report_path = output.with_suffix(".report.json")
    if args.input.resolve() in (output.resolve(), report_path.resolve()) or output.resolve() == report_path.resolve():
        parser.error("Input, output, and report paths must be different.")
    try:
        document = parse_markdown(args.input.read_text(encoding="utf-8-sig"))
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "docx":
            warnings = render_docx(document, output, base_dir=args.input.resolve().parent,
                                   allow_remote_images=args.allow_remote_images)
            report = validate_docx(document, output)
        else:
            output.write_text(json.dumps({"title": args.title or args.input.stem, "requests": build_requests(document)}, indent=2), encoding="utf-8")
            warnings = document.warnings
            report = {"scope": "google-request-plan", "ok": True}
        report["warnings"] = [asdict(warning) for warning in warnings]
        if args.upload and report["ok"]:
            report["local_validation"] = report.copy()
            try:
                drive, docs = google_clients(args.credentials, args.token)
                remote = (import_docx(drive, docs, output, args.title or args.input.stem) if args.format == "docx"
                          else create_document(docs, document, args.title or args.input.stem))
                report.update(validate_google(document, remote))
                report["google_url"] = f"https://docs.google.com/document/d/{remote['documentId']}/edit"
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
