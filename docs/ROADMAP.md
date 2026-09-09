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
| 10 | Google Docs integration | Discover actual MCP capabilities; create and read back a fixture document, or generate DOCX and verify import; report which path and checks ran | Implemented; live verification pending |
| 11 | Validation | Expected/observed element counts expose missing content; blockquotes and rules verified; unsupported HTML reported; code not mistaken for leaked Markdown | Complete (local checks) |
| 12 | Agent Skill packaging | One vendor-neutral skill invokes the engine, reports degradation, and validates/builds into an installable ZIP | Complete (local checks) |
| 13 | Claude marketplace packaging | Marketplace installs the same canonical skill; no duplicated runtime instructions | Complete (local checks) |
| 14 | GitHub Actions release workflow | Offline checks run in CI; a tag builds tested package/skill artifacts without private data | CI passed; tag release pending |

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
- No callable Google Docs/Drive creation tools were exposed in this session.
  No live Google document was created, imported, or read back. Milestone 10 is
  the next unfinished acceptance check; use a synthetic fixture when connected.

Local structural checks do not establish visual layout fidelity in Word or
Google Docs. Review an imported fixture before describing Google support as
verified. Durable decisions live in this roadmap and the architecture.
