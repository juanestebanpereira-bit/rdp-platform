"""
MkDocs build hooks.

Invoked via ../rdp-client/mkdocs.yml's `hooks:` config (relative path) —
this file stays in rdp-platform, shared across every customer's rdp-client
fork, while the site itself (mkdocs.yml and docs_dir) lives in rdp-client.

on_pre_build:
  1. Copies reference documentation from rdp-model/ into docs/reference/.
  2. Copies RDP-owned component documentation (overview.md, contract.md)
     from rdp-model/docs/{subject-area}/{component}/ into
     docs/subject_areas/{subject_area}/{component}/.
  3. Generates a data dictionary page per component from dwh_views schema.yml
     and doc blocks, writing docs/{subject_area}/{component}/dictionary.md.

All outputs are gitignored in rdp-client — sources of truth live in rdp-model/.
"""

import re
import shutil
import yaml
from pathlib import Path

_here = Path(__file__).parent
BASE = _here if (_here / "rdp-model").exists() else _here.parent
RDP  = BASE / "rdp-model"

REFERENCE_FILES = {
    "contract.md":          RDP / "contract.md",
    "data-model-index.md":  RDP / "data-model.md",
    "style-guide.md":       RDP / "style-guide.md",
    "components.md":        RDP / "docs" / "components.md",
}


def _copy_component_docs(docs_dir: Path) -> None:
    """
    Copy RDP-owned component documentation from
    rdp-model/docs/{subject-area}/{component}/ into
    docs/subject_areas/{subject_area}/{component}/ in the customer site.

    Source folders use lowercase-with-hyphens (rdp-model's file-naming
    convention); destination folders use lowercase-with-underscores,
    matching the existing subject_area/component naming already used
    throughout the dbt project and generated site (e.g. product_hierarchy).

    Only RDP-owned files (overview.md, contract.md) are
    copied today. Customer-specific extensions — e.g. a suffix pattern
    like `overview_customer.md`, read from the matching location in
    rdp-client — are a future extension point for when a customer needs
    to add their own content alongside the canonical RDP documentation.
    """
    component_docs_root = RDP / "docs"
    if not component_docs_root.exists():
        return

    for subject_area_dir in sorted(p for p in component_docs_root.iterdir() if p.is_dir()):
        subject_area = subject_area_dir.name.replace("-", "_")
        for component_dir in sorted(p for p in subject_area_dir.iterdir() if p.is_dir()):
            component = component_dir.name.replace("-", "_")
            dest_dir = docs_dir / "subject_areas" / subject_area / component
            for filename in ("overview.md", "contract.md"):
                src = component_dir / filename
                if src.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest_dir / filename)


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

    # ── component docs ────────────────────────────────────────────────────────
    _copy_component_docs(docs_dir)

    # ── data dictionaries ─────────────────────────────────────────────────────
    _generate_dictionaries(docs_dir)
