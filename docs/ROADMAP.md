# Milestones and acceptance criteria

Follow the original order. Only mark a milestone complete after its acceptance
checks pass; partial implementation is not completion.

| # | Milestone | Acceptance criteria | Status |
| --- | --- | --- | --- |
| 1 | Project skeleton | Python package builds and imports; public development docs and fixtures exist; `.temp/` is ignored; `CLAUDE.md` resolves to `AGENTS.md` | Complete |
| 2 | Markdown parser -> IR | Offline fixture tests cover typed nodes, nesting, source ranges, Unicode, empty input, and warnings; no API calls during parsing | Complete |
| 3 | Paragraphs and headings | Deterministic rendered text and heading styles, including emoji range tests | Complete (local checks) |
| 4 | Bold, italic, links | Combined styles and link destinations survive rendering; ranges verified | Complete (local checks) |
| 5 | Lists | Ordered starts, bullets, nested items, and multi-paragraph items preserved | Complete (local checks) |
| 6 | Code blocks | Code stays selectable, monospace, shaded, and whitespace-preserving; inline code styled | Complete (local checks) |
| 7 | Tables | Header, cells, inline formatting, and alignment preserved; structural indexes tested | Complete (local checks) |
| 8 | Images | Relative paths resolve against source directory; alt text preserved; missing assets reported | Complete (local checks) |
| 9 | Mermaid | Provider validates syntax and returns PNG; source retained; failures produce warnings and readable source | Complete (local checks) |
| 10 | Google Docs integration | Discover actual MCP capabilities; create and read back a fixture document, or generate DOCX and verify import; report which path and checks ran | Complete (live DOCX import and read-back) |
| 11 | Validation | Expected/observed element counts expose missing content; blockquotes and rules verified; unsupported HTML reported; code not mistaken for leaked Markdown | Complete (local checks) |
| 12 | Agent Skill packaging | One vendor-neutral skill invokes the engine, reports degradation, and validates/builds into an installable ZIP | Complete (local checks) |
| 13 | Claude marketplace packaging | Marketplace installs the same canonical skill; no duplicated runtime instructions | Complete (local checks) |
| 14 | GitHub Actions release workflow | Offline checks run in CI; a tag builds tested package/skill artifacts without private data | Complete (tag v0.1.0 built a verified draft) |

Milestone 2 establishes the AST mapping for all MVP node types; milestones 3-9
add output behavior incrementally. Blockquotes and horizontal rules belong in
the parser and basic renderer work even though they have no separate milestone.

For milestone 10, automatic Google Doc creation and manual DOCX import are
different outcomes. A generated DOCX alone is local fallback delivery, not
evidence of successful Google Docs import. Keep the integration milestone
open until at least one end-to-end path is verified. A standalone CLI and
optional API authentication belong here, sharing the same conversion engine.

License: MIT, selected by the owner.

## Verification evidence (2026-09-09)

- 50 offline tests passed on Windows/Python 3.10.2: parsing, rendering, assets,
  UTF-16 requests, API failure boundaries, validation, CLI, and ZIP execution.
- Two real Mermaid CLI tests passed: valid PNG and invalid-syntax fallback.
- Kitchen-sink DOCX passed all expected/observed counts and content checks,
  including its image and Mermaid diagram; HTML retained literally with warning.
- Wheel and source distribution built. A fresh environment installed the wheel
  and converted the basic fixture successfully.
- Both ZIPs execute outside the checkout and contain identical canonical skills.
  The skill validator passed. Claude's CLI validated the marketplace, installed
  it in an isolated profile, and the installed converter passed a fixture check.
- Workflows passed actionlint. [Hosted CI](https://github.com/zhuy9/markdown-to-google-docs/actions/runs/34367365699)
  passed all four Windows/Linux Python jobs and the real Mermaid job for
  commit `b592b9a`. Tag release execution remains unverified, so milestone 14
  stays open.
- The initial session had no callable Google creation tools. The connected
  verification below completes milestone 10 through DOCX import.

## Live Google verification (2026-09-09)

- Converted `tests/fixtures/kitchen-sink.md` with the existing CLI and local
  Mermaid renderer; all local DOCX checks passed. Imported it with the connected
  `google_drive_import_document` tool using `native_google_docs`, then read it
  with `google_drive_get_document`. Drive metadata confirmed native Google Docs
  MIME type, the `ChatGPT` destination folder, and `shared: false`.
- `validate_google` passed against the live response: 1 heading, 1 table,
  1 selectable code block, 2 images (local image and Mermaid), 1 rule, 5 list
  items, and 1 link destination. Text, links, monospace code, indentation, and
  shading survived. HTML stayed literal with the expected `unsupported_html`
  warning.
- Additional read-back checks confirmed ordered numbering starts at 3, nested
  bullets, the unnumbered continuation paragraph, quote indentation, the 2x2
  table and its cell text, bold/italic text, and image alt text/title.
- Fixed validator assumptions exposed by the live response: flattened MCP tabs,
  imported soft line breaks, paragraph shading, and zero-width borders. Three
  regression tests reproduce those shapes and detect missing shading, changed
  code indentation, and a missing rule.
- PDF export succeeded (76,248 bytes), but the runtime could not materialize the
  returned file reference for rendered-page inspection. Layout fidelity remains
  unverified. Direct native creation and standalone OAuth were not live-tested.
- Raw read-back and reports remain in ignored `.temp/google-verification/`;
  document IDs and temporary image URLs are excluded from tracked evidence.

All milestone acceptance checks now pass. Structural read-back does not
establish visual layout fidelity, which remains the main unverified property.
Durable decisions live in this roadmap and the architecture.

## Tag release verification (2026-09-09)

- Tag `v0.1.0` on commit `fbeaa1f` ran the release workflow to success. The
  reused checks workflow passed, the release job's version assertion matched the
  tag to the packaged `0.1.0`, and the draft received all four expected
  artifacts: wheel, source distribution, skill ZIP, and Claude plugin ZIP.
- Downloaded draft assets confirmed the embedded license and marketplace owner
  both read `Darren Zhu`, so owner metadata propagates into published archives.
- The release stays a draft pending manual publish, so public release and
  install-from-release-asset paths are still unexercised.
