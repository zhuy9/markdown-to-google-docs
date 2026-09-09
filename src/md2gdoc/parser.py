"""Normalize CommonMark and pipe tables into the document IR without I/O."""

from dataclasses import replace
import re

from markdown_it import MarkdownIt
from markdown_it.rules_block import reference, table
from markdown_it.rules_block.table import escapedSplit, getLine
from markdown_it.tree import SyntaxTreeNode

from . import models as ir


def parse_markdown(text: str) -> ir.Document:
    """Parse text, preserving HTML literally and deferring asset rendering."""
    warnings: list[ir.Warning] = []
    parser = MarkdownIt("commonmark").enable("table")
    parser.block.ruler.at("table", _table_no_loss)
    parser.block.ruler.at("reference", _reference_no_footnotes)
    parser.core.ruler.before("text_join", "extension_warnings", _extension_warnings)
    tree = SyntaxTreeNode(parser.parse(text, {"warnings": warnings}))
    blocks = tuple(_block(node, warnings) for node in tree.children)
    return ir.Document(blocks, tuple(warnings))


def _reference_no_footnotes(state, start, end, silent):
    if getLine(state, start).lstrip().startswith("[^"):
        return False
    return reference(state, start, end, silent)


def _table_no_loss(state, start, end, silent):
    offset = len(state.tokens)
    if not table(state, start, end, silent):
        return False
    if not silent:
        width = sum(token.type == "th_open" for token in state.tokens[offset:])
        for token in state.tokens[offset:]:
            if token.type != "tr_open" or token.map[0] == start:
                continue
            cells = escapedSplit(getLine(state, token.map[0]).strip())
            cells = cells[1:] if cells and cells[0] == "" else cells
            cells = cells[:-1] if cells and cells[-1] == "" else cells
            if len(cells) > width:
                state.env["warnings"].append(ir.Warning(
                    "malformed_table", "Extra table cells: the table is preserved as literal text.",
                    ir.SourceRange(*token.map)))
                content = state.getLines(start, state.line, state.blkIndent, True)
                del state.tokens[offset:]
                literal = state.push("literal_block", "", 0)
                literal.content, literal.map = content, [start, state.line]
                break
    return True


def _extension_warnings(state):
    # ponytail: syntax hints, not extension parsers; add a dialect plugin if rendering is needed.
    patterns = {
        "task_list": r"^\[[ xX]\]\s",
        "math": r"\$\$|\$[^\s$][^$]*\$",
        "strikethrough": r"~~\S.*?~~",
        "footnote": r"\[\^[^\]]+\]",
    }
    for token in state.tokens:
        if token.type != "inline":
            continue
        plain = [child.content for child in token.children if child.type == "text"]
        for name, pattern in patterns.items():
            if any(re.search(pattern, text) for text in plain):
                state.env["warnings"].append(ir.Warning(
                    "unsupported_" + name, f"Possible {name.replace('_', ' ')} syntax is preserved literally.",
                    ir.SourceRange(*token.map)))


def _source(node: SyntaxTreeNode) -> ir.SourceRange:
    assert node.map is not None
    return ir.SourceRange(*node.map)


def _warn_html(source: ir.SourceRange, warnings: list[ir.Warning]) -> None:
    warnings.append(ir.Warning("unsupported_html", "HTML is preserved as literal text.", source))


def _block(node: SyntaxTreeNode, warnings: list[ir.Warning]) -> ir.Block:
    source = _source(node)
    match node.type:
        case "paragraph":
            return ir.Paragraph(_inlines(node.children[0], source, warnings), source)
        case "heading":
            return ir.Heading(int(node.tag[1:]), _inlines(node.children[0], source, warnings), source)
        case "bullet_list" | "ordered_list":
            items = tuple(
                ir.ListItem(tuple(_block(child, warnings) for child in item.children))
                for item in node.children
            )
            return ir.ListBlock(node.type == "ordered_list", int(node.attrs.get("start", 1)), items, source)
        case "blockquote":
            return ir.Blockquote(tuple(_block(child, warnings) for child in node.children), source)
        case "fence" | "code_block":
            language = node.info.split()[0] if node.info.strip() else None
            if language == "mermaid":
                return ir.MermaidDiagram(node.content, source)
            return ir.CodeBlock(node.content, language, source)
        case "table":
            header = node.children[0].children[0]
            return ir.Table(
                _cells(header, warnings),
                tuple(_cells(row, warnings) for body in node.children[1:] for row in body.children),
                tuple(str(cell.attrs["style"]).removeprefix("text-align:")
                      if "style" in cell.attrs else None for cell in header.children),
                source,
            )
        case "hr":
            return ir.HorizontalRule(source)
        case "html_block":
            _warn_html(source, warnings)
            return ir.Paragraph((ir.TextSpan(node.content),), source)
        case "literal_block":
            return ir.Paragraph((ir.TextSpan(node.content),), source)
        case _:
            raise ValueError(f"Unexpected Markdown block: {node.type}")


def _cells(row: SyntaxTreeNode, warnings: list[ir.Warning]) -> tuple[ir.TableCell, ...]:
    return tuple(ir.TableCell(_inlines(cell.children[0], _source(row), warnings)) for cell in row.children)


def _inlines(
    node: SyntaxTreeNode,
    source: ir.SourceRange,
    warnings: list[ir.Warning],
    style: ir.TextSpan = ir.TextSpan(""),
) -> tuple[ir.Inline, ...]:
    inlines: list[ir.Inline] = []
    for child in node.children:
        match child.type:
            case "text" | "text_special" | "code_inline" | "html_inline":
                if child.type == "html_inline":
                    _warn_html(source, warnings)
                if child.content:
                    inlines.append(replace(style, text=child.content, code=child.type == "code_inline"))
            case "strong":
                inlines.extend(_inlines(child, source, warnings, replace(style, bold=True)))
            case "em":
                inlines.extend(_inlines(child, source, warnings, replace(style, italic=True)))
            case "link":
                inlines.extend(_inlines(child, source, warnings, replace(style, link=str(child.attrs["href"]))))
            case "softbreak" | "hardbreak":
                inlines.append(ir.LineBreak(hard=child.type == "hardbreak"))
            case "image":
                alt = "".join(
                    part.text if isinstance(part, ir.TextSpan) else
                    part.alt if isinstance(part, ir.Image) else "\n"
                    for part in _inlines(child, source, warnings)
                )
                title = str(child.attrs["title"]) if "title" in child.attrs else None
                inlines.append(ir.Image(str(child.attrs["src"]), alt, title, style.link))
            case _:
                raise ValueError(f"Unexpected Markdown inline: {child.type}")
    return tuple(inlines)
