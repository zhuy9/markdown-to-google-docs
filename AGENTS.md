# Repository development instructions

## Before coding

- Read `docs/ARCHITECTURE.md` and the current Git state. Continue from the
  next unfinished milestone in `docs/ROADMAP.md`.
- State assumptions before writing code. If the request has multiple
  interpretations, list them and ask which is intended. If anything is
  unclear, stop and ask; do not guess silently.
- If a simpler approach exists, say so. Preserve recorded architectural
  decisions unless a concrete technical problem justifies changing them.
- Before a multi-step task, give a short plan: step -> verification check.

## Architecture

- Keep the core vendor-neutral: Markdown AST -> Document IR -> renderer.
  See `docs/ARCHITECTURE.md` for the IR contract and adapter boundaries.
- Conversion logic belongs in `src/md2gdoc/`, not in agent prompts.
- Keep Google Docs indexing and API details inside its adapter. Prefer a
  connected Google Docs MCP with adequate creation, formatting, and read-back
  tools; otherwise use the planned DOCX import fallback. Check actual tool
  capabilities before claiming support.
- Keep Mermaid rendering behind a small callable boundary. Preserve its
  source, and report rendering failures and unsupported content.
- Code blocks remain selectable text, never screenshots.

## Shared skill and contributor guidance

- The canonical runtime skill is
  `skills/markdown-to-google-docs/SKILL.md`, shared by Codex and Claude.
  Do not duplicate it into separate vendor directories.
- Add vendor metadata only when its packaging milestone is implemented.
- `AGENTS.md` is the canonical development guide. `CLAUDE.md` must be a
  relative symbolic link to `AGENTS.md`, not a second copy or a hard link.

## Writing and editing code

- Write the minimum code needed. Prefer the standard library; add a
  dependency only when the current milestone needs it.
- No speculative abstractions, configuration, features, or error handling
  for scenarios that cannot occur. If a solution exceeds roughly 50 lines
  and a simpler version exists, simplify it.
- Change only what the task requires and match the surrounding style.
- Remove imports, variables, and functions made unused by your changes.
  Mention unrelated dead code in a review comment; do not delete it.
- Use Python type hints, ordinary dataclasses, and small functions.

## Validation

- Prefer a failing fixture-driven test before implementing behavior.
  Use synthetic data in `tests/fixtures/`; parser tests run offline.
- Run `python -m build` and install/import the wheel to verify packaging.
- Once behavior tests exist, run `python -m unittest discover -s tests -v`.
  A zero-test run does not establish conversion correctness.
- Test renderer operations independently of live Google APIs. Keep live
  integration checks separate and report any checks that were not run.
- Run `git diff --check` and inspect the final Git state. Mark a milestone
  complete only when its acceptance criteria are verified, and update the
  roadmap with evidence and the next unfinished milestone.

## Public repository

- Keep `.temp/`, credentials, tokens, private documents, and generated
  output out of Git. Use fictional examples and no personal contact data.
- Inspect candidate files and package archives before publishing. Ignore
  rules do not remove files already tracked or committed in Git history.
- Do not publish source images or Mermaid content to an external renderer
  or hosting service without authorization covering that disclosure.
