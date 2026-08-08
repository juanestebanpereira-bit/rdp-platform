# RDP Platform

This repository holds shared tooling for the Retail Data Platform (RDP) —
manifest merging, ERD/lineage generation — used to build documentation for
each customer implementation. It hosts no documentation site of its own.

## Repository Structure

See [rdp-docs/README.md](../rdp-docs/README.md) for the full repo map. RDP
spans four independent git repositories — `rdp-docs`, `rdp-model`,
`rdp-client`, `rdp-platform` — siblings under `~/projects/`, not nested
inside one another.

When committing changes, always check which repo you are in:

```bash
git -C ../rdp-model status
git -C ../rdp-client status
git status          # this repo (rdp-platform)
```

## Documentation Sites

RDP has two documentation sites, serving different audiences:

- **[rdp-docs](../rdp-docs/)** — one public product site: ecosystem
  overview, architecture decisions, glossary, design principles.
- **Each customer's `rdp-client` fork** — one generated site per customer,
  covering their enabled subject areas (ERDs, lineage diagrams, data
  dictionary). The MkDocs config for this site lives in `rdp-client`, not
  here.

`rdp-platform` hosts neither site. It provides the tooling a customer's
`rdp-client` site build depends on — manifest merging and ERD generation.

### Setup

**Prerequisites:** [Homebrew](https://brew.sh) and Python 3.12
(`brew install python@3.12`).

```bash
./scripts/setup.sh       # bootstraps pipx CLI tools + dbt-env venv; safe to re-run
source dbt-env/bin/activate
```

All dbt, dbterd, and colibri commands (here and in `rdp-model`/`rdp-client`)
run through the shared venv `dbt-env/`, built from `requirements.txt`. To
rebuild it by hand instead of via the script:

```bash
python3.12 -m venv dbt-env
dbt-env/bin/pip install -r requirements.txt
```

```bash
# Generate merged manifests (required before ERD/lineage generation)
python3 merge_manifests.py --subject-area products --component product_hierarchy

# Generate ERD — output goes to rdp-client's docs/ (the site lives there, not here)
dbterd run -ad build -s "schema:dev_rdp_dwh_views" -a model_contract -t mermaid \
  -o ../rdp-client/docs/subject_areas/products/product_hierarchy -ofn erd.md
```

To preview a customer's site locally, run `mkdocs serve` from that
customer's `rdp-client` repo — not from here.

## Further Reading

- `../rdp-model/CONTRACT.md` — customer staging contract and column documentation guide
- `../rdp-model/CONTRIBUTING.md` — developer guide: folder conventions, tool choices, adding components
- `../rdp-model/STYLE_GUIDE.md` — SQL and dbt coding standards
