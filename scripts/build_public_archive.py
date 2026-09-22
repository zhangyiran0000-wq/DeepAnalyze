"""Build a source-only release archive from an explicit public-file allowlist."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FIXED = {
    "README.md", "LICENSE", "pyproject.toml", "main.py", ".gitignore", ".gitattributes",
    "docs/API.md", "docs/ARCHITECTURE.md", "scripts/build_public_archive.py", "scripts/serve_private.py",
    ".github/workflows/tests.yml",
    "tests/__init__.py",
}


def public_files(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    result = [root / name for name in FIXED if (root / name).is_file()]
    result.extend(path for path in (root / "src" / "deepanalyze").rglob("*")
                  if path.is_file() and path.suffix in {".py", ".html", ".css", ".js"}
                  and "__pycache__" not in path.parts)
    result.extend((root / "tests").glob("test_*.py"))
    for path in result:
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Public archive files must stay inside the source checkout.")
        if path.name.lower().startswith(("intent", "intend")):
            raise ValueError("Private intent documents must not be archived.")
        text = path.read_text(encoding="utf-8")
        if re.search(r"sk-[A-Za-z0-9_-]{32,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
            raise ValueError("Possible credential material detected in a public file.")
        if re.search(r"[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+|/(?:Users|home)/[A-Za-z0-9_.-]+", text):
            raise ValueError("A personal home path was detected in a public file.")
    return sorted(set(result))


def build(destination: Path | None = None, root: Path = ROOT) -> Path:
    root = root.resolve()
    paths = public_files(root)
    destination = destination or root / "dist" / "DeepAnalyze-source.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, "DeepAnalyze/" + path.relative_to(root).as_posix())
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Destination ZIP (default: dist/DeepAnalyze-source.zip)")
    args = parser.parse_args()
    output = build(args.output)
    print(f"Built {output.name} from {len(public_files())} public source files. No upload performed.")
