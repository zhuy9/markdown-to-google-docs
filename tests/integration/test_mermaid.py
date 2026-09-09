from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from md2gdoc.mermaid import render_mermaid


class MermaidIntegrationTests(unittest.TestCase):
    def test_real_cli_produces_png_and_retains_source(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "diagram.png"
            source = "graph LR\n A[Markdown] --> B[Document]\n"
            self.assertEqual(render_mermaid(source, path), path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(path.with_suffix(".mmd").read_text(), source)

    def test_scale_raises_pixel_dimensions(self):
        source = "graph LR\n A[Markdown] --> B[Document]\n"
        with TemporaryDirectory() as directory:
            sizes = {}
            for scale in (1, 3):
                path = Path(directory) / f"scale-{scale}.png"
                render_mermaid(source, path, scale=scale)
                sizes[scale] = struct.unpack(">II", path.read_bytes()[16:24])
            self.assertEqual(sizes[3], tuple(value * 3 for value in sizes[1]))

    def test_real_cli_rejects_invalid_syntax(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.png"
            with self.assertRaisesRegex(RuntimeError, "Mermaid render failed"):
                render_mermaid("this is not mermaid", path)
            self.assertTrue(path.with_suffix(".mmd").is_file())


if __name__ == "__main__":
    unittest.main()
