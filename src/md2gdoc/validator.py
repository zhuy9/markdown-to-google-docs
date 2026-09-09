"""Compare source structure with saved output, independently of the renderer."""

from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

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
    return counts, links, blocks


def _report(expected, actual, checks, scope):
    counts = {key: {"expected": value, "actual": actual[key]} for key, value in expected.items()}
    checks["element_counts"] = expected == actual
    return {"scope": scope, "ok": all(checks.values()), "counts": counts, "checks": checks}


def _box(document) -> tuple[int, int]:
    """Printable area of the first section, in EMU."""
    section = document.sections[0]
    return (section.page_width - section.left_margin - section.right_margin,
            section.page_height - section.top_margin - section.bottom_margin)


def _source_paragraphs(blocks, depth=0, bullet=None):
    for index, block in enumerate(blocks):
        marker = bullet if index == 0 else None
        if isinstance(block, ir.Blockquote):
            yield from _source_paragraphs(block.blocks, depth + 1)
        elif isinstance(block, ir.ListBlock):
            for item in block.items:
                marker = (min(depth, 8), block.ordered, block.start)
                if not item.blocks or not isinstance(item.blocks[0], (ir.Paragraph, ir.Heading)):
                    yield ("", (), 0, (depth + 1) * 18, marker, False)
                    marker = None
                yield from _source_paragraphs(item.blocks, depth + 1, marker)
        elif isinstance(block, ir.Table):
            for row in (block.header, *block.rows):
                for cell in row:
                    yield (_text(cell.inlines), cell.inlines, 0, 0, None, False)
        elif isinstance(block, (ir.Paragraph, ir.Heading, ir.CodeBlock)):
            code = isinstance(block, ir.CodeBlock)
            inlines = () if code else block.inlines
            yield (block.text if code else _text(inlines), inlines,
                   block.level if isinstance(block, ir.Heading) else 0, depth * 18, marker, code)


def _paragraph_checks(source, observed):
    """Match whole paragraphs in order; native code may span several paragraphs."""
    checks = dict(text_preserved=True, paragraph_structure=True, inline_formatting=True, code_formatting=True)
    cursor = 0
    code_count = 0
    for text, inlines, heading, indent, bullet, code in _source_paragraphs(source.blocks):
        text = text.rstrip("\n")
        # Image-only paragraphs and empty table cells have separate structural counts.
        if not text and not (heading or bullet or code):
            continue
        while cursor < len(observed) and not observed[cursor]["text"].strip("\n") and text:
            cursor += 1
        if cursor == len(observed):
            checks["text_preserved"] = False
            break
        paragraph = observed[cursor]
        group = [paragraph]
        cursor += 1
        actual = paragraph["text"].rstrip("\n")
        while code and actual != text and text.startswith(actual + "\n") and cursor < len(observed):
            group.append(observed[cursor])
            actual += "\n" + observed[cursor]["text"].rstrip("\n")
            cursor += 1
        checks["text_preserved"] &= actual == text
        checks["paragraph_structure"] &= all(
            p["heading"] == heading and p["indent"] >= indent and p["bullet"] == bullet for p in group)
        if code:
            formatted = all(
                style.get("code") and style.get("shaded")
                for p in group for char, style in p["characters"] if not char.isspace())
            checks["code_formatting"] &= formatted
            code_count += actual == text and formatted
        elif actual == text:
            required = []
            for inline in inlines:
                if isinstance(inline, ir.TextSpan):
                    required.extend((char, inline) for char in inline.text)
                elif isinstance(inline, ir.LineBreak):
                    required.append(("\n" if inline.hard else " ", None))
            characters = paragraph["characters"]
            checks["inline_formatting"] &= all(
                i < len(characters) and all(not wanted or characters[i][1].get(key) == wanted
                    for key, wanted in (("bold", span.bold), ("italic", span.italic),
                                        ("code", span.code), ("link", span.link)))
                for i, (char, span) in enumerate(required) if span and not char.isspace())
    checks["text_preserved"] &= not any(p["text"].strip() for p in observed[cursor:])
    return checks, code_count


def _docx_paragraph(paragraph, document):
    numbering = paragraph._p.xpath("./w:pPr/w:numPr")
    bullet = None
    if numbering:
        level = paragraph._p.pPr.numPr.ilvl.val
        identifier = paragraph._p.pPr.numPr.numId.val
        root = document.part.numbering_part.element
        abstract = root.xpath(f'./w:num[@w:numId="{identifier}"]/w:abstractNumId/@w:val')[0]
        definition = root.xpath(f'./w:abstractNum[@w:abstractNumId="{abstract}"]/w:lvl[@w:ilvl="{level}"]')[0]
        bullet = (level, definition.find(qn("w:numFmt")).get(qn("w:val")) == "decimal",
                  int(definition.find(qn("w:start")).get(qn("w:val"))))
    characters = []
    for part in paragraph.iter_inner_content():
        for run in getattr(part, "runs", (part,)):
            style = {"bold": run.bold, "italic": run.italic, "code": run.font.name == "Courier New",
                     "shaded": bool(paragraph._p.xpath("./w:pPr/w:shd") or run._r.xpath("./w:rPr/w:shd")),
                     "link": getattr(part, "url", None)}
            characters.extend((char, style) for char in run.text)
    return {"text": paragraph.text, "characters": characters,
            "heading": int(paragraph.style.name.split()[-1]) if paragraph.style.name.startswith("Heading ") else 0,
            "indent": (paragraph.paragraph_format.left_indent or 0) / 12700, "bullet": bullet}


