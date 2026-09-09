"""Render Mermaid locally using the official CLI; retain source beside PNGs."""

from pathlib import Path
import shutil
import subprocess


def render_mermaid(source: str, output: Path, scale: int = 3) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    input_path = output.with_suffix(".mmd")
    input_path.write_text(source, encoding="utf-8")
    executable = shutil.which("mmdc")
    candidates = [
        Path.cwd() / "node_modules/@mermaid-js/mermaid-cli/src/cli.js",
        Path(__file__).resolve().parents[2] / "node_modules/@mermaid-js/mermaid-cli/src/cli.js",
    ]
    if executable:
        candidates.insert(0, Path(executable).parent / "node_modules/@mermaid-js/mermaid-cli/src/cli.js")
    script = next((path for path in candidates if path.is_file()), None)
    if script and shutil.which("node"):
        command = [shutil.which("node"), str(script)]
    elif executable and Path(executable).suffix.lower() != ".cmd":
        command = [executable]
    else:
        raise RuntimeError("Install Mermaid CLI with npm install -g @mermaid-js/mermaid-cli.")
    try:
        # ponytail: scale is the only resolution knob; the renderer caps display width,
        # so a higher scale raises effective DPI. Raise it if diagrams look soft in print.
        subprocess.run(command + ["-i", str(input_path), "-o", str(output), "-b", "white",
                                  "-s", str(scale)],
                       check=True, capture_output=True, text=True, timeout=60)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Mermaid render failed: " + error.stderr.strip()[:600]) from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Mermaid rendering exceeded 60 seconds.") from error
    if not output.is_file():
        raise RuntimeError("Mermaid CLI did not produce a PNG.")
    return output
