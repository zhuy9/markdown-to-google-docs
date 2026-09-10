# Usage and installation

Convert Markdown into styled DOCX, with an optional Google Docs delivery path.
Code remains selectable, monospace, and shaded; Mermaid diagrams become PNGs.
One Python engine powers the CLI and the shared Codex/Claude skill.

**Status:** local conversion, package tests, hosted CI, and one live Google Docs
import path all have verification evidence. Both pages of the synthetic Google
PDF demo were visually inspected; arbitrary layouts and standalone OAuth upload
remain unverified. See [milestones](ROADMAP.md).

## Quick start

Requires Python 3.10+; use a virtual environment. From this checkout:

```bash
python -m venv .venv
# Activate the virtual environment for your shell, then:
python -m pip install .
md2gdoc tests/fixtures/basic.md -o output/basic.docx
```

For Mermaid, install Node.js and run `npm ci` in this repository, then:

```bash
md2gdoc tests/fixtures/kitchen-sink.md -o output/kitchen-sink.docx
```

Diagrams render at 3x pixel density. Because images are capped to the page
width, `--mermaid-scale` (1-5) changes sharpness rather than size:

```bash
md2gdoc input.md --mermaid-scale 5 -o output/sharp.docx
```

The [official Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) runs locally;
**no Mermaid API key is needed**. Outside a checkout, install it with
`npm install -g @mermaid-js/mermaid-cli@11.17.0`. Diagram source and PNGs are
retained in the output's sibling `.assets/` directory.

## Supported content

DOCX supports headings, paragraphs, combined bold/italic/link styles, inline
code, nested native lists, ordered starts, code blocks, pipe tables, images,
Mermaid, indented blockquotes, and horizontal rules. Images resolve relative to
the Markdown file; HTTP(S) downloads require `--allow-remote-images`.

HTML is preserved literally with a warning. Other Markdown extensions, including
math, footnotes, and task lists, are outside this MVP. Mermaid or image failures
produce visible fallback content and a failed validation report.

Tables with excess cells fall back to literal source instead of losing cells.
Footnote-like definitions remain visible instead of becoming reference links.
Task-list, dollar-math, footnote, and strikethrough syntax produce source-line
warnings; detection is best effort and excludes fenced/inline code and escaped
markers. These warnings describe unsupported syntax, not rendered extensions.

Pictures are scaled to fit the printable page box, preserving aspect ratio. A
Mermaid diagram too tall for one page still fits, but prints smaller than the
text width and reports a `mermaid_scaled_to_page` warning with its source lines;
splitting the graph or laying it out left-to-right reads better than shrinking.
The warning appears only when the page's height actually forces scaling; small
diagrams and diagrams scaled only to fit the width do not trigger it.

Each conversion writes a sibling `.report.json`: expected/observed counts,
content and formatting checks, warnings, and verification scope. Exit codes:
`0` checks passed within that scope, `1` validation/upload failed, `2` conversion
could not complete. Partial artifacts may remain after failure.

Validation matches whole text blocks in source order, including code boundaries,
heading levels, quote/list indentation, list starts/nesting, and explicit inline
styles. Google validation also checks table dimensions and resolves inherited
named text styles. Its code count reports matched, formatted source blocks.
These checks do not establish exact pagination, image placement, or pixel fidelity.

## Preflight and strict conversion

```bash
md2gdoc input.md --dry-run
md2gdoc input.md --dry-run --strict --upload
md2gdoc input.md --strict -o output/document.docx
```

Dry run prints JSON counts, source warnings, local asset checks, and dependency
requirements. It never creates files, starts Mermaid, downloads images, or signs
in to Google, even with `--upload` or `--allow-remote-images`. Mermaid syntax,
browser launch, remote asset availability, and rendering fidelity remain unchecked.
`--format google-requests` also checks that the source fits the native adapter.

Strict mode exits 1 for any warning, including literal unsupported syntax and
layout degradation. It prevents upload when local validation or warnings fail.
A normal strict conversion still writes its DOCX and report for inspection;
dry run only prints the report. Without strict mode, preserved literal content
continues to succeed with warnings; missing assets still fail validation.

## Google delivery

The shared skill first checks the connected MCP's actual capabilities. Text-only
documents can use generated native requests:

```bash
md2gdoc input.md --format google-requests -o output/document.requests.json
```

This path supports paragraphs, headings, styled text, and code. It rejects lists,
tables, quotes, rules, images, and Mermaid before remote creation; use DOCX import
for those. A request plan is not a created Google Doc.

### Google authentication

For standalone OAuth upload:

1. Create/select your Google Cloud project and enable both **Google Drive API**
   (DOCX import) and **Google Docs API** (creation, editing, read-back).
2. Configure Google Auth Platform branding and audience. For an external app in
   testing, add the account you will sign in with as a test user.
