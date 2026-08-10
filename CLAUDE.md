# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`rdp-platform` holds shared tooling for RDP — manifest merging, ERD/lineage generation — used to build documentation for each customer implementation (`rdp-client`). It hosts no documentation site of its own.

## Repository Structure

- **`../rdp-model/`** — The RDP product (published as a dbt package, consumed by clients)
- **`../rdp-client/`** — Customer implementation layer (maps source data to the RDP contract)
- **`build/`** — Intermediate CI artifacts: merged `manifest.json` / `catalog.json` consumed by dbterd and Colibri; gitignored
- **`merge_manifests.py`** — Merges dbt manifests/catalogs from both projects into `build/` to produce cross-project lineage; run before dbterd or Colibri

See [rdp-docs/README.md](../rdp-docs/README.md) for the full repo map.

## Commands

All dbt commands run from within the relevant project directory (`../rdp-model/` or `../rdp-client/`).

```bash
dbt deps          # Install packages (required before first run in rdp-client)
dbt compile       # Compile SQL without executing
dbt run           # Run all models
dbt run --select rdp_temp.*           # Run a specific layer
dbt run --select +model_name          # Run model and all upstream dependencies
dbt test                              # Run all data quality tests
dbt test --select model_name          # Test a specific model
dbt test --select test_type:unique    # Run tests of a specific type
dbt docs generate                     # Generate manifest.json/catalog.json (NOT the site — see below)
dbt clean                             # Remove target/ and dbt_packages/
```

```bash
# Run from this repo (rdp-platform) — merged manifests/catalogs go to build/, lineage HTML goes to docs/
python3 merge_manifests.py                                                     # Full report
python3 merge_manifests.py --subject-area products --component product_hierarchy  # Single component

# Generate ERD — must run merge_manifests.py first; use model_contract algo (reads constraints, not tests)
# Output goes to rdp-client's docs/ — the site lives there, not here
dbt-env/bin/dbterd run \
  -ad build \
  -s "schema:dev_rdp_dwh_views" \
  -a model_contract \
  -t mermaid \
  -o ../rdp-client/docs/subject_areas/products/product_hierarchy \
  -ofn erd.md
```

None of the above updates the customer site by itself — see
[README.md](README.md), "Common commands: dbt model → customer site",
for the full sequence ending in `mkdocs build` (in `rdp-client`), which
is the step that actually rebuilds it.

> Note: `../rdp-model/.claude/settings.local.json` only permits `dbt compile` by default.

## Architecture

Full architecture detail lives in `rdp-model`, not here:

- **Data flow, layer overview** — [rdp-model/README.md](../rdp-model/README.md)
- **Style guide (naming, column ordering, SQL conventions)** — [rdp-model/style-guide.md](../rdp-model/style-guide.md)
- **Customer staging contract** — [rdp-model/implementation-guide.md](../rdp-model/implementation-guide.md)
- **Canonical data model, denormalization/carry-down pattern** — [rdp-model/data-model.md](../rdp-model/data-model.md)
- **Layer→schema mapping, key macros, component conventions** — [rdp-model/CONTRIBUTING.md](../rdp-model/CONTRIBUTING.md)
- **Architecture decisions (ADRs)** — [rdp-docs/docs/decisions/](../rdp-docs/docs/decisions/)
