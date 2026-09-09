from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from md2gdoc.models import (
    Blockquote,
    CodeBlock,
    Document,
    Heading,
    HorizontalRule,
    Image,
    LineBreak,
    ListBlock,
    MermaidDiagram,
    Paragraph,
    SourceRange,
    Table,
    TextSpan,
)
from md2gdoc.parser import parse_markdown


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParserTests(unittest.TestCase):
    def test_overflow_table_cells_survive_in_literal_fallback(self):
        for prefix in ("", "> ", "  "):
            markdown = "\n".join(prefix + line for line in ("| H |", "| --- |", "| kept | LOST |"))
            document = parse_markdown(markdown)
            block = document.blocks[0]
            if isinstance(block, Blockquote):
                block = block.blocks[0]
            self.assertIsInstance(block, Paragraph)
            self.assertIn("LOST", block.inlines[0].text)
            self.assertEqual(document.warnings[0].code, "malformed_table")
            self.assertEqual(document.warnings[0].source, SourceRange(2, 3))

    def test_footnotes_stay_literal_instead_of_becoming_reference_links(self):
        document = parse_markdown('Note[^1].\n\n[^1]: https://example.com/ "Explanation"')
        self.assertEqual(len(document.blocks), 2)
        self.assertIn('"Explanation"', document.blocks[1].inlines[0].text)
        self.assertFalse(any(span.link for block in document.blocks for span in block.inlines))
        self.assertTrue(all(w.code == "unsupported_footnote" for w in document.warnings))

    def test_extension_warnings_exclude_code_and_escaped_syntax(self):
        document = parse_markdown('- [x] Done\n\n$x^2$ and ~~old~~ and [^note].')
        self.assertEqual({w.code for w in document.warnings}, {
            "unsupported_task_list", "unsupported_math", "unsupported_strikethrough", "unsupported_footnote"})
        self.assertEqual(parse_markdown('`$x$ ~~old~~ [^note]`\n\n```\n- [x] Done\n```').warnings, ())
        self.assertEqual(parse_markdown(r'\$x\$ and \~\~old\~\~ and \[^note]').warnings, ())

    def test_empty_input(self):
        for text in ("", "\n\n", " \t\r\n"):
            with self.subTest(text=text):
                self.assertEqual(parse_markdown(text), Document((), ()))

    def test_basic_fixture_structure_and_source_ranges(self):
        document = parse_markdown(fixture("basic.md"))
        self.assertEqual(
            [type(block) for block in document.blocks],
            [Heading, Paragraph, Heading, Paragraph, Blockquote, HorizontalRule, Paragraph],
        )
        self.assertEqual(document.blocks[0], Heading(1, (TextSpan("Basic document"),), SourceRange(0, 1)))
        self.assertEqual(document.blocks[1].source, SourceRange(2, 4))
        self.assertEqual(document.blocks[2], Heading(2, (TextSpan("Unicode 😀"),), SourceRange(5, 6)))
        self.assertEqual(document.blocks[3].inlines, (TextSpan("Café and 中文 preserve their text."),))
        self.assertEqual(document.blocks[4].blocks[0].source, SourceRange(9, 10))
        self.assertEqual(document.blocks[5].source, SourceRange(11, 12))
        self.assertEqual(document.warnings, ())

    def test_basic_fixture_inline_styles_and_breaks(self):
        document = parse_markdown(fixture("basic.md"))
        inlines = document.blocks[1].inlines
        self.assertIn(TextSpan("bold", bold=True), inlines)
        self.assertIn(TextSpan("italic", italic=True), inlines)
        self.assertIn(TextSpan("both", bold=True, italic=True), inlines)
        self.assertIn(TextSpan("a link", link="https://example.com/"), inlines)
        self.assertIn(LineBreak(hard=False), inlines)
        self.assertIn(TextSpan("inline code", code=True), document.blocks[4].blocks[0].inlines)
        self.assertEqual(
            document.blocks[-1].inlines,
            (TextSpan("Line with a hard break."), LineBreak(hard=True), TextSpan("Next line.")),
        )

    def test_style_scope_and_links_combine_without_leaking(self):
        paragraph = parse_markdown("**bold *both* bold** plain [**`x`**](https://example.com/)").blocks[0]
        self.assertEqual(paragraph.inlines, (
            TextSpan("bold ", bold=True),
            TextSpan("both", bold=True, italic=True),
            TextSpan(" bold", bold=True),
            TextSpan(" plain "),
            TextSpan("x", bold=True, code=True, link="https://example.com/"),
        ))

    def test_reference_links_autolinks_and_entities(self):
        document = parse_markdown(
            "[reference][id] &amp; <https://example.com/> \\*literal\\*\n\n"
            "[id]: https://example.com/reference\n"
        )
        self.assertEqual(len(document.blocks), 1)
        self.assertEqual(document.blocks[0].inlines, (
            TextSpan("reference", link="https://example.com/reference"),
            TextSpan(" & "),
            TextSpan("https://example.com/", link="https://example.com/"),
            TextSpan(" *literal*"),
        ))

    def test_setext_and_empty_headings(self):
        document = parse_markdown("Title\n=====\n\nSubtitle\n--------\n\n###\n")
        self.assertEqual(document.blocks, (
            Heading(1, (TextSpan("Title"),), SourceRange(0, 2)),
            Heading(2, (TextSpan("Subtitle"),), SourceRange(3, 5)),
            Heading(3, (), SourceRange(6, 7)),
        ))

    def test_code_fixture_preserves_fences_and_image_syntax_as_code(self):
        document = parse_markdown(fixture("code-blocks.md"))
        self.assertEqual(document.blocks[2], CodeBlock(
            'def greet(name):\n    message = f"Hello, {name}"\n\n    return message\n',
            "python", SourceRange(4, 10),
        ))
        self.assertEqual(document.blocks[3], CodeBlock(
            'Literal fenced Markdown:\n```python\nprint("not another block")\n```\n'
            '![not an image](literal.png)\n',
            "text", SourceRange(11, 18),
        ))
        self.assertEqual(document.warnings, ())

    def test_code_normalizes_line_endings_but_preserves_tabs_and_blank_lines(self):
        document = parse_markdown("```python title\r\n\tvalue = 1  \r\n\r\n\treturn value\r\n```\r\n")
        self.assertEqual(document.blocks, (
            CodeBlock("\tvalue = 1  \n\n\treturn value\n", "python", SourceRange(0, 5)),
        ))

    def test_indented_unlabelled_and_unclosed_code(self):
        cases = (
            ("    one\n        two\n", "one\n    two\n", SourceRange(0, 2)),
            ("```\nvalue\n```\n", "value\n", SourceRange(0, 3)),
            ("```\nvalue", "value", SourceRange(0, 2)),
        )
        for text, code, source in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_markdown(text).blocks, (CodeBlock(code, None, source),))

    def test_mermaid_fixture_preserves_valid_and_invalid_source_without_rendering(self):
        document = parse_markdown(fixture("mermaid.md"))
        self.assertEqual(document.blocks[1:], (
            MermaidDiagram("graph TD\n  A[Markdown] --> B[Document IR]\n  B --> C[Google Docs]\n", SourceRange(2, 7)),
            MermaidDiagram("this is deliberately invalid mermaid\n", SourceRange(8, 11)),
        ))
        self.assertEqual(document.warnings, ())

    def test_table_fixture_retains_alignment_inline_content_and_empty_cells(self):
        table = parse_markdown(fixture("tables.md")).blocks[1]
        self.assertIsInstance(table, Table)
        self.assertEqual(table.source, SourceRange(2, 7))
        self.assertEqual(table.alignments, ("left", "center", "right"))
        self.assertEqual([cell.inlines for cell in table.header], [
            (TextSpan("Feature"),), (TextSpan("State"),), (TextSpan("Count"),),
        ])
        self.assertEqual(len(table.rows), 3)
        self.assertEqual(table.rows[0][0].inlines, (TextSpan("Code", bold=True),))
        self.assertEqual(table.rows[0][1].inlines, (TextSpan("planned", code=True),))
        self.assertEqual(table.rows[1][0].inlines, (TextSpan("Links", link="https://example.com/"),))
        self.assertEqual(table.rows[2][0].inlines, (TextSpan("Escaped | pipe"),))
        self.assertEqual(table.rows[2][1].inlines, ())

    def test_table_with_only_a_header(self):
        table = parse_markdown("| A | B |\n| --- | --- |\n").blocks[0]
        self.assertEqual(table.alignments, (None, None))
        self.assertEqual(table.rows, ())

    def test_nested_lists_keep_start_and_multiple_paragraphs(self):
        document = parse_markdown(fixture("kitchen-sink.md"))
        ordered = document.blocks[2]
        self.assertIsInstance(ordered, ListBlock)
        self.assertTrue(ordered.ordered)
        self.assertEqual(ordered.start, 3)
        self.assertEqual(len(ordered.items), 2)
        self.assertEqual(ordered.source, SourceRange(4, 11))
        nested = ordered.items[1].blocks[1]
        self.assertIsInstance(nested, ListBlock)
        self.assertFalse(nested.ordered)
        self.assertEqual(nested.start, 1)
        self.assertEqual(len(nested.items[1].blocks), 2)
        self.assertEqual(nested.items[1].blocks[1], Paragraph(
            (TextSpan("A second paragraph in the same item."),), SourceRange(9, 10),
        ))
        quote = document.blocks[3]
        self.assertIsInstance(quote, Blockquote)
        self.assertIsInstance(quote.blocks[1], ListBlock)
        self.assertEqual(quote.blocks[0].source, SourceRange(11, 12))

    def test_image_references_and_titles_are_not_resolved(self):
        paragraph = parse_markdown(fixture("kitchen-sink.md")).blocks[6]
        self.assertEqual(paragraph.inlines, (Image("assets/example.png", "Local image", "Example figure"),))
        paragraph = parse_markdown('Before ![**Alt** &amp; `code`](https://example.com/image.png) after').blocks[0]
        self.assertEqual(paragraph.inlines, (
            TextSpan("Before "), Image("https://example.com/image.png", "Alt & code"), TextSpan(" after"),
        ))

    def test_linked_image_retains_the_link_destination(self):
        paragraph = parse_markdown("[![Alt](image.png)](https://example.com/target)").blocks[0]
        self.assertEqual(paragraph.inlines, (Image("image.png", "Alt", link="https://example.com/target"),))

    def test_html_block_is_literal_and_warns_with_source_location(self):
        document = parse_markdown(fixture("kitchen-sink.md"))
        html = '<details>\n<summary>Unsupported HTML</summary>\nKeep this content visible and report a warning.\n</details>\n'
        self.assertEqual(document.blocks[-1], Paragraph((TextSpan(html),), SourceRange(33, 37)))
        self.assertEqual(len(document.warnings), 1)
        self.assertEqual(document.warnings[0].code, "unsupported_html")
        self.assertEqual(document.warnings[0].source, SourceRange(33, 37))

    def test_inline_html_and_table_html_stay_literal_with_warnings(self):
        document = parse_markdown("Text <b>bold</b>.\n\n| H |\n| --- |\n| <br> |\n")
        self.assertEqual("".join(span.text for span in document.blocks[0].inlines), "Text <b>bold</b>.")
        self.assertEqual(document.blocks[1].rows[0][0].inlines, (TextSpan("<br>"),))
        self.assertEqual([warning.source for warning in document.warnings], [
            SourceRange(0, 1), SourceRange(0, 1), SourceRange(4, 5),
        ])
        self.assertTrue(all(warning.code == "unsupported_html" for warning in document.warnings))

    def test_windows_and_unix_line_endings_have_identical_ir(self):
        text = fixture("kitchen-sink.md")
        self.assertEqual(parse_markdown(text.replace("\n", "\r\n")), parse_markdown(text))
        self.assertEqual(parse_markdown(text.replace("\n", "\r")), parse_markdown(text))

    def test_fixtures_parse_deterministically_without_network_access(self):
        for path in sorted(FIXTURES.glob("*.md")):
            with self.subTest(fixture=path.name):
                text = path.read_text(encoding="utf-8")
                with patch.object(socket, "socket", side_effect=AssertionError("Parser attempted network access")):
                    self.assertEqual(parse_markdown(text), parse_markdown(text))

    def test_warnings_do_not_leak_between_documents(self):
        self.assertTrue(parse_markdown("<div>HTML</div>\n").warnings)
        self.assertEqual(parse_markdown("plain").warnings, ())


if __name__ == "__main__":
    unittest.main()
