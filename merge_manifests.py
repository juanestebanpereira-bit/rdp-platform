#!/usr/bin/env python3
"""
Merge dbt manifests and catalogs from rtl_rdp_client and rtl_rdp into a single
unified pair, then run colibri generate.

Key relationship:
  rtl_rdp_client produces  model.rtl_rdp_client.stg_*  (in rdp_staging schema)
  rtl_rdp consumes them as source.rtl_rdp.rdp_staging.stg_*  via source()

The merge rewires rtl_rdp nodes' depends_on to point directly at the
model.rtl_rdp_client.stg_* nodes so lineage is continuous across the boundary.

Outputs:
  Merged manifests/catalogs → build/                                    (intermediate, gitignored)
  Colibri lineage HTML      → docs/subject_areas/{area}/{component}/lineage/  (per component)
                            → docs/lineage/                             (full platform, unfiltered)

"Combined" refers only to the cross-project merge of rtl_rdp + rtl_rdp_client.
Lineage is always scoped per component — there is no cross-component aggregation.

Usage:
  python3 merge_manifests.py                                                    # full report
  python3 merge_manifests.py --subject-area products --component product_hierarchy
"""

import argparse
import json
import subprocess
import sys
import yaml
from pathlib import Path

_here = Path(__file__).parent
BASE = _here if (_here / "rdp-model").exists() else _here.parent
CLIENT_TARGET = BASE / "rdp-client" / "target"
RDP_TARGET    = BASE / "rdp-model"  / "target"
BUILD_DIR     = _here / "build"
DOCS_DIR      = _here / "docs"
COLIBRI       = _here / "dbt-env" / "bin" / "colibri"


