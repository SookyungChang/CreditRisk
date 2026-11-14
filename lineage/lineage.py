"""Column-level lineage of the risk_dbt models: a manually validated golden baseline.

dbt docs shows table-level lineage only. LINEAGE documents which column feeds
which model column and how. check_consistency() fails if LINEAGE drifts from
what dbt actually built: the models in dbt's manifest, their columns in
risk.duckdb, and the column edges sqlglot parses from their compiled SQL.

Step 4 of the pipeline (after `dbt build`): uv run python lineage/lineage.py
Add --check-only to skip trace/impact and drawing (no Graphviz needed, as in CI).
"""
import json
import sys
from collections import deque

import duckdb
import graphviz
from sqlglot import exp
from sqlglot.lineage import lineage as sql_lineage

from credit_risk.config import config

MANIFEST_PATH = config.PROJECT_ROOT / "risk_dbt" / "target" / "manifest.json"

# (source, target, transformation): one entry per column-to-column edge.
# Must match risk_dbt/models/*.sql exactly; check_consistency() enforces it.
LINEAGE = [
    # risk_dbt/models/stg_application.sql
    ("application.SK_ID_CURR", "stg_application.SK_ID_CURR", "pass-through"),
    ("application.TARGET", "stg_application.TARGET", "pass-through"),
    ("application.AMT_INCOME_TOTAL", "stg_application.AMT_INCOME_TOTAL", "pass-through"),
    ("application.AMT_CREDIT", "stg_application.AMT_CREDIT", "pass-through"),
    ("application.AMT_ANNUITY", "stg_application.AMT_ANNUITY", "pass-through"),
    ("application.DAYS_EMPLOYED", "stg_application.days_employed",
     "NULL if 365243 (placeholder), else DAYS_EMPLOYED"),
    ("application.DAYS_EMPLOYED", "stg_application.is_not_employed",
     "1 if 365243 (placeholder), else 0"),

    # risk_dbt/models/bureau_agg.sql
    ("bureau.SK_ID_CURR", "bureau_agg.SK_ID_CURR", "GROUP BY key"),
    ("bureau.SK_ID_BUREAU", "bureau_agg.n_loans", "COUNT(*) per SK_ID_CURR"),
    ("bureau.AMT_CREDIT_SUM", "bureau_agg.avg_amount", "AVG(AMT_CREDIT_SUM)"),
    ("bureau.CREDIT_ACTIVE", "bureau_agg.n_active_loans",
     "SUM(CASE WHEN CREDIT_ACTIVE = 'Active' THEN 1 ELSE 0 END)"),

    # risk_dbt/models/risk_mart.sql
    ("stg_application.SK_ID_CURR", "risk_mart.SK_ID_CURR", "pass-through (LEFT JOIN key)"),
    ("stg_application.TARGET", "risk_mart.TARGET", "pass-through"),
    ("bureau_agg.n_loans", "risk_mart.n_loans", "COALESCE(n_loans, 0)"),
    ("bureau_agg.avg_amount", "risk_mart.avg_amount", "pass-through (NULL without bureau history)"),
    ("bureau_agg.n_active_loans", "risk_mart.n_active_loans", "COALESCE(n_active_loans, 0)"),
    ("stg_application.AMT_CREDIT", "risk_mart.credit_income_ratio",
     "AMT_CREDIT / NULLIF(AMT_INCOME_TOTAL, 0)"),
    ("stg_application.AMT_INCOME_TOTAL", "risk_mart.credit_income_ratio",
     "AMT_CREDIT / NULLIF(AMT_INCOME_TOTAL, 0)"),
    ("stg_application.days_employed", "risk_mart.days_employed", "pass-through (cleaned in staging)"),
    ("stg_application.is_not_employed", "risk_mart.is_not_employed", "pass-through (derived in staging)"),
    ("stg_application.AMT_CREDIT", "risk_mart.AMT_CREDIT", "pass-through"),
    
    # risk_dbt/models/kri.sql
    ("risk_mart.SK_ID_CURR", "kri.n_customers", "COUNT(*)"),
    ("risk_mart.TARGET", "kri.observed_default_rate", "AVG(TARGET)"),
    ("risk_mart.TARGET", "kri.avg_pd",
     "AVG(pd), pd = AVG(TARGET) per n_active_loans segment"),
    ("risk_mart.AMT_CREDIT", "kri.total_ead", "SUM(AMT_CREDIT)"),
    ("risk_mart.AMT_CREDIT", "kri.expected_loss", "SUM(pd * lgd * ead), lgd = 0.45 (assumption)"),
    ("risk_mart.TARGET", "kri.expected_loss", "pd = AVG(TARGET) per n_active_loans segment"),
    ("risk_mart.AMT_CREDIT", "kri.top10_concentration",
     "EAD share of the largest 10% of loans (NTILE(10) by AMT_CREDIT)"),
]

