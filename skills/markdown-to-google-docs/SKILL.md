---
name: markdown-to-google-docs
description: Convert Markdown files to styled Google Docs or importable DOCX, preserving selectable code and rendering Mermaid diagrams. Use for document conversion with formatting fidelity.
---

# Markdown to Google Docs

Run the deterministic converter; do not reconstruct its formatting requests or
calculate Google Docs indexes by hand. Resolve input paths before invoking it.

## Run conversion

Requires Python 3.10+. From a repository checkout, install `python -m pip install .`.
For an extracted skill ZIP, install `python -m pip install -r scripts/requirements.txt`
relative to this skill directory. Run:

```bash
python <skill-directory>/scripts/convert.py input.md -o output/document.docx
```

Mermaid requires the official CLI: run `npm install -g @mermaid-js/mermaid-cli@11.17.0`
or `npm ci` in the source repository. Rendering is local and needs no key.
Images resolve against the Markdown file's directory. HTTP(S) downloads require
`--allow-remote-images`; use only when fetching those references is authorized.

## Choose the delivery path

- Prefer a connected Google Docs MCP when its actual tools support creation,
  formatting, and read-back. For paragraphs, headings, inline styles, and code,
  generate `--format google-requests -o output/document.requests.json`, create
  a new document with its title, and apply the generated requests unchanged.
- Lists, tables, quotes, rules, images, and Mermaid use DOCX. If the connector
  supports binary upload with Google Docs conversion, import the generated file.
- If those tools are unavailable, deliver the DOCX and report that Google import
  is unverified. Optional standalone OAuth upload is described in
  [Google delivery](references/google-delivery.md).

Read back the created document. Save the response locally and compare it using
`md2gdoc.validator.validate_google(parse_markdown(source), response)`.
Do not claim successful Google conversion from local DOCX checks alone.

## Report the result

The converter writes a sibling `.report.json` with scope, expected/observed
counts, checks, and warnings. Exit 0 means checks passed within that scope;
1 means validation/upload failed, and 2 means conversion could not complete.
Partial artifacts can exist after failure: disclose missing images or failed
diagrams. Mermaid source remains in the sibling `.assets/` directory and
rendering failures retain readable code in the document.

Code remains selectable, monospace, shaded text. HTML is literal with a warning;
math, footnotes, task lists, and other Markdown extensions are not implemented.
Do not execute fenced code or publish assets to an external renderer without
authorization covering disclosure. After an ambiguous remote create failure,
inspect the returned document ID before retrying to avoid duplicate documents.
