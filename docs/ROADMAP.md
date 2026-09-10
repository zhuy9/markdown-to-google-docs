# Milestones and acceptance criteria

## Review follow-ups

1. Parser loss prevention: complete. Overflow tables fall back to literal text;
   footnotes remain literal; extension warnings exclude code/escapes. 59 offline
   tests passed, including three new regressions.
2. Validation fidelity: complete. Whole-block matching, inline styles, heading
   levels, indentation, list starts/nesting, table shape, and code boundaries
   pass 63 offline tests and a fresh synthetic Google import/read-back.
3. Strict and dry-run CLI: complete. 66 offline tests passed; side-effect guards
   verify dry run never renders/downloads/authenticates/writes and strict warnings
   block upload while default warning behavior remains compatible.
4. Mermaid sizing diagnostic: complete. 67 offline tests passed; tall diagrams
   warn, while naturally small and width-limited diagrams do not.
5. Documentation and visual verification: complete. Added the compatibility matrix,
   real Google-exported demo image, OAuth setup/scopes/revocation, limitations, and
   reconciled release evidence. Fresh import/read-back passes; both PDF pages were
   inspected (headings, lists, code, table, images, diagram, rule, literal HTML).
6. Safe document updates and folder targeting: implemented for single-tab text/code
   documents. Source-bound atomic state, pending-operation recovery, local locking,
   remote fingerprint checks, revision-guarded batches, explicit new/update flags,
   and folder preflight have offline coverage. A synthetic live update preserved
   headings, emoji, links, bold, hard breaks, and two code blocks; a stale-revision
   batch was rejected by Google. Live testing exposed and fixed native paragraph
   styles resetting inline styles. Full-content updates remain a future milestone;
   standalone OAuth and folder targeting have not been exercised live.

Next unfinished feature milestone: revision-protected updates for tables, lists,
images, and Mermaid, which require expanding the native adapter. Do not substitute
an unguarded full DOCX overwrite. Batch conversion and presets remain deferred.

Final review checks: 81 offline tests and 3 real Mermaid tests passed on macOS /
Python 3.14. Wheel/source and both skill archives build; archive contents are
inspected and the installed wheel is exercised outside the checkout. Live Google
verification used connected MCP tools, not standalone OAuth. Hosted CI passed on the
current main commit; standalone OAuth and folder checks remain outstanding. No new
runtime dependency was added.

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
| 14 | GitHub Actions release workflow | Offline checks run in CI; a tag builds tested package/skill artifacts without private data | Complete (tags v0.1.0 and v0.1.1 built verified artifacts; v0.1.1 published) |

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
  commit `b592b9a`. The subsequent tag verification below completed milestone 14.
- The initial session had no callable Google creation tools. The connected
  verification below completes milestone 10 through DOCX import.

## Live Google verification (2026-09-09)

- Converted `tests/fixtures/kitchen-sink.md` with the existing CLI and local
  Mermaid renderer; all local DOCX checks passed. Imported it with the connected
  `google_drive_import_document` tool using `native_google_docs`, then read it
  with `google_drive_get_document`. Drive metadata confirmed native Google Docs
  MIME type, the intended destination folder, and `shared: false`.
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

All original milestone acceptance checks passed. Structural read-back alone
does not establish visual layout fidelity; the review follow-up above adds a
two-page visual inspection of the synthetic fixture, not a general layout guarantee.
Durable decisions live in this roadmap and the architecture.

## Tag release verification (2026-09-09)

- Tag `v0.1.0` on commit `fbeaa1f` ran the release workflow to success. The
  reused checks workflow passed, the release job's version assertion matched the
  tag to the packaged `0.1.0`, and the draft received all four expected
  artifacts: wheel, source distribution, skill ZIP, and Claude plugin ZIP.
- Downloaded draft assets confirmed the embedded license and marketplace owner
  both read `Darren Zhu`, so owner metadata propagates into published archives.
- Tag `v0.1.1` repeated the same workflow success and its draft was published, so
  the public release and the `releases/latest/download` skill-archive URL both
  resolve. Installing from that published asset is still unexercised.

## Release 0.2.0 preparation (2026-09-10)

- Bumped `pyproject.toml` and `.claude-plugin/plugin.json` together to `0.2.0`,
  since packaging tests assert the manifests match the installed version.
- 81 offline tests and 3 real Mermaid CLI tests passed on macOS / Python 3.14.
- Wheel, source distribution, skill ZIP, and Claude plugin ZIP all built at
  `0.2.0`. A clean venv installed the wheel outside the checkout and converted a
  sample file with every local check passing.
- Reconciled stale release evidence: hosted CI passes on the current main commit,
  `v0.1.1` is published with all four assets, and the
  `releases/latest/download` skill-archive URL returns 200.
- Hosted checks passed on the release commit `3a6ffbc`: all four Windows/Linux
  Python jobs and the real Mermaid job.
- Tag `v0.2.0` ran the release workflow to success. Its version assertion matched
  the tag to the packaged `0.2.0`, and the draft received all four expected
  artifacts. Downloaded draft assets confirm `0.2.0` in the wheel metadata and
  the plugin manifest, the MIT license file, and the `Darren Zhu` marketplace
  owner. The downloaded skill archive converted a table fixture outside any
  checkout with all local checks passing.
- Outstanding: publishing the draft is an owner action. Standalone OAuth and
  folder targeting are still not exercised live, and installing from a published
  release asset is still unexercised.
