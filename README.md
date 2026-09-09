# Markdown to Google Docs

Turn Markdown into a formatted Word document (DOCX) for Google Docs.
Keep headings, lists, tables, links, images, and editable code blocks.
Mermaid diagrams become images using a local tool; no API key is needed.

**Status:** DOCX conversion and native Google Docs import through the connected
Drive MCP passed kitchen-sink checks. Pictures are checked to fit the printable
page box. Visual layout fidelity beyond that, and standalone OAuth upload,
remain unverified.

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

## Install as an agent skill

One canonical skill runs in both agents. Each needs the Python engine's two
dependencies; add Node.js only if you want Mermaid diagrams.

```bash
python -m pip install "markdown-it-py>=4.2,<5" "python-docx>=1.2,<2"
```

### Claude Code

Add this repository as a plugin marketplace, then install from it:

```text
/plugin marketplace add zhuy9/markdown-to-google-docs
/plugin install markdown-to-google-docs@markdown-to-google-docs
```

The same two commands work outside a session as `claude plugin marketplace add`
and `claude plugin install`. A local checkout can be used as the marketplace
source instead: pass its absolute path to `marketplace add`.

### Codex

Extract the skill archive into a skills directory Codex scans, either
`~/.agents/skills` for every project or `.agents/skills` inside one repository:

```bash
mkdir -p ~/.agents/skills
curl -L -o skill.zip https://github.com/zhuy9/markdown-to-google-docs/releases/latest/download/markdown-to-google-docs-skill.zip
unzip skill.zip -d ~/.agents/skills
```

The archive already contains a copy of the engine, so no checkout is needed.
Invoke it with `$markdown-to-google-docs`, or run `/skills` to browse.

### Using it

Ask the agent to convert a Markdown file. It writes a DOCX plus a JSON report,
then either uploads through a connected Google Drive tool or hands back the file
to import yourself. Upload the DOCX to Drive and open it with Google Docs;
optional direct upload uses your own Google sign-in. Keep credentials and tokens
outside this repository.

See [setup and usage](docs/USAGE.md) for Google upload details and for building
the archives yourself with `python tools/build_skill.py`.

## Contributing

See [contributing](CONTRIBUTING.md), [architecture](docs/ARCHITECTURE.md), and
[roadmap](docs/ROADMAP.md). Local tests and hosted CI pass.

[MIT license](LICENSE).