# COUNT(*) columns have no input column for sqlglot to find, so their
# documented edge is accepted as long as the SQL still counts rows.
ROW_COUNT_COLUMNS = {"bureau_agg.n_loans", "kri.n_customers"}
# Columns with an input that is a fixed assumption rather than a table column.
# The value documents the assumption, so it stays visible in the lineage.
ASSUMPTION_COLUMNS = {
    "kri.expected_loss": "LGD fixed at 45% (not in the data)",
}

def trace(column):
    """Return every edge upstream of `column`, nearest first."""
    edges, queue, seen = [], deque([column]), {column}
    while queue:
        current = queue.popleft()
        for edge in LINEAGE:
            if edge[1] == current:
                edges.append(edge)
                if edge[0] not in seen:
                    seen.add(edge[0])
                    queue.append(edge[0])
    return edges


def impact(column):
    """Return every edge downstream of `column`, nearest first."""
    edges, queue, seen = [], deque([column]), {column}
    while queue:
        current = queue.popleft()
        for edge in LINEAGE:
            if edge[0] == current:
                edges.append(edge)
                if edge[1] not in seen:
                    seen.add(edge[1])
                    queue.append(edge[1])
    return edges


def documented_columns():
    """Map each table in LINEAGE to the set of its documented columns."""
    columns = {}
    for source, target, _ in LINEAGE:
        for qualified in (source, target):
            table, column = qualified.split(".", 1)
            columns.setdefault(table, set()).add(column)
    return columns


def load_manifest(path=MANIFEST_PATH):
    """Return ({model: compiled SQL}, {source table}) from dbt's manifest.json."""
    manifest = json.loads(path.read_text())
    models = {
        node["name"]: node.get("compiled_code")
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model" and node["package_name"] == "risk_dbt"
    }
    sources = {node["name"] for node in manifest["sources"].values()}
    return models, sources


def load_columns(con):
    """Return {table: [column]} for risk.duckdb, plus the same as a sqlglot schema."""
    columns, schema = {}, {}
    for catalog, table, column, data_type in con.execute(
            "SELECT table_catalog, table_name, column_name, data_type"
            " FROM information_schema.columns WHERE table_schema = 'main'"
            " ORDER BY table_name, ordinal_position").fetchall():
        columns.setdefault(table, []).append(column)
        schema.setdefault(catalog, {}).setdefault("main", {}).setdefault(table, {})[column] = data_type
    return columns, schema


def derive_edges(models, columns, schema):
    """Parse each model's compiled SQL with sqlglot into one-hop (source, target) edges.

    Also returns the targets with an input that is not a table column, such as
    COUNT(*), which sqlglot cannot trace.
    """
    edges, untraced = set(), set()
    for model, sql in models.items():
        for column in columns[model]:
            target = f"{model}.{column}"
            for node in sql_lineage(column, sql, schema=schema, dialect="duckdb").walk():
                if node.downstream:
                    continue
                if isinstance(node.source, exp.Table):
                    edges.add((f"{node.source.name}.{node.name.split('.')[-1]}", target))
                else:
                    untraced.add(target)
    return edges, untraced


