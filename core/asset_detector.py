"""Groups detected asset files into suggested PyInstaller data-file mappings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from models.project import AssetFile


@dataclass(frozen=True)
class SuggestedDataMapping:
    source: Path  # file or directory, relative to project root
    dest_in_bundle: str
    file_count: int
    category: str


class AssetDetector:
    """Turns a flat list of detected assets into folder-level bundle suggestions.

    Rather than suggesting one PyInstaller --add-data entry per file (which
    gets unwieldy fast), assets are grouped by their immediate parent
    directory relative to the project root.
    """

    def suggest_mappings(self, project_root: Path, assets: list[AssetFile]) -> list[SuggestedDataMapping]:
        groups: dict[Path, list[AssetFile]] = {}
        for asset in assets:
            try:
                rel_parent = asset.path.relative_to(project_root).parent
            except ValueError:
                continue
            groups.setdefault(rel_parent, []).append(asset)

        mappings: list[SuggestedDataMapping] = []
        for rel_parent, group_assets in sorted(groups.items(), key=lambda kv: str(kv[0])):
            dest = "." if str(rel_parent) == "." else str(rel_parent).replace("\\", "/")
            category_counts: dict[str, int] = {}
            for a in group_assets:
                category_counts[a.category] = category_counts.get(a.category, 0) + 1
            dominant_category = max(category_counts, key=category_counts.get)
            mappings.append(
                SuggestedDataMapping(
                    source=project_root / rel_parent,
                    dest_in_bundle=dest,
                    file_count=len(group_assets),
                    category=dominant_category,
                )
            )
        return mappings
