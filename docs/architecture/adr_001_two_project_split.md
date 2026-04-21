# ADR-001: Two-Project Architecture for Product and Customer Concerns

**Status:** Accepted
**Date:** 2026-04-01
**Decision Makers:** Product Team

---

## Context

The Retail Data Platform (RDP) is a packaged data platform delivered to retail customers. It defines a canonical data model for retail subject areas (products, digital orders, inventory, sales, etc.) and the transformations that produce warehouse and mart layers from customer source data.

Each customer has unique source systems and unique business requirements:
- Different e-commerce platforms (Shopify, Olist, custom systems)
- Different column names, table structures, and data formats
- Custom business attributes specific to their organization

At the same time, the canonical model must remain **stable and consistent across all customers**. A "department" means the same thing for every customer. `digital_orders` has the same structure regardless of source system.

We needed an architecture that separates:
- **What RDP owns** — the canonical model, transformations, tests, documentation standards
- **What the customer owns** — their source system mappings, custom columns, implementation specifics

## Decision

We adopted a **two-project dbt architecture**:

1. **`rdp-model`** — the product project, owned by the RDP product team
   - Contains canonical model definitions (`temp`, `dwh`, `dwh_views` layers)
   - Ships as a versioned dbt package
   - Defines the staging contract all customers must satisfy
   - Reads only from customer-provided staging views via `{{ source() }}`

2. **`rdp-client`** — the customer project, owned per customer
   - Contains customer-specific staging layer
   - Maps customer source data to the canonical contract
   - May extend with `cust_*` columns and custom `client` models
   - Installs `rtl_rdp` as a package dependency via `dbt deps`

The staging layer is the **only** place customer and product code meet. Once data crosses the staging contract, RDP owns all downstream processing.

## Consequences

### Positive

- **Clean ownership boundaries** — product and customer teams work in separate repositories with clear contracts between them
- **Product independence** — RDP releases don't require coordinated customer deployments
- **Customer autonomy** — customers can customize their implementation without touching product code
- **Standards enforcement** — the canonical model is immutable from the customer side
- **Clear contract surface** — `CONTRACT.md` defines exactly what customers must provide

### Negative

- **Cross-project lineage is not native to dbt** — required building a manifest merge process (`merge_manifests.py`) to produce unified column-level lineage
- **Setup overhead** — customers must install two projects and manage their dependency relationship
- **Documentation split** — product documentation and customer documentation live in different repositories, requiring build-time linking via MkDocs

### Mitigations

- The manifest merge process is automated and repeatable — addressed in the documentation pipeline
- Customer setup is documented in detail in `README.md` with prerequisites and step-by-step installation
- Documentation sources are linked rather than duplicated — product `CONTRACT.md`, `DATA_MODEL.md`, and glossary files are pulled into the customer MkDocs site at build time

## Alternatives Considered

**Single repository, branch per customer**
Rejected — branches drift, merging becomes painful, customers can't have independent release cycles, product updates don't cleanly propagate.

**Single repository, schema per customer**
Rejected — doesn't separate ownership. Customer changes would require PRs against the product repository. Blocks both teams.

**Monolithic project with customer-configurable macros**
Rejected — pushes customer complexity into Jinja macros, which are hard to debug and harder to document. Poor separation of concerns.

## Related Decisions

- ADR-002 (Platform Evolution) builds on this architecture by adding a metadata and UI layer that abstracts the two-project complexity away from end users (implementation consultants)