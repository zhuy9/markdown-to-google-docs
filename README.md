# Markdown to Google Docs

Turn Markdown into a formatted Word document (DOCX) for Google Docs.
Keep headings, lists, tables, links, images, and editable code blocks.
Mermaid diagrams become images using a local tool; no API key is needed.

**Status:** DOCX conversion is tested. Google Docs upload and import still
need live verification.

## Prerequisites

- Python 3.10+.
- A connected **Google Drive MCP** for the agent to create Google Docs. It must
  support document creation or DOCX import, plus reading the result.
- Node.js for Mermaid diagrams.

DOCX-only conversion works without an MCP connection.

## Quick start

From this repository:

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on PowerShell or
`source .venv/bin/activate` on macOS/Linux. Then run:

```bash
python -m pip install .
md2gdoc tests/fixtures/basic.md -o output/basic.docx
```

For Mermaid diagrams, install Node.js and run `npm ci` first.
Each conversion saves a DOCX and a JSON report with any warnings.
HTML stays plain text. Math, footnotes, and task lists are not supported.

## Google Docs and agent skills

Upload the DOCX to Drive and open it with Google Docs. Optional direct upload
uses your own Google sign-in. Keep credentials and tokens outside this repo.

The same skill works with Codex and Claude.
See [setup and usage](docs/USAGE.md) for Google upload and skill installation.

## Contributing

See [contributing](CONTRIBUTING.md), [architecture](docs/ARCHITECTURE.md), and
[roadmap](docs/ROADMAP.md). Local tests and hosted CI pass.

[MIT license](LICENSE).