3. Create an OAuth client with application type **Desktop app**, download its
   JSON, and store it outside the checkout. Follow Google's
   [desktop setup](https://developers.google.com/workspace/drive/api/quickstart/python).

Install the optional Google dependencies and sign in:

```bash
python -m pip install ".[google]"
md2gdoc input.md -o output/document.docx --upload --credentials /private/client.json
```

First sign-in opens a browser. Tokens default to `~/.config/md2gdoc/token.json`;
subsequent uploads can omit `--credentials`. Each user supplies their own OAuth
configuration. No shared credentials belong in this public project.

The only requested scope is `https://www.googleapis.com/auth/drive.file`.
It authorizes files created by or explicitly opened/shared with this OAuth app,
and supports the converter's Drive and Docs operations. It does not grant access
to every document in your Drive. A file available through a separate MCP app is
not automatically available to this desktop client.
See [Google's scope guidance](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

The token file contains access and refresh credentials. Newly created token files
use owner-only permissions on POSIX; protect their containing directory and use
appropriate account permissions on Windows. `--token /path/token.json` selects
another location. Avoid placing credentials in a shared or synced folder.

To revoke access, remove your OAuth app in your Google Account's third-party
connections, then delete the local token file. Removing the local file alone
does not revoke the grant. Google also documents
[token revocation](https://developers.google.com/identity/protocols/oauth2/native-app#tokenrevoke).

If sign-in is denied, check audience/test users and your organization's OAuth
policy. If refresh fails after revocation or expiry, remove the obsolete token
and sign in again with `--credentials`. For missing Google modules, install
`.[google]` with the same Python used to run the converter. For API-disabled
errors, enable both APIs in the client's project. A 404/403 can mean the signed-in
account or this app lacks access. `--dry-run` does not test authentication or API
availability; there are no separate `auth setup/status` commands yet.

Alternatively, upload the DOCX to Drive and open it with Google Docs. Check the
imported result: local validation does not establish Google import fidelity.
See [Google delivery details](../skills/markdown-to-google-docs/references/google-delivery.md).

### Update an existing document

```bash
# Default: create a new document, and record its identity beside the source.
md2gdoc notes.md --upload
# Replace that saved document after checking for remote edits.
md2gdoc notes.md --upload --update
# Explicitly select an existing document on the first update.
md2gdoc notes.md --upload --update DOCUMENT_ID
# Explicitly create another document, even after an ambiguous earlier run.
md2gdoc notes.md --upload --new
# Create a document in a specific writable folder.
md2gdoc notes.md --upload --folder-id FOLDER_ID
```

The initial update implementation supports paragraphs, headings, inline styles,
links, hard breaks, and code in a single text-only document tab. Tables, lists,
images, Mermaid, headers/footers, footnotes, suggestions, and multi-tab targets
are rejected before replacement. New-document DOCX import still supports the full
compatibility matrix. Updates replace body content, preserve the title/folder,
and do not preserve comments attached to replaced text or merge collaborators' edits.

The source's sibling `notes.md.gdoc.json` records its resolved path, document ID,
revision, content fingerprint, and verification status. The default still creates
a new Doc; only `--update` reuses the identity. No document is selected by title.
Keep this local record: it detects changes made since the last verified publication.
Changing/moving a source requires reviewing its association; copied state with a
different source path is rejected. These files are ignored by Git.

Updates use the freshly read revision with Google's atomic
[`requiredRevisionId` precondition](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate#writecontrol).
They also compare the saved fingerprint, since persisted revision IDs are not a
durable content identity. If Google content changed, review the current document
and deliberately retry with `--update DOCUMENT_ID --expected-revision REVISION_ID`.
The error provides the current revision; a further edit makes that retry fail.
There is no unconditional force-overwrite flag.

A `pending` record means the operation was not verified, possibly after an
ambiguous network failure. Inspect the recorded ID and Google revision history;
do not blindly retry. After review, supply the current expected revision for an
update or use `--new` for a deliberate new document. A per-source `.gdoc.lock`
prevents simultaneous local publications. If a process crashes, confirm it has
stopped and inspect the pending state before removing its stale lock.

Folder targeting is for creation only. It checks folder identity, type, and
permission to add children before creating anything. It works with either DOCX
import or native creation and does not move an existing document during update.
Google access still depends on the signed-in account and the `drive.file` grant.
Dry run does not verify remote IDs, revisions, or folder permissions.

## Agent installation

Build with `python -m pip install -e ".[dev]"` then `python tools/build_skill.py`.
The two ZIPs in `dist/` bundle the same canonical skill and generated engine copy.
Extract the skill ZIP into your agent's skills directory, install its
`scripts/requirements.txt`, and invoke `$markdown-to-google-docs` in Codex.
See [Codex skills](https://developers.openai.com/codex/skills/).

For Claude Code, extract the Claude plugin ZIP and run:

```text
/plugin marketplace add /absolute/path/to/extracted/markdown-to-google-docs
/plugin install markdown-to-google-docs@markdown-to-google-docs
```

Install the extracted skill's `scripts/requirements.txt` with the Python you use
for conversion. A source checkout can also be added as a local marketplace after
`python -m pip install .`. The hosted GitHub repository works as the marketplace
source directly: `/plugin marketplace add zhuy9/markdown-to-google-docs`. See [Claude marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).

## Development and releases

```bash
python -m pip install -e ".[dev,google]"
python -m unittest discover -s tests -v
npm ci
python -m unittest discover -s tests/integration -v
python -m build
python tools/build_skill.py
```

Tests use synthetic documents; live Google checks are separate. CI tests Windows
and Linux, builds wheels/source distributions and both skill ZIPs, and exercises
the real Mermaid CLI on Windows. Pushing a version-matching `v*` tag creates a
draft GitHub release after checks pass; publishing the draft is an owner action.
Hosted CI passes on Windows and Linux, including real Mermaid rendering, and it
passed on the current main commit. The `v0.2.0` tag workflow built and attached
all four expected artifacts, and that release is published, so the latest-asset
download URL resolves and serves the current skill archive. Local archive builds
remain available as a fallback.

Read [architecture](ARCHITECTURE.md), [CONTRIBUTING.md](../CONTRIBUTING.md), and
[AGENTS.md](../AGENTS.md). `CLAUDE.md` is a relative symlink to `AGENTS.md`.
Private notes, credentials, build artifacts, and generated documents are ignored.

## License

[MIT](../LICENSE).
