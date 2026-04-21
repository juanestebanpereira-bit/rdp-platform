# ADR-002: Consultant-Facing Platform Architecture

**Status:** Proposed
**Date:** 2026-04-18
**Decision Makers:** Product Team

---

## Context

RDP is built on the two-project dbt architecture defined in ADR-001. Today, implementation consultants (SI partners, IT staff) work directly with dbt — editing YAML schema files, writing staging SQL, running `dbt run` commands, reviewing test results.

This works for technical dbt practitioners but creates friction:

- **Overreliance on offshore partners** — Even simple tasks require offshore involvment, adding overhead and lead times.
- **Steep learning curve** — consultants must know dbt conventions, Jinja, the RDP canonical model, and the two-project structure
- **Error-prone** — manual SQL writing leads to naming convention drift, missing tests, incorrect sentinel values
- **Hard to maintain offshore** — dbt code delivered by offshore teams frequently drifts from RDP standards, and SQL is hard to review at scale
- **Inconsistent documentation** — implementation rationale (why a mapping was done this way, what source tables were excluded) is lost once the SQL is committed
- **Slow for consultants** — mapping Olist columns to canonical columns by hand takes hours; with AI assistance it could take minutes

We need an architecture that lets consultants work at a higher level of abstraction — configuring mappings rather than writing SQL — while preserving the dbt-based execution model underneath.

## Decision

We will build a **three-layer consultant-facing platform** on top of the existing dbt projects:

### Layer 1 — Metadata in YAML, stored in git

No database. All metadata lives as YAML files in the customer's `rdp-client` repository:

- **Canonical contract** — dbt-native `schema.yml` files in `rtl_rdp` (unchanged from today)
- **Component enablement** — `components.yml` (unchanged from today)
- **Source-to-canonical mappings** — new YAML files under `rdp-client/mappings/` per component

The mapping YAML format supports:
- Direct column mappings with optional SQL expressions
- Structured forms for common patterns (`case_when`, `coalesce`, `lookup`)
- Joins, `WHERE` clauses, `GROUP BY`, `UNION ALL`
- Raw SQL escape hatch for edge cases

### Layer 2 — API as a Python package

A new repository `rdp-platform` contains a Python package (`rdp_platform`) with modules for:
- `metadata` — read/write YAML, validate against schemas
- `mappings` — CRUD operations on mapping files
- `codegen` — generate dbt staging SQL from mapping YAML
- `runner` — execute dbt commands as subprocess calls
- `ai` — Claude API integration for mapping suggestions

Called directly from the UI (same process). No REST wrapper initially. Can be wrapped with FastAPI later if other clients need the API — no architectural changes required.

### Layer 3 — Streamlit frontend

Runs locally on each consultant's machine. Reads and writes YAML in the customer's git repo, triggers dbt commands, displays results. Pages for:
- Component enablement
- Mapping wizard (side-by-side source schema and canonical contract, with AI-suggested mappings)
- dbt run monitoring
- Test results
- Documentation links

### Generation Flow

```
mapping.yml  →  codegen  →  stg_*.sql  →  dbt run  →  manifest.json  →  colibri/dbterd/MkDocs
```

The mapping YAML is the source of truth. The generated staging SQL is committed to git as a generated artifact. A pre-commit hook regenerates SQL from mappings and fails if the two are out of sync.

### Documentation Layering

`data_model.md` (implementation documentation per component) is generated from the mapping YAML — it describes source tables, filters, joins, and transformation rationale. `erd.md`, `lineage.html`, and the data dictionary continue to be generated from dbt artifacts via dbterd, colibri, and dbt docs. The two sources of truth are complementary:

- **dbt artifacts** describe what was built
- **Mapping YAML** describes why and how it was built

## Consequences

### Positive

- **Faster implementation** — consultants configure mappings in minutes with AI assistance, not hours
- **Standards enforcement automatic** — the code generator produces SQL that always follows RDP conventions; consultants can't drift
- **In-house maintainability preserved** — because metadata is the source of truth and SQL is regenerated, offshore-delivered implementations can be audited, reviewed, and rebuilt from the YAML at any time
- **Self-documenting implementations** — the mapping YAML is readable documentation of what the customer implementation does
- **AI leverage** — the most tedious task (source schema to canonical column mapping) becomes AI-assisted
- **Lower barrier to entry** — consultants no longer need deep dbt expertise to implement a customer
- **Small surface area** — Python package + Streamlit + YAML in git is a minimal stack to maintain

### Negative

- **New repository to maintain** — `rdp-platform` adds to the product team's surface area
- **Metadata format lock-in** — once consultants are using the YAML format, changing it requires migration
- **Two abstractions for the same thing** — some consultants may prefer editing SQL directly; the platform must not block that workflow
- **Initial build effort** — 4-6 weeks to a working v1

### Mitigations

- Version the mapping YAML schema from day one. Breaking changes go through a migration tool.
- The platform generates standard dbt artifacts — consultants who prefer SQL can always edit the generated SQL directly and ignore the UI for that component.
- Keep the Python package modular so individual modules can be swapped or replaced without rewriting the whole platform.

### Maintainability Rationale

This architecture directly addresses the pain point of offshore maintenance:

1. **Metadata is the code** — business logic is readable YAML, not dense SQL buried in offshore deliverables
2. **Generated SQL is disposable** — if offshore SQL gets messy, regenerate from the metadata; there is no legacy SQL problem
3. **AI handles the mechanical translation** — offshore teams become reviewers of AI-generated mappings, not authors of complex SQL
4. **The platform enforces standards** — naming, column ordering, sentinel values, tests are all produced by the code generator; offshore cannot drift from standards
5. **Documentation generated automatically** — offshore cannot ship undocumented implementations; docs flow from metadata and dbt artifacts
6. **Full audit trail in git** — every metadata change, regeneration, and dbt run is tracked

This architecture lets the in-house team delegate implementation work to offshore with confidence, while retaining complete control over quality and standards.

## Alternatives Considered

**Build on dbt Cloud**
Rejected — vendor lock-in, per-user pricing at scale, limited ability to customize the UI to our canonical model concept. Also doesn't support our two-project architecture cleanly.

**Commercial low-code platform (Coalesce, Matillion)**
Rejected for similar reasons — these are generalized tools, not specific to our canonical retail model. We would spend effort fitting our model into their abstractions rather than building on dbt which we already use.

**Full custom build (React + FastAPI + Postgres)**
Rejected as overkill for 10 customers and a small team. Streamlit covers the UI needs in a fraction of the code. A Python package covers the API needs without deploying a server. YAML in git covers the metadata needs without running a database.

**Pure raw SQL, no structured mappings**
Rejected — defeats the purpose of the platform. The whole value is in making common mapping patterns structured and AI-assistable.

**REST API from day one**
Deferred — adds deployment complexity (a server to host, auth, tenancy) before we need it. When a second client consuming the API emerges, we wrap the Python package with FastAPI in a day.

## Out of Scope

Explicitly not addressed by this architecture:

- **Multi-tenancy** — single-tenant deployments, one per customer
- **Authentication** — consultants run the platform locally; git permissions handle access control
- **BI / reporting** — separate concern, handled by Lightdash or Looker
- **Orchestration** — separate concern, handled by Dagster, Airflow, or dbt Cloud job scheduling
- **Real-time anything** — the platform is batch-oriented, following the dbt model

## Related Decisions

- Builds on ADR-001 (Two-dbt-Project Split) — preserves the canonical/customer separation while abstracting its complexity from consultants
- Future: ADR-003 (Mapping YAML Format) will specify the mapping YAML schema in detail once the platform is built