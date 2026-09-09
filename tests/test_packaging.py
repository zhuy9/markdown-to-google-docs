import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_archives_run_outside_checkout_and_share_skill(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = subprocess.run([sys.executable, str(ROOT / "tools/build_skill.py"), "--output", str(directory)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            source = directory / "input.md"
            source.write_text("# Packaged\n\n**Bold** and `code`.", encoding="utf-8")
            canonical = (ROOT / "skills/markdown-to-google-docs/SKILL.md").read_bytes()
            for archive in directory.glob("*.zip"):
                with self.subTest(archive=archive.name), ZipFile(archive) as bundle:
                    names = bundle.namelist()
                    self.assertFalse(any(part in {".temp", ".git", "node_modules", "__pycache__"}
                                         for name in names for part in Path(name).parts))
                    skill_name = next(name for name in names if name.endswith("/SKILL.md"))
                    self.assertEqual(bundle.read(skill_name), canonical)
                    self.assertIn(b"python-docx", bundle.read(skill_name.replace("SKILL.md", "scripts/requirements.txt")))
                    destination = directory / archive.stem
                    bundle.extractall(destination)
                    script = destination / skill_name.replace("SKILL.md", "scripts/convert.py")
                    output = destination / "result.docx"
                    run = subprocess.run([sys.executable, str(script), str(source), "-o", str(output)],
                                         cwd=directory, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertTrue(json.loads(output.with_suffix(".report.json").read_text())["ok"])

    def test_skill_metadata_and_marketplace_resolve(self):
        skill = ROOT / "skills/markdown-to-google-docs"
        frontmatter = yaml.safe_load((skill / "SKILL.md").read_text().split("---", 2)[1])
        self.assertEqual(frontmatter["name"], skill.name)
        self.assertTrue(frontmatter["description"])
        ui = yaml.safe_load((skill / "agents/openai.yaml").read_text())["interface"]
        self.assertIn("$markdown-to-google-docs", ui["default_prompt"])
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        plugin = ROOT / marketplace["plugins"][0]["source"]
        self.assertTrue((plugin / "skills" / skill.name / "SKILL.md").is_file())
        manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
        from importlib.metadata import version
        self.assertEqual(manifest["version"], version("markdown-to-google-docs"))
