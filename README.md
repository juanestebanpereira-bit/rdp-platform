# RDP Platform — Monorepo Root

This repository is the root of the Retail Data Platform (RDP) monorepo.
It contains three separate git repositories co-located in a single directory,
plus shared tooling that spans all of them.

## Repository Structure

```
~/projects/
├── rdp-platform/          # MkDocs documentation site + shared tooling (this repo)
│   ├── docs/
│   ├── build/
│   └── merge_manifests.py
├── rdp-model/             # RDP product — published as a dbt package (own git repo)
└── rdp-client/            # Customer implementation — reference client (own git repo)
```

## Three Git Repositories

Although `rdp-model`, `rdp-client`, and `rdp-platform` all live under `~/projects/`,
they are **three independent git repositories**:

| Repository | Purpose | Audience |
|---|---|---|
| `rdp-platform` (root) | MkDocs site, shared tooling | Documentation consumers |
| `rdp-model` | RDP product code, published as a dbt package | RDP developers |
| `rdp-client` | Reference customer implementation | Customer teams |

This separation exists because `rtl_rdp` has its own release cycle and is
distributed to customers as a dbt package via `dbt deps`. It must be
versioned and committed independently of any customer implementation.
`rtl_rdp_client` is a reference implementation that customers fork —
it must not be coupled to the product repo.

When committing changes, always check which repo you are in:

```bash
git -C ../rdp-model status
git -C ../rdp-client status
git status          # rdp-platform repo
```

## Documentation Site

The MkDocs site integrates output from both dbt projects into a single
documentation portal covering ERDs, lineage diagrams, and the data dictionary.

```bash
# Generate merged manifests (required before ERD/lineage generation)
python3 merge_manifests.py --subject-area products --component product_hierarchy

# Generate ERD
dbterd run -ad build -s "schema:dev_rdp_dwh_views" -a model_contract -t mermaid \
  -o docs/subject_areas/products/product_hierarchy -ofn erd.md

# Serve docs locally
mkdocs serve
```

## Further Reading

- `../rdp-model/CONTRACT.md` — customer staging contract and column documentation guide
- `../rdp-model/CONTRIBUTING.md` — developer guide: folder conventions, tool choices, adding components
- `../rdp-model/STYLE_GUIDE.md` — SQL and dbt coding standards
