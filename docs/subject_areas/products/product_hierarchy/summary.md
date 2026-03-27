# Product Hierarchy — Summary

The Product Hierarchy component defines the classification structure used to organize merchandise. It is the foundation of the Products subject area and a prerequisite for all transactional data — sales, inventory, purchasing, and orders are all recorded at the item level and roll up through this hierarchy.

## Hierarchy Levels

The hierarchy has four levels, from broadest to most granular:

| Level | Entity | Description |
|---|---|---|
| 1 | Department | Broadest grouping. Used to report and analyze performance at the highest level of the classification structure. |
| 2 | Class | Grouping of styles within a department. Used to analyze performance across all styles and items within it. |
| 3 | Style | Grouping of items within a class. Used to analyze performance across all items within it. |
| 4 | Item | The primary unit of merchandise. All transactional data is recorded at this level. |

## Design Notes

**Denormalization** — warehouse tables carry parent attributes down through the hierarchy. For example, `vw_dim_items` includes `department_name`, `class_name`, and `style_name` directly, so reporting tools can filter and group at any level without joins.

**Stable public interface** — downstream consumers (BI tools, reports) connect to the `vw_dim_*` views, not the physical tables. This absorbs any breaking schema changes before they reach consumers.

## Available Tables

| Table | Description |
|---|---|
| `vw_dim_departments` | One row per department |
| `vw_dim_classes` | One row per class, includes department attributes |
| `vw_dim_styles` | One row per style, includes class and department attributes |
| `vw_dim_items` | One row per item, includes style, class, and department attributes |
