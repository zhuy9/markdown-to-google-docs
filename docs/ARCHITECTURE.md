# Architecture and initial review

The project uses a deterministic Python engine shared by thin Codex and Claude
orchestration. Parsing, DOCX rendering, validation, CLI, Google
adapter, and shared skill packaging are implemented. Native DOCX import through
the connected Drive MCP passed live kitchen-sink read-back. Both pages of a fresh
Google PDF export were visually inspected. The v0.1.1 tag produced a published
release with all four artifacts. Standalone OAuth and arbitrary document layout
remain unverified; see the roadmap for per-path evidence.

## Pipeline and boundaries

```text
Markdown -> parser AST -> Document IR -> Google Docs operations -> MCP/API
                              |
                              +-> DOCX -> Google Docs import
```

`parser.py` normalizes the AST without file or network access. `models.py`
holds frozen dataclasses. `renderer.py` maps the IR to DOCX formatting;
`google_docs.py` owns API request construction, indexes, and execution.
`publishing.py` owns source-bound identity, local publication locks, fingerprints,
and pending/verified state. `images.py` resolves assets; the renderer accepts a Mermaid callable, defaulting
to the local official CLI in `mermaid.py`. `validator.py` independently compares
expected and observed output.

Native Google requests support paragraphs, headings, inline styles, and code.
Structural and asset content is rejected before mutation and uses DOCX import.
This avoids speculative table-index editing and public image hosting.
Google read-back validation checks content and structure, not exact layout.

The agent discovers connected tools and invokes the engine. The engine
calculates all indexes deterministically; the agent never counts characters
or reconstructs hundreds of requests manually.

## Libraries

| Need | Choice | When to add |
| --- | --- | --- |
| Package | setuptools with `pyproject.toml` | Milestone 1 |
| IR, CLI, tests | Standard-library `dataclasses`, `argparse`, `unittest` | As behavior is implemented |
| Markdown AST | `markdown-it-py>=4.2,<5`, CommonMark with the table rule enabled | Milestone 2 |
| DOCX fallback | `python-docx>=1.2,<2` | Milestones 3-9 rendering |
| Standalone Google authentication/API | `google-auth`, `google-api-python-client` if needed beyond MCP | Milestone 10 |
| Mermaid PNG | Official Mermaid CLI 11.17.0 via a callable | Milestone 9 |

