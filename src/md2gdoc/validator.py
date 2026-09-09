"""Compare source structure with saved output, independently of the renderer."""

from collections import Counter
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

from . import models as ir


def _blocks(blocks):
    for block in blocks:
        yield block
        if isinstance(block, ir.Blockquote):
            yield from _blocks(block.blocks)
        elif isinstance(block, ir.ListBlock):
            for item in block.items:
                yield from _blocks(item.blocks)


def _inline_groups(block):
    if isinstance(block, (ir.Paragraph, ir.Heading)):
        yield block.inlines
    elif isinstance(block, ir.Table):
        for row in (block.header, *block.rows):
            for cell in row:
                yield cell.inlines


def _text(inlines):
    return "".join(part.text if isinstance(part, ir.TextSpan) else
                   ("\n" if part.hard else " ") if isinstance(part, ir.LineBreak) else ""
                   for part in inlines)


def _expected(document):
    blocks = list(_blocks(document.blocks))
    inlines = [part for block in blocks for group in _inline_groups(block) for part in group]
    links = {part.link for part in inlines if isinstance(part, (ir.TextSpan, ir.Image)) and part.link}
    counts = {
        "headings": sum(isinstance(block, ir.Heading) for block in blocks),
        "tables": sum(isinstance(block, ir.Table) for block in blocks),
        "code_blocks": sum(isinstance(block, ir.CodeBlock) for block in blocks),
        "images": sum(isinstance(part, ir.Image) for part in inlines),
        "mermaid": sum(isinstance(block, ir.MermaidDiagram) for block in blocks),
        "rules": sum(isinstance(block, ir.HorizontalRule) for block in blocks),
        "list_items": sum(len(block.items) for block in blocks if isinstance(block, ir.ListBlock)),
        "link_destinations": len(links),
    }
    texts = [block.text for block in blocks if isinstance(block, ir.CodeBlock)]
    texts.extend(_text(group) for block in blocks for group in _inline_groups(block))
    return counts, Counter(text for text in texts if text), links, blocks


def _report(expected, actual, checks, scope):
    counts = {key: {"expected": value, "actual": actual[key]} for key, value in expected.items()}
    checks["element_counts"] = expected == actual
    return {"scope": scope, "ok": all(checks.values()), "counts": counts, "checks": checks}


def _box(document) -> tuple[int, int]:
    """Printable area of the first section, in EMU."""
    section = document.sections[0]
    return (section.page_width - section.left_margin - section.right_margin,
            section.page_height - section.top_margin - section.bottom_margin)


def validate_docx(source: ir.Document, path: Path) -> dict:
    document = Document(path)
    root = document.element
    paragraphs = [Paragraph(node, document) for node in root.xpath(".//w:body//w:p")]
    code = [paragraph for paragraph in paragraphs if paragraph.style.name == "Code Block"]
    pictures = root.xpath(".//wp:docPr")
    diagrams = [picture for picture in pictures if picture.get("name", "").startswith("mermaid-")]
    ids = root.xpath(".//w:hyperlink/@r:id") + root.xpath(".//a:hlinkClick/@r:id")
    links = {document.part.rels[identifier].target_ref for identifier in ids}
    expected, texts, expected_links, blocks = _expected(source)
    actual = {
        "headings": sum(paragraph.style.name.startswith("Heading ") for paragraph in paragraphs),
        "tables": len(root.xpath(".//w:body//w:tbl")),
        "code_blocks": len(code), "images": len(pictures) - len(diagrams), "mermaid": len(diagrams),
        "rules": len(root.xpath(".//w:pPr/w:pBdr/w:bottom")),
        "list_items": len(root.xpath(".//w:pPr/w:numPr")), "link_destinations": len(links),
    }
    checks = {
        "text_preserved": not (texts - Counter(paragraph.text for paragraph in paragraphs if paragraph.text)),
        "links_preserved": expected_links == links,
        "code_formatting": all(paragraph._p.xpath("./w:pPr/w:shd") and
                               all(run.font.name == "Courier New" for run in paragraph.runs) for paragraph in code),
        "images_fit_page": all(shape.width <= _box(document)[0] and shape.height <= _box(document)[1]
                               for shape in document.inline_shapes),
        "table_shape": [(len(table.rows), len(table.columns)) for table in document.tables] ==
                       [(1 + len(block.rows), len(block.header)) for block in blocks if isinstance(block, ir.Table)],
    }
    return _report(expected, actual, checks, "local-docx")


def _google_elements(content):
    for element in content:
        yield element
        for row in element.get("table", {}).get("tableRows", []):
            for cell in row.get("tableCells", []):
                yield from _google_elements(cell.get("content", []))


def _google_tabs(tabs):
    for tab in tabs:
        yield from _google_elements((tab.get("documentTab", tab).get("body") or {}).get("content", []))
        yield from _google_tabs(tab.get("childTabs", []))


def validate_google(source: ir.Document, document: dict) -> dict:
    elements = list(_google_tabs(document["tabs"])) if document.get("tabs") else list(_google_elements(document.get("body", {}).get("content", [])))
    paragraphs = [element["paragraph"] for element in elements if "paragraph" in element]
    runs = [element.get("textRun", {}) for paragraph in paragraphs for element in paragraph.get("elements", [])]
    links = {run["textStyle"]["link"]["url"] for run in runs if run.get("textStyle", {}).get("link", {}).get("url")}
    expected, texts, expected_links, blocks = _expected(source)
    expected["images"] += expected.pop("mermaid")
    mono = "".join(run.get("content", "") for run in runs if run.get("textStyle", {}).get("weightedFontFamily", {}).get("fontFamily") == "Courier New").replace("\u000b", "\n")
    shaded = "".join(element.get("textRun", {}).get("content", "")
                     for paragraph in paragraphs for element in paragraph.get("elements", [])
                     if paragraph.get("paragraphStyle", {}).get("shading", {}).get("backgroundColor") or
                     element.get("textRun", {}).get("textStyle", {}).get("backgroundColor")).replace("\u000b", "\n")
    codes = [block.text.rstrip("\n") for block in blocks if isinstance(block, ir.CodeBlock)]
    actual = {
        "headings": sum(paragraph.get("paragraphStyle", {}).get("namedStyleType", "").startswith("HEADING_") for paragraph in paragraphs),
        "tables": sum("table" in element for element in elements),
        "code_blocks": sum(code in mono for code in codes),
        "images": sum("inlineObjectElement" in element for paragraph in paragraphs for element in paragraph.get("elements", [])),
        "rules": sum(paragraph.get("paragraphStyle", {}).get("borderBottom", {}).get("width", {}).get("magnitude", 0) > 0 or
                     any("horizontalRule" in element for element in paragraph.get("elements", [])) for paragraph in paragraphs),
        "list_items": sum("bullet" in paragraph for paragraph in paragraphs), "link_destinations": len(links),
    }
    visible = " ".join("".join(run.get("content", "") for run in runs).split())
    normalized = Counter(" ".join(text.split()) for text in texts.elements())
    checks = {
        "text_preserved": all(visible.count(text) >= count for text, count in normalized.items() if text),
        "links_preserved": expected_links == links,
        "code_formatting": all(code in mono and code in shaded for code in codes),
    }
    return _report(expected, actual, checks, "google-readback")