def check_edges(models, columns, schema):
    """Compare the documented edges into `models` with the edges in their SQL."""
    def key(edge):  # DuckDB identifiers are case-insensitive; sqlglot lowercases them
        return edge[0].lower(), edge[1].lower()

    derived, untraced = derive_edges(models, columns, schema)
    derived = {key(edge): edge for edge in derived}
    documented = {key((source, target)): (source, target)
                  for source, target, _ in LINEAGE if target.split(".", 1)[0] in models}
    untraced = {target.lower() for target in untraced}
        # COUNT(*) columns and assumption-based columns both have untraceable inputs
    untraceable = ROW_COUNT_COLUMNS | set(ASSUMPTION_COLUMNS)
    row_count = {column.lower() for column in untraceable if column.split(".", 1)[0] in models}

    problems = []
    for edge in sorted(derived.keys() - documented.keys()):
        problems.append("in SQL but not in LINEAGE: {} -> {}".format(*derived[edge]))
    for edge in sorted(documented.keys() - derived.keys()):
        if edge[1] not in (row_count & untraced):
            problems.append("in LINEAGE but not in SQL: {} -> {}".format(*documented[edge]))
    for target in sorted(untraced - row_count):
        problems.append(f"{target}: input is not a column; add it to ROW_COUNT_COLUMNS if it is a COUNT(*)")
    for target in sorted(row_count - untraced):
        problems.append(f"{target}: in ROW_COUNT_COLUMNS but sqlglot traces its input; remove it")
    return problems


def check_consistency(con, models, sources):
    """Compare LINEAGE with dbt's build and return a list of problems (empty = OK).

    - Every table in LINEAGE must be a dbt model or source.
    - Every model in the manifest must be built, and its columns must match the
      documented ones exactly. Source tables only need to contain the
      documented columns, since most raw columns are unused.
    - The documented edges must match the edges sqlglot parses from each
      model's compiled SQL.
    """
    problems = []
    columns, schema = load_columns(con)
    documented = documented_columns()

    for table in sorted(documented.keys() - models.keys() - sources):
        problems.append(f"{table}: not a dbt model or source")
    for source, target, _ in LINEAGE:
        if target.split(".", 1)[0] in sources:
            problems.append(f"{source} -> {target}: target is a dbt source, not a model")
    for table in sorted(models.keys() | documented.keys()):
        if table not in columns:
            problems.append(f"{table}: table not found in {config.DB_PATH.name}")
            continue
        actual, documented_cols = set(columns[table]), documented.get(table, set())
        missing_in_db = documented_cols - actual
        if missing_in_db:
            problems.append(f"{table}: documented but not in table: {sorted(missing_in_db)}")
        if table in models:
            undocumented = actual - documented_cols
            if undocumented:
                problems.append(f"{table}: in table but not documented: {sorted(undocumented)}")

    for model in sorted(model for model, sql in models.items() if not sql):
        problems.append(f"{model}: no compiled SQL in {MANIFEST_PATH.name}; run dbt build")
    built = {model: sql for model, sql in models.items() if sql and model in columns}
    problems += check_edges(built, columns, schema)
    return problems


def draw_lineage(outputs_dir=config.OUTPUTS_DIR):
    """Render LINEAGE with graphviz to lineage.png and lineage.svg."""
    dot = graphviz.Digraph("lineage", graph_attr={"rankdir": "LR"})
    for source, target, transformation in LINEAGE:
        dot.edge(source, target, tooltip=transformation)  # tooltip shows in the SVG
    outputs_dir.mkdir(exist_ok=True)
    for fmt in ("png", "svg"):
        path = outputs_dir / f"lineage.{fmt}"
        path.write_bytes(dot.pipe(format=fmt))
        print(f"Saved {path.relative_to(config.PROJECT_ROOT)}")


def print_edges(title, edges):
    print(title)
    for source, target, transformation in edges:
        print(f"  {source} -> {target}: {transformation}")


def main():
    if not MANIFEST_PATH.exists():
        sys.exit(f"FAIL  {MANIFEST_PATH.relative_to(config.PROJECT_ROOT)} not found; run dbt build first")
    models, sources = load_manifest()
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        problems = check_consistency(con, models, sources)
    finally:
        con.close()
    if problems:
        print("FAIL  LINEAGE does not match the dbt build:")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    print(f"PASS  LINEAGE matches the dbt build ({', '.join(sorted(models))})")
    if "--check-only" in sys.argv:
        return

    print_edges("trace('risk_mart.credit_income_ratio'):", trace("risk_mart.credit_income_ratio"))
    print_edges("impact('application.DAYS_EMPLOYED'):", impact("application.DAYS_EMPLOYED"))
    draw_lineage()


if __name__ == "__main__":
    main()
