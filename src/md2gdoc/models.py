"""Document structure independent of Markdown tokens and rendering APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class SourceRange:
    """Zero-based source lines, with an exclusive end."""

    start_line: int
    end_line: int


@dataclass(frozen=True)
class Warning:
    code: str
    message: str
    source: SourceRange


@dataclass(frozen=True)
class TextSpan:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link: str | None = None


@dataclass(frozen=True)
class Image:
    src: str
    alt: str
    title: str | None = None
    link: str | None = None


@dataclass(frozen=True)
class LineBreak:
    hard: bool


Inline: TypeAlias = TextSpan | Image | LineBreak


@dataclass(frozen=True)
class Paragraph:
    inlines: tuple[Inline, ...]
    source: SourceRange


@dataclass(frozen=True)
class Heading:
    level: int
    inlines: tuple[Inline, ...]
    source: SourceRange


@dataclass(frozen=True)
class ListItem:
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    start: int
    items: tuple[ListItem, ...]
    source: SourceRange


@dataclass(frozen=True)
class CodeBlock:
    text: str
    language: str | None
    source: SourceRange


@dataclass(frozen=True)
class MermaidDiagram:
    text: str
    source: SourceRange


@dataclass(frozen=True)
class TableCell:
    inlines: tuple[Inline, ...]


@dataclass(frozen=True)
class Table:
    header: tuple[TableCell, ...]
    rows: tuple[tuple[TableCell, ...], ...]
    alignments: tuple[str | None, ...]
    source: SourceRange


@dataclass(frozen=True)
class Blockquote:
    blocks: tuple[Block, ...]
    source: SourceRange


@dataclass(frozen=True)
class HorizontalRule:
    source: SourceRange


Block: TypeAlias = (
    Paragraph | Heading | ListBlock | CodeBlock | MermaidDiagram
    | Table | Blockquote | HorizontalRule
)


@dataclass(frozen=True)
class Document:
    blocks: tuple[Block, ...]
    warnings: tuple[Warning, ...]
