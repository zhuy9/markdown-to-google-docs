# Changelog

## 0.2.0 - 2026-09-10

- Preserve overflow tables and footnote-like definitions; warn on unsupported syntax.
- Validate ordered blocks, inline formatting, heading/list structure, and code boundaries.
- Add offline `--dry-run` and warning-sensitive `--strict` modes.
- Correct false height warnings for small Mermaid diagrams.
- Add a real Google-exported demo, compatibility matrix, and OAuth/recovery docs.
- Add explicit revision-protected text/code updates, persisted identity, and creation folder targeting.
- Apply native paragraph styles before inline styles and preserve hard line breaks.
- Document Claude Code plugin and Codex skill installation.
- Reconcile release evidence with the published `v0.1.1` release and hosted CI.

## 0.1.1 - 2026-09-09

- Fit pictures to the printable page box; tall Mermaid diagrams no longer run
  off the page, and a squeezed diagram reports `mermaid_scaled_to_page`.
- Added the `images_fit_page` validation check.
- Rendered Mermaid at 3x pixel density with a `--mermaid-scale` flag (1-5).

## 0.1.0 - 2026-09-09

- Implemented styled DOCX rendering, local Mermaid PNGs, image resolution, and validation reports.
- Added CLI, UTF-16 Google request plans, and optional OAuth DOCX import/read-back.
- Added a shared agent skill, portable ZIPs, and Claude marketplace manifests.
- Added CI and version-tag draft releases; hosted CI and live Google Docs import verified.
- Selected the MIT license.

- Added the CommonMark and pipe-table parser with typed document IR and offline tests.
- Preserved linked-image destinations and reported literal HTML with source locations.
- Established the Python package skeleton and synthetic Markdown fixtures.
- Recorded the architecture review, IR contract, and milestone criteria.
- Documented Google Docs MCP preference and DOCX import fallback.
- Added shared development guidance and public-repository ignore rules.
