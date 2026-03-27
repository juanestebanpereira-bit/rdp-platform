"""
MkDocs build hooks.

on_pre_build:
  1. Copies reference documentation from rtl_rdp/ into docs/reference/.
  2. Generates a data dictionary page per component from dwh_views schema.yml
     and doc blocks, writing docs/{subject_area}/{component}/dictionary.md.

Both outputs are gitignored — sources of truth live in rtl_rdp/.
"""

import re
import shutil
import yaml
from pathlib import Path

BASE = Path(__file__).parent
RDP  = BASE / "rtl_rdp"

REFERENCE_FILES = {
    "contract.md":         RDP / "CONTRACT.md",
    "data_model_index.md": RDP / "DATA_MODEL.md",
    "style_guide.md":      RDP / "STYLE_GUIDE.md",
}


def _load_doc_blocks() -> dict:
    """Parse all {% docs name %}...{% enddocs %} blocks from rtl_rdp/models/*.md."""
    docs = {}
    for md_file in (RDP / "models").glob("*.md"):
        for m in re.finditer(
            r"\{%-?\s*docs\s+(\w+)\s*-?%\}(.*?)\{%-?\s*enddocs\s*-?%\}",
            md_file.read_text(),
            re.DOTALL,
        ):
            docs[m.group(1)] = m.group(2).strip()
    return docs


def _resolve(description: str, doc_blocks: dict) -> str:
    """Replace {{ doc('name') }} with the actual doc block text."""
    m = re.match(r'\{\{\s*doc\([\'"](\w+)[\'"]\)\s*\}\}', description.strip())
    if m:
        return doc_blocks.get(m.group(1), f"*(missing doc block: {m.group(1)})*")
    return description.strip()


def _title(slug: str) -> str:
    return slug.replace("_", " ").title()


def _generate_dictionaries(docs_dir: Path) -> None:
    """
    For each dwh_views/{subject_area}/{component}/schema.yml, generate a
    dictionary.md page under docs/subject_areas/{subject_area}/{component}/.
    """
    doc_blocks = _load_doc_blocks()
    dwh_views_root = RDP / "models" / "dwh_views"

    for schema_path in sorted(dwh_views_root.rglob("schema.yml")):
        rel = schema_path.relative_to(dwh_views_root)
        if len(rel.parts) != 3:          # expect subject_area/component/schema.yml
            continue
        subject_area, component = rel.parts[0], rel.parts[1]
        schema = yaml.safe_load(schema_path.read_text())

        lines = [
            f"# {_title(component)} — Data Dictionary\n\n",
            "*Auto-generated from `schema.yml` and doc blocks. "
            "Do not edit manually — re-generated on each `mkdocs build`.*\n\n",
        ]

        for model in schema.get("models", []):
            model_name = model["name"]
            model_desc = " ".join(model.get("description", "").split())
            lines.append(f"## `{model_name}`\n\n{model_desc}\n\n")

            columns = model.get("columns", [])
            if columns:
                lines.append("| Column | Description |\n|---|---|\n")
                for col in columns:
                    col_name = col["name"]
                    col_desc = " ".join(
                        _resolve(col.get("description", ""), doc_blocks).split()
                    )
                    lines.append(f"| `{col_name}` | {col_desc} |\n")
                lines.append("\n")

        out = docs_dir / "subject_areas" / subject_area / component / "dictionary.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(lines))


def on_pre_build(config, **kwargs):
    docs_dir = Path(config["docs_dir"])

    # ── reference docs ────────────────────────────────────────────────────────
    reference_dir = docs_dir / "reference"
    reference_dir.mkdir(exist_ok=True)
    for dest_name, src_path in REFERENCE_FILES.items():
        shutil.copy2(src_path, reference_dir / dest_name)

    # ── data dictionaries ─────────────────────────────────────────────────────
    _generate_dictionaries(docs_dir)
