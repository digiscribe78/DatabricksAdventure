"""Read the world manifest (content/manifest.yaml)."""

from pathlib import Path

import yaml


def load_manifest(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def doc_metadata(manifest: dict) -> dict[str, dict]:
    """Map each lorebook's PDF stem to the metadata stored on its chunks."""
    return {
        Path(d["file"]).stem: {"doc_type": d["doc_type"], "location_id": d["location_id"]}
        for d in manifest["documents"]
    }
