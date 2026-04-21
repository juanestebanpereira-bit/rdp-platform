# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This is a monorepo containing two dbt projects targeting BigQuery, plus a shared documentation layer:

- **`../rdp-model/`** — The RDP product (published as a dbt package, consumed by clients)
- **`../rdp-client/`** — Customer implementation layer (maps source data to the RDP contract)
- **`docs/`** — MkDocs site integrating both projects; lives at the monorepo root because it spans both (not inside either project)
- **`build/`** — Intermediate CI artifacts: merged `manifest.json` / `catalog.json` consumed by dbterd and Colibri; gitignored
- **`merge_manifests.py`** — Merges dbt manifests/catalogs from both projects into `build/` to produce cross-project lineage; run before dbterd or Colibri

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
dbt docs generate                     # Generate documentation
dbt clean                             # Remove target/ and dbt_packages/
```

```bash
# Run from monorepo root — merged manifests/catalogs go to build/, lineage HTML goes to docs/
python3 merge_manifests.py                                                     # Full report
python3 merge_manifests.py --subject-area products --component product_hierarchy  # Single component

# Generate ERD — must run merge_manifests.py first; use model_contract algo (reads constraints, not tests)
dbt-env/bin/dbterd run \
  -ad build \
  -s "schema:dev_rdp_dwh_views" \
  -a model_contract \
  -t mermaid \
  -o docs/subject_areas/products/product_hierarchy \
  -ofn erd.md
```

> Note: `../rdp-model/.claude/settings.local.json` only permits `dbt compile` by default.

## Architecture

### Data Flow

```
Customer Source Systems
        ↓
rtl_rdp_client: staging (stg_*) — customer-owned, maps sources to RDP contract
        ↓
rtl_rdp: temp (int_*) — internal joins, enrichment, sentinel row creation
        ↓
rtl_rdp: dwh (dim_*, fct_*) — conformed physical dimension and fact tables
        ↓
rtl_rdp: dwh_views (vw_dim_*, vw_fct_*) — stable public interface (absorbs schema changes)
        ↓
rtl_rdp: mart (mart_*) — subject-area aggregations
        ↓
rtl_rdp: mart_views (vw_mart_*) — BI-facing layer (Lightdash)
```

### Layer → Schema Mapping

Each layer materializes into a BigQuery dataset prefixed with the target environment (`dev`, `tst`, `prd`) via the `generate_schema_name` macro:

| Layer | Schema suffix | Materialization |
|---|---|---|
| staging | `rdp_staging` | view |
| temp | `rdp_temp` | table |
| dwh | `rdp_dwh` | table |
| dwh_views | `rdp_dwh_views` | view |
| mart | `rdp_mart` | table |
| mart_views | `rdp_mart_views` | view |

### Key Macros (`../rdp-model/macros/`)

- **`generate_schema_name.sql`** — Prefixes dataset names with the active dbt target (dev/tst/prd)
- **`audit_columns.sql`** — Appends `rdp_created_at` and `rdp_updated_at` to all models
- **`customer_columns.sql`** — Dynamically passes through any `cust_*` columns from staging without code changes

### Customer Contract

Customers implement staging models in `../rdp-client/models/staging/`. The contract is defined in `../rdp-model/CONTRACT.md`. Key rules:
- All required columns must match exact names and data types defined in the contract
- Custom columns use the `cust_` prefix and are passed through automatically
- `rdp_*` column names are reserved for the platform
- One `rdp_source_system` column identifies the data source

### Denormalization Pattern

Physical DWH tables carry down parent attributes across hierarchy levels. For example, `dim_items` contains `department_number`, `department_name`, `class_number`, `class_name`, etc. so BI tools don't need joins. The `temp` layer performs this attribute carry-down before the DWH layer materializes.

### Component Design

All models are organized by subject area (e.g., `products/product_hierarchy/`). Currently only the **Product Hierarchy** component is implemented. Components can be enabled/disabled via flags in source YAML.

## Style Guide

Full conventions are in `../rdp-model/STYLE_GUIDE.md`. Key rules:

- **Model prefixes by layer:** `stg_`, `int_`, `dim_`, `fct_`, `vw_dim_`, `vw_fct_`, `mart_`, `vw_mart_`
- **Column ordering:** PK → FK → strings → numeric → boolean → dates → timestamps → `cust_*` → `rdp_*`
- **SQL:** keywords uppercase, columns lowercase, CTEs over subqueries, explicit JOIN types
- **Sentinel values for missing data:** `NOT_ASSIGNED`, `UNKNOWN`, `NOT_AVAILABLE`
- **dbt:** always use `source()` and `ref()`, define constraints explicitly in `schema.yml` (not just as tests), use `{{ doc() }}` for column descriptions