Python 3.10+ is the initial target. `markdown-it-py` and `python-docx` are the runtime
dependencies; Google SDKs are optional. Avoid an LLM SDK, orchestration framework, schema framework,
or handwritten Markdown parser. The parser's
[syntax tree](https://markdown-it-py.readthedocs.io/en/latest/api/markdown_it.tree.html)
and [rule configuration](https://markdown-it-py.readthedocs.io/en/latest/using.html)
support the proposed AST boundary. `python-docx` provides
[Word document construction](https://python-docx.readthedocs.io/en/latest/).

## Document IR contract

The IR uses typed dataclasses and ordered child tuples, without an inheritance
framework. The concrete types live in `src/md2gdoc/models.py`.
Every block carries a `SourceRange` for diagnostics. No Google indexes, MCP
tool names, credentials, remote document IDs, or formatting API objects belong
in the IR.

| Type | Fields and meaning |
| --- | --- |
| `SourceRange` | `start_line: int`, `end_line: int`; zero-based, end-exclusive |
| `Document` | `blocks: tuple[Block, ...]`, `warnings: tuple[Warning, ...]` |
| `Warning` | `code: str`, `message: str`, `source: SourceRange` |
| `TextSpan` | `text: str`, `bold: bool`, `italic: bool`, `code: bool`, `link: str \| None`; styles can combine |
| `Image` | `src: str`, `alt: str`, `title: str \| None`, `link: str \| None`; retains the unresolved image reference and any enclosing hyperlink |
| `LineBreak` | `hard: bool`; preserves explicit versus soft line breaks |
| `Paragraph` | `inlines: tuple[Inline, ...]`, `source: SourceRange` |
| `Heading` | `level: int` (1-6), `inlines: tuple[Inline, ...]`, `source: SourceRange` |
| `ListBlock` | `ordered: bool`, `start: int`, `items: tuple[ListItem, ...]`, `source: SourceRange` |
| `ListItem` | `blocks: tuple[Block, ...]`; preserves nested lists and multiple paragraphs |
| `CodeBlock` | `text: str`, `language: str \| None`, `source: SourceRange`; preserve whitespace |
| `MermaidDiagram` | `text: str`, `source: SourceRange`; source survives image rendering |
| `Table` | `header: tuple[TableCell, ...]`, `rows: tuple[tuple[TableCell, ...], ...]`, `alignments: tuple[str \| None, ...]`, `source: SourceRange` |
| `TableCell` | `inlines: tuple[Inline, ...]`; alignments are left, center, right, or unspecified |
| `Blockquote` | `blocks: tuple[Block, ...]`, `source: SourceRange` |
| `HorizontalRule` | `source: SourceRange` |

`Inline` is the union of `TextSpan`, `Image`, and `LineBreak`. `Block` is the
union of `Paragraph`, `Heading`, `ListBlock`, `CodeBlock`, `MermaidDiagram`,
`Table`, `Blockquote`, and `HorizontalRule`. Standalone images live in
paragraphs, matching Markdown's inline image semantics. Resolve relative
images against the input file's directory, supplied separately to the asset
resolver. Normalize source line endings to LF but preserve code indentation,
tabs, and blank lines, after Markdown container indentation is removed.
Inline code follows CommonMark's whitespace normalization.

`parse_markdown(text)` returns a `Document`. Raw HTML is preserved literally
with `unsupported_html` warnings; inline warnings use the containing paragraph
or table-row source range. Mermaid fences retain source without validation or
rendering. Other Markdown extensions remain outside the supported dialect.

The optional `Image.link` field addresses a concrete gap in the original
contract: `[![alt](image.png)](destination)` would otherwise lose its hyperlink.

## Concrete risks and decisions

- **MCP capability varies.** Prefer a connected tool that can create, apply
  the required formatting, insert images/tables, and read the result. No
  Google Docs creation MCP was callable during the initial repository review.
  Do not assume a Drive connector supplies full Docs editing capabilities.
- **Indexes and structural edits.** Google Docs uses UTF-16 code units;
  Python character counts differ for emoji. Paragraphs, tables, and document
  tabs also affect request locations. Keep this logic in the adapter and
  verify operation ranges with emoji and table fixtures before live writes.
  See [Google Docs structure](https://developers.google.com/workspace/docs/api/concepts/structure).
- **Image hosting.** Direct inline insertion requires a publicly accessible
  image URL. Do not assume a private Drive sharing link will work. Prefer a
  connector's verified image-upload capability; otherwise use DOCX with
  embedded images or user-authorized temporary hosting. See
  [inline image insertion](https://developers.google.com/workspace/docs/api/how-tos/images).
- **Fallback fidelity.** If MCP cannot perform the required edits, generate
  DOCX from the same IR. Import using a supported Drive upload operation with
  target MIME type `application/vnd.google-apps.document`, or provide the
  file for manual import. Check `about.importFormats` when using the API.
  Import may change layout; verify the imported result before claiming
  fidelity. See [Drive import](https://developers.google.com/workspace/drive/api/guides/manage-uploads#import_to_google_docs_types).
- **Retries and ownership.** New-document creation remains the default. Explicit
  single-tab text/code updates check saved fingerprints and use one atomic Docs
  batch with `requiredRevisionId`. State is marked pending before mutation and
  verified only after read-back. No automatic retry or unconditional overwrite;
  complex content continues to use new DOCX imports. See usage for recovery.
- **Mermaid and untrusted input.** The selected provider must validate/render
  syntax and return PNG. Preserve source locally for regeneration; failures
  retain readable source with a warning. Do not execute fenced code or raw
  HTML. External rendering and hosting disclose content to another service.
- **Validation is evidence.** Separate local structural checks from live
  read-back. Count headings, styled code, tables, links, images, and diagrams;
  flag missing/degraded elements without treating literal Markdown inside
  code blocks as leaked syntax. Link preservation is distinct from checking
  destination availability over the network.

MVP code stays selectable, monospace, shaded, and whitespace-preserving.
Inline code gets light formatting. Syntax highlighting, math, footnotes,
task lists, admonitions, TOC, captions, HTML rendering, and front matter are
later work. `clean` and `faithful` modes remain candidates, not current flags.
