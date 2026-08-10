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

## Common commands: dbt model → customer site

There is no CI/CD or automation wiring these together — each step below
is a separate manual command. `dbt run` alone does **not** update the
customer site; none of steps 1–4 do, on their own. Only step 5 actually
rebuilds the site, and it depends on the artifacts every step before it
produces.

```bash
# 1. Run the dbt models for one subject area. rdp-client (staging) must
#    run before rdp-model (canonical) — rdp-model reads rdp-client's
#    staging views via source().
cd ../rdp-client
dbt deps   # only needed after packages.yml changes
dbt run --select path:models/staging/products
# Or, to run every subject area at once: dbt run
# Or, a single model: dbt run --select stg_departments

cd ../rdp-model
dbt run --select path:models/temp/products+
# The trailing + also runs everything downstream of temp/products
# (dwh, dwh_views) in this same command.
# Or, to run every subject area at once: dbt run
# Or, a single model: dbt run --select int_departments

# 2. Generate dbt artifacts (manifest.json / catalog.json) in both projects.
#    `dbt run` does not produce these — lineage, ERD, and the data
#    dictionary all read from them.
dbt docs generate

cd ../rdp-client
dbt docs generate

# 3. Merge manifests/catalogs across both projects, and generate the
#    lineage viewer for this component.
cd ../rdp-platform
python3 merge_manifests.py --subject-area products --component product_hierarchy
# Or, to regenerate every component at once: python3 merge_manifests.py

# 4. Generate the ERD for this component.
dbt-env/bin/dbterd run \
  -ad build \
  -s "schema:dev_rdp_dwh_views" \
  -a model_contract \
  -t mermaid \
  -o ../rdp-client/docs/subject_areas/products/product_hierarchy \
  -ofn erd.md

# 5. Build or preview the customer site. This is the step that actually
#    assembles everything above, plus implementation-guide.md / style-guide.md /
#    data-model.md / components.md / each component's overview.md
#    (copied from rdp-model), and the data dictionary (generated from
#    schema.yml). Pick one:
cd ../rdp-client

# 5a. One-off static build, written to site/.
#     Home page: rdp-client/site/index.html
mkdocs build

# 5b. Live-reloading local preview instead of 5a — watches docs/ and
#     mkdocs.yml, rebuilds on save, serves at http://127.0.0.1:8000,
#     writes nothing to disk. Must stay running (its own terminal or a
#     background job) to stay reachable.
mkdocs serve
```

**Output:** 5a writes `rdp-client/site/index.html` — open directly in
a browser. 5b writes nothing; open `http://127.0.0.1:8000` instead
while it's running.

Steps 3–4 operate on one component at a time; repeat them (with a
different `--subject-area`/`--component`/`-o` path) for each additional
component, or use `python3 merge_manifests.py` with no arguments to
regenerate all of them.

## Further Reading

- `../rdp-model/implementation-guide.md` — customer staging contract and column documentation guide
- `../rdp-model/CONTRIBUTING.md` — developer guide: folder conventions, tool choices, adding components
- `../rdp-model/style-guide.md` — SQL and dbt coding standards