def load(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def build_source_to_model(rdp_manifest: dict, client_manifest: dict) -> dict:
    """
    Map each source.rtl_rdp.rdp_staging.stg_X  →  model.rtl_rdp_client.stg_X
    Only includes entries where the matching client model actually exists.
    """
    mapping = {}
    for source_key, source_node in rdp_manifest["sources"].items():
        table_name = source_node["name"]           # e.g. "stg_items"
        model_key  = f"model.rtl_rdp_client.{table_name}"
        if model_key in client_manifest["nodes"]:
            mapping[source_key] = model_key
    return mapping


def remap(ids: list, mapping: dict) -> list:
    return [mapping.get(i, i) for i in ids]


def populate_compiled_code(nodes: dict, target_dir: Path) -> None:
    """
    Read compiled SQL from target/compiled/ on disk and write it into
    each node's compiled_code field so colibri can display it.
    Pattern: target/compiled/{package_name}/{original_file_path}
    """
    filled = 0
    for node in nodes.values():
        if node.get("compiled_code") or node.get("resource_type") not in (
            "model", "analysis", "seed",
        ):
            continue
        pkg  = node.get("package_name", "")
        ofp  = node.get("original_file_path", "")
        path = target_dir / "compiled" / pkg / ofp
        if path.exists():
            node["compiled_code"] = path.read_text()
            filled += 1
    print(f"  Populated compiled_code for {filled} nodes from {target_dir.name}/compiled/")


def merge_manifests(client: dict, rdp: dict, source_to_model: dict) -> dict:
    # ── merge flat sections ────────────────────────────────────────────────
    simple_sections = [
        "nodes", "macros", "docs", "exposures", "metrics", "groups",
        "selectors", "disabled", "saved_queries", "semantic_models",
        "unit_tests", "functions",
    ]
    merged = {s: {**client.get(s, {}), **rdp.get(s, {})} for s in simple_sections}

    # ── sources: keep client sources + rdp non-staging sources only ───────
    # The rdp staging sources (source.rtl_rdp.rdp_staging.*) are dropped because
    # they are fully replaced by the direct model.rtl_rdp_client.stg_* nodes.
    # Keeping them would render duplicate stg_* nodes in the lineage graph.
    rdp_staging_source_keys = set(source_to_model.keys())
    merged["sources"] = {
        **client.get("sources", {}),
        **{k: v for k, v in rdp.get("sources", {}).items()
           if k not in rdp_staging_source_keys},
    }

    # ── metadata ──────────────────────────────────────────────────────────
    merged["metadata"] = {**client["metadata"], "project_name": "merged"}

    # ── rewire depends_on in every rtl_rdp node ────────────────────────────
    for node_key, node in merged["nodes"].items():
        if ".rtl_rdp." not in node_key:
            continue
        deps = node.get("depends_on", {}).get("nodes", [])
        remapped = remap(deps, source_to_model)
        if remapped != deps:
            node["depends_on"]["nodes"] = remapped

    # ── rebuild parent_map / child_map from depends_on ─────────────────────
    all_ids   = set(merged["nodes"]) | set(merged["sources"])
    parent_map = {}
    child_map  = {k: [] for k in all_ids}

    for node_key, node in {**merged["nodes"], **merged["sources"]}.items():
        parents = node.get("depends_on", {}).get("nodes", [])
        parent_map[node_key] = parents
        for p in parents:
            child_map.setdefault(p, []).append(node_key)

    merged["parent_map"] = parent_map
    merged["child_map"]  = child_map
    merged["group_map"]  = {**client.get("group_map", {}), **rdp.get("group_map", {})}

    return merged


def merge_catalogs(client: dict, rdp: dict, source_to_model: dict) -> dict:
    merged_nodes   = {**client.get("nodes", {}),   **rdp.get("nodes", {})}
    rdp_staging_source_keys = set(source_to_model.keys())
    merged_sources = {
        **client.get("sources", {}),
        **{k: v for k, v in rdp.get("sources", {}).items()
           if k not in rdp_staging_source_keys},
    }

    # For each rdp staging source that maps to a client model node, ensure
    # the catalog also has a *node* entry under the model key so colibri
    # can find column info when traversing model → model lineage.
    for source_key, model_key in source_to_model.items():
        if source_key in merged_sources and model_key not in merged_nodes:
            entry = dict(merged_sources[source_key])
            entry["unique_id"] = model_key
            merged_nodes[model_key] = entry

    return {
        "metadata": client["metadata"],
        "nodes":    merged_nodes,
        "sources":  merged_sources,
        "errors":   (client.get("errors") or []) + (rdp.get("errors") or []),
    }


def filter_by_component(manifest: dict, catalog: dict, component: str) -> tuple[dict, dict]:
    """
    Reduce the merged manifest and catalog to only nodes whose path contains
    `component`, plus all upstream sources those nodes depend on.
    """
    # ── identify nodes belonging to this component ─────────────────────────
    component_node_keys = {
        k for k, v in manifest["nodes"].items()
        if component in v.get("path", "")
        and v.get("resource_type") == "model"
    }

    # ── collect all upstream dependencies (sources + models) ──────────────
    all_nodes_and_sources = {**manifest["nodes"], **manifest["sources"]}
    included = set(component_node_keys)
    frontier = set(component_node_keys)
    while frontier:
        next_frontier = set()
        for key in frontier:
            for parent in all_nodes_and_sources.get(key, {}).get("depends_on", {}).get("nodes", []):
                if parent not in included:
                    included.add(parent)
                    next_frontier.add(parent)
        frontier = next_frontier

    component_sources = {k for k in included if k in manifest["sources"]}
    component_nodes   = {k for k in included if k in manifest["nodes"]}

    # ── filter manifest ────────────────────────────────────────────────────
    filtered_manifest = {
        **manifest,
        "nodes":      {k: v for k, v in manifest["nodes"].items()   if k in component_nodes},
        "sources":    {k: v for k, v in manifest["sources"].items() if k in component_sources},
        "parent_map": {k: v for k, v in manifest["parent_map"].items() if k in included},
        "child_map":  {k: v for k, v in manifest["child_map"].items()  if k in included},
        "metadata":   {**manifest["metadata"], "project_name": f"merged_{component}"},
    }

    # ── filter catalog ─────────────────────────────────────────────────────
    filtered_catalog = {
        **catalog,
        "nodes":   {k: v for k, v in catalog["nodes"].items()   if k in component_nodes},
        "sources": {k: v for k, v in catalog["sources"].items() if k in component_sources},
    }

    return filtered_manifest, filtered_catalog


def postprocess_erd(erd_path: Path, subject_area: str, component: str) -> None:
    """Wrap dbterd's raw erDiagram output in a mermaid code fence, add LR
    layout directive, and sort entities in schema.yml declaration order.

    dbterd outputs plain `erDiagram ...` text. This makes it render correctly
    in MkDocs Material with Mermaid and reads left-to-right in hierarchy order.
    """
    schema_path = BASE / "rdp-model" / "models" / "dwh_views" / subject_area / component / "schema.yml"
    entity_order = []
    if schema_path.exists():
        with open(schema_path) as f:
            data = yaml.safe_load(f)
        entity_order = [m["name"].upper() for m in data.get("models", [])]

    raw = erd_path.read_text()
    if not raw.strip().startswith("erDiagram"):
        return  # already processed or unexpected format

    lines = raw.strip().splitlines()
    header = lines[0]
    entity_blocks, relationship_lines, current_block = [], [], []

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith('"') and stripped.endswith("{"):
            if current_block:
                entity_blocks.append("\n".join(current_block))
            current_block = [line]
        elif stripped == "}" and current_block:
            current_block.append(line)
            entity_blocks.append("\n".join(current_block))
            current_block = []
        elif stripped.startswith('"') and not stripped.endswith("{"):
            relationship_lines.append(line)
        elif current_block:
            current_block.append(line)

    if entity_order:
        def sort_key(block):
            upper = block.upper()
            for i, name in enumerate(entity_order):
                if name in upper:
                    return i
            return len(entity_order)
        entity_blocks.sort(key=sort_key)
        relationship_lines.sort(key=sort_key)

    # Strip "MODEL.PACKAGE." prefix from all entity names (e.g. MODEL.RTL_RDP.VW_DIM_X → VW_DIM_X)
    import re
    def strip_prefix(text: str) -> str:
        return re.sub(r'"[A-Z_]+\.[A-Z_]+\.([A-Z_]+)"', r'"\1"', text)

    entity_blocks      = [strip_prefix(b) for b in entity_blocks]
    relationship_lines = [strip_prefix(l) for l in relationship_lines]

    # Flip any child→parent relationships to parent→child so Mermaid renders
    # in hierarchy order (e.g. }|--|| becomes ||--|{, entities swapped).
    if entity_order:
        def flip_if_reversed(line):
            m = re.match(r'(\s*)"([^"]+)"\s+(\S+)\s+"([^"]+)":\s*(\S+)', line)
            if not m:
                return line
            indent, left_ent, notation, right_ent, label = m.groups()
            left_idx  = next((i for i, n in enumerate(entity_order) if n in left_ent.upper()),  len(entity_order))
            right_idx = next((i for i, n in enumerate(entity_order) if n in right_ent.upper()), len(entity_order))
            if left_idx <= right_idx:
                return line  # already parent→child
            sep = '--' if '--' in notation else '..'
            parts = notation.split(sep, 1)
            if len(parts) != 2:
                return line
            left_tok, right_tok = parts
            new_left  = right_tok[::-1].replace('{', '}')
            new_right = left_tok[::-1].replace('}', '{')
            return f'{indent}"{right_ent}" {new_left}{sep}{new_right} "{left_ent}": {label}'
        relationship_lines = [flip_if_reversed(l) for l in relationship_lines]

    title = f"# {component.replace('_', ' ').title()} — ERD\n\n"
    directive = '%%{init: {"er": {"layoutDirection": "RL"}} }%%'
    body = "\n".join([header, "  direction LR"] + entity_blocks + relationship_lines)
    erd_path.write_text(f"{title}```mermaid\n{directive}\n{body}\n```\n")
    print(f"  Post-processed {erd_path.name}: {len(entity_blocks)} entities, LR layout")


def run_colibri(manifest_path: Path, catalog_path: Path, output_dir: Path) -> Path:
    print(f"\nRunning: colibri generate → {output_dir}")
    result = subprocess.run(
        [
            str(COLIBRI), "generate",
            "--manifest",   str(manifest_path),
            "--catalog",    str(catalog_path),
            "--output-dir", str(output_dir),
        ],
        cwd=str(_here),
    )
    if result.returncode != 0:
        print(f"\ncolibri generate exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    html_files = sorted(output_dir.glob("*.html"))
    return html_files[0] if html_files else output_dir


def main():
    parser = argparse.ArgumentParser(description="Merge dbt manifests and run colibri generate.")
    parser.add_argument(
        "--component",
        help="Filter to a single component, e.g. product_hierarchy. "
             "Requires --subject-area. Omit to generate a report for all components.",
    )
    parser.add_argument(
        "--subject-area",
        help="Subject area containing the component, e.g. products. "
             "Required when --component is provided.",
    )
    args = parser.parse_args()

    if args.component and not args.subject_area:
        parser.error("--subject-area is required when --component is provided")

    BUILD_DIR.mkdir(exist_ok=True)

    print("Loading manifests and catalogs…")
    client_manifest = load(CLIENT_TARGET / "manifest.json")
    rdp_manifest    = load(RDP_TARGET    / "manifest.json")
    client_catalog  = load(CLIENT_TARGET / "catalog.json")
    rdp_catalog     = load(RDP_TARGET    / "catalog.json")

    source_to_model = build_source_to_model(rdp_manifest, client_manifest)
    print(f"Source→Model rewrites ({len(source_to_model)}):")
    for src, mdl in source_to_model.items():
        print(f"  {src}  →  {mdl}")

    print("\nPopulating compiled_code from disk…")
    populate_compiled_code(client_manifest["nodes"], CLIENT_TARGET)
    populate_compiled_code(rdp_manifest["nodes"],    RDP_TARGET)

    print("\nMerging manifests…")
    merged_manifest = merge_manifests(client_manifest, rdp_manifest, source_to_model)

    print("Merging catalogs…")
    merged_catalog = merge_catalogs(client_catalog, rdp_catalog, source_to_model)

    if args.component:
        print(f"\nFiltering to component: {args.component}")
        manifest, catalog = filter_by_component(merged_manifest, merged_catalog, args.component)
        node_count = sum(1 for v in manifest["nodes"].values() if v.get("resource_type") == "model")
        print(f"  {node_count} models matched")
        output_dir    = DOCS_DIR / "subject_areas" / args.subject_area / args.component / "lineage-viewer"
        manifest_path = BUILD_DIR / f"manifest_{args.component}.json"
        catalog_path  = BUILD_DIR / f"catalog_{args.component}.json"
    else:
        manifest, catalog = merged_manifest, merged_catalog
        output_dir    = DOCS_DIR / "lineage"
        manifest_path = BUILD_DIR / "manifest.json"
        catalog_path  = BUILD_DIR / "catalog.json"

    print(f"\nWriting {manifest_path}")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Writing {catalog_path}")
    with open(catalog_path, "w") as f:
        json.dump(catalog, f, indent=2)

    html = run_colibri(manifest_path, catalog_path, output_dir)
    print(f"\nOutput HTML: {html}")

    if args.component:
        erd_path = DOCS_DIR / "subject_areas" / args.subject_area / args.component / "erd.md"
        if erd_path.exists():
            print("\nPost-processing ERD…")
            postprocess_erd(erd_path, args.subject_area, args.component)


if __name__ == "__main__":
    main()
