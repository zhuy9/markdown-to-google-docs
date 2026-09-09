"""Build portable skill and Claude plugin ZIPs from one canonical source."""

import argparse
from importlib.metadata import metadata
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
NAME = "markdown-to-google-docs"


def build(output: Path) -> list[Path]:
    skill = ROOT / "skills" / NAME
    files = {path.relative_to(skill).as_posix(): path.read_bytes()
             for path in skill.rglob("*") if path.is_file() and path.suffix in {".md", ".py", ".yaml"}}
    files.update({f"scripts/md2gdoc/{path.name}": path.read_bytes()
                  for path in (ROOT / "src/md2gdoc").glob("*.py")})
    requirements = [item for item in metadata(NAME).get_all("Requires-Dist", []) if "extra ==" not in item]
    files["scripts/requirements.txt"] = ("\n".join(requirements) + "\n").encode()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    plugin = {f"skills/{NAME}/{name}": data for name, data in files.items()}
    plugin.update({f".claude-plugin/{path.name}": path.read_bytes()
                   for path in (ROOT / ".claude-plugin").glob("*.json")})
    plugin["LICENSE"] = files["LICENSE"]
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for kind, contents in (("skill", files), ("claude-plugin", plugin)):
        archive = output / f"{NAME}-{kind}.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED) as target:
            for name, data in sorted(contents.items()):
                info = ZipInfo(f"{NAME}/{name}")
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                target.writestr(info, data)
        archives.append(archive)
    return archives


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    for archive in build(parser.parse_args().output):
        print(archive)
