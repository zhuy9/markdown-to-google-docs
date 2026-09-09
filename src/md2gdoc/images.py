"""Resolve image references without changing the document IR."""

from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen


def resolve_image(src: str, base_dir: Path, cache_dir: Path, allow_remote: bool = False) -> Path:
    url = urlsplit(src)
    if url.scheme in ("http", "https"):
        if not allow_remote:
            raise ValueError("Remote images require --allow-remote-images.")
        with urlopen(src, timeout=20) as response:
            data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("Image exceeds 20 MiB.")
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / (sha256(data).hexdigest() + ".image")
        path.write_bytes(data)
        return path
    if url.scheme and not Path(src).is_absolute():
        raise ValueError("Use a local image path or an HTTP(S) URL.")
    path = base_dir / unquote(src)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {src}")
    return path