def validate_docx(source: ir.Document, path: Path) -> dict:
    document = Document(path)
    root = document.element
    paragraphs = [Paragraph(node, document) for node in root.xpath(".//w:body//w:p")]
    code = [paragraph for paragraph in paragraphs if paragraph.style.name == "Code Block"]
    pictures = root.xpath(".//wp:docPr")
    diagrams = [picture for picture in pictures if picture.get("name", "").startswith("mermaid-")]
    ids = root.xpath(".//w:hyperlink/@r:id") + root.xpath(".//a:hlinkClick/@r:id")
    links = {document.part.rels[identifier].target_ref for identifier in ids}
    expected, expected_links, blocks = _expected(source)
    actual = {
        "headings": sum(paragraph.style.name.startswith("Heading ") for paragraph in paragraphs),
        "tables": len(root.xpath(".//w:body//w:tbl")),
        "code_blocks": len(code), "images": len(pictures) - len(diagrams), "mermaid": len(diagrams),
        "rules": len(root.xpath(".//w:pPr/w:pBdr/w:bottom")),
        "list_items": len(root.xpath(".//w:pPr/w:numPr")), "link_destinations": len(links),
    }
    checks = {
        "links_preserved": expected_links == links,
        "images_fit_page": all(shape.width <= _box(document)[0] and shape.height <= _box(document)[1]
                               for shape in document.inline_shapes),
        "table_shape": [(len(table.rows), len(table.columns)) for table in document.tables] ==
                       [(1 + len(block.rows), len(block.header)) for block in blocks if isinstance(block, ir.Table)],
    }
    paragraph_checks, _ = _paragraph_checks(source, [_docx_paragraph(p, document) for p in paragraphs])
    checks.update(paragraph_checks)
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


def _google_contexts(document):
    if not document.get("tabs"):
        yield document
    for tab in document.get("tabs", []):
        yield tab.get("documentTab", tab)
        if tab.get("childTabs"):
            yield from _google_contexts({"tabs": tab["childTabs"]})


def _google_paragraph(paragraph, context):
    style = paragraph.get("paragraphStyle", {})
    named = {s["namedStyleType"]: s.get("textStyle", {})
             for s in (context.get("namedStyles") or {}).get("styles", [])}
    inherited = named.get("NORMAL_TEXT", {}) | named.get(style.get("namedStyleType"), {})
    characters = []
    for element in paragraph.get("elements", []):
        run = element.get("textRun", {})
        text_style = inherited | run.get("textStyle", {})
        flags = {"bold": text_style.get("bold"), "italic": text_style.get("italic"),
                 "code": text_style.get("weightedFontFamily", {}).get("fontFamily") == "Courier New",
                 "shaded": bool(text_style.get("backgroundColor") or style.get("shading", {}).get("backgroundColor")),
                 "link": text_style.get("link", {}).get("url")}
        characters.extend((char, flags) for char in run.get("content", "").replace("\u000b", "\n"))
    bullet = None
    if "bullet" in paragraph:
        marker = paragraph["bullet"]
        level = marker.get("nestingLevel", 0)
        levels = (context.get("lists") or {}).get(marker.get("listId"), {}).get("listProperties", {}).get("nestingLevels", [])
        definition = levels[level] if level < len(levels) else {}
        bullet = (level, definition.get("glyphType") == "DECIMAL", definition.get("startNumber", 1))
    return {"text": "".join(char for char, _ in characters), "characters": characters,
            "heading": int(style["namedStyleType"][-1]) if style.get("namedStyleType", "").startswith("HEADING_") else 0,
            "indent": style.get("indentStart", {}).get("magnitude", 0), "bullet": bullet}


def validate_google(source: ir.Document, document: dict) -> dict:
    elements = list(_google_tabs(document["tabs"])) if document.get("tabs") else list(_google_elements(document.get("body", {}).get("content", [])))
    paragraphs = [element["paragraph"] for element in elements if "paragraph" in element]
    runs = [element.get("textRun", {}) for paragraph in paragraphs for element in paragraph.get("elements", [])]
    links = {run["textStyle"]["link"]["url"] for run in runs if run.get("textStyle", {}).get("link", {}).get("url")}
    expected, expected_links, blocks = _expected(source)
    expected["images"] += expected.pop("mermaid")
    actual = {
        "headings": sum(paragraph.get("paragraphStyle", {}).get("namedStyleType", "").startswith("HEADING_") for paragraph in paragraphs),
        "tables": sum("table" in element for element in elements),
        "images": sum("inlineObjectElement" in element for paragraph in paragraphs for element in paragraph.get("elements", [])),
        "rules": sum(paragraph.get("paragraphStyle", {}).get("borderBottom", {}).get("width", {}).get("magnitude", 0) > 0 or
                     any("horizontalRule" in element for element in paragraph.get("elements", [])) for paragraph in paragraphs),
        "list_items": sum("bullet" in paragraph for paragraph in paragraphs), "link_destinations": len(links),
    }
    checks = {"links_preserved": expected_links == links}
    observed = [_google_paragraph(e["paragraph"], context) for context in _google_contexts(document)
                for e in _google_elements((context.get("body") or {}).get("content", [])) if "paragraph" in e]
    paragraph_checks, actual["code_blocks"] = _paragraph_checks(source, observed)
    checks.update(paragraph_checks)
    checks["table_shape"] = [tuple(len(row.get("tableCells", [])) for row in e["table"].get("tableRows", []))
                             for e in elements if "table" in e] == [
                                 (len(b.header),) * (1 + len(b.rows)) for b in blocks if isinstance(b, ir.Table)]
    return _report(expected, actual, checks, "google-readback")
