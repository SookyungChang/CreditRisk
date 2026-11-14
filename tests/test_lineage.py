"""Tests for lineage/lineage.py, run against the real dbt model SQL on sample data."""
import re

import duckdb
import pytest

import lineage
from credit_risk.config import config
from sample_data import create_sample_db

MODELS_DIR = config.PROJECT_ROOT / "risk_dbt" / "models"
MODEL_ORDER = ["stg_application", "bureau_agg", "risk_mart", "kri"]  # build order
SOURCES = {"application", "bureau"}

# {{ source('raw', 'x') }} / {{ ref('x') }}
JINJA_REF = re.compile(r"\{\{\s*(?:source\(\s*'raw'\s*,\s*|ref\(\s*)'(\w+)'\s*\)\s*\}\}")


def compile_model(name):
    """Render source() and ref() the way dbt-duckdb compiles them for risk.duckdb."""
    sql = (MODELS_DIR / f"{name}.sql").read_text()
    return JINJA_REF.sub(r'"risk"."main"."\1"', sql)


@pytest.fixture
def built(tmp_path):
    """Sample risk.duckdb with every model built from its real SQL."""
    path = tmp_path / "risk.duckdb"  # file name sets the catalog name, as in dbt
    create_sample_db(path)
    models = {name: compile_model(name) for name in MODEL_ORDER}
    con = duckdb.connect(str(path))
    for name, sql in models.items():
        con.execute(f"CREATE TABLE {name} AS {sql}")
    yield con, models
    con.close()


def check(built, models=None):
    con, built_models = built
    return lineage.check_consistency(con, models or built_models, SOURCES)


def replace_edge(old_source, old_target, new_source, new_target):
    edges = list(lineage.LINEAGE)
    index = next(i for i, edge in enumerate(edges) if edge[:2] == (old_source, old_target))
    edges[index] = (new_source, new_target, edges[index][2])
    return edges


def test_lineage_matches_models(built):
    assert check(built) == []


def test_stale_edge_after_staging_refactor(built, monkeypatch):
    # risk_mart reads stg_application, so a direct edge from the raw table is stale
    monkeypatch.setattr(lineage, "LINEAGE", replace_edge(
        "stg_application.TARGET", "risk_mart.TARGET", "application.TARGET", "risk_mart.TARGET"))
    assert check(built) == [
        "in SQL but not in LINEAGE: stg_application.target -> risk_mart.TARGET",
        "in LINEAGE but not in SQL: application.TARGET -> risk_mart.TARGET",
    ]


def test_wrong_input_column_in_same_table(built, monkeypatch):
    monkeypatch.setattr(lineage, "LINEAGE", replace_edge(
        "stg_application.AMT_CREDIT", "risk_mart.credit_income_ratio",
        "stg_application.AMT_ANNUITY", "risk_mart.credit_income_ratio"))
    assert check(built) == [
        "in SQL but not in LINEAGE: stg_application.amt_credit -> risk_mart.credit_income_ratio",
        "in LINEAGE but not in SQL: stg_application.AMT_ANNUITY -> risk_mart.credit_income_ratio",
    ]


def test_sql_change_without_lineage_update(built):
    _, models = built
    changed = dict(models, risk_mart=models["risk_mart"].replace("a.AMT_CREDIT /", "a.AMT_ANNUITY /"))
    assert check(built, changed) == [
        "in SQL but not in LINEAGE: stg_application.amt_annuity -> risk_mart.credit_income_ratio",
        "in LINEAGE but not in SQL: stg_application.AMT_CREDIT -> risk_mart.credit_income_ratio",
    ]


def test_new_model_must_be_documented(built):
    con, models = built
    sql = 'SELECT SK_ID_CURR FROM "risk"."main"."application"'
    con.execute(f"CREATE TABLE extra_model AS {sql}")
    assert check(built, dict(models, extra_model=sql)) == [
        "extra_model: in table but not documented: ['SK_ID_CURR']",
        "in SQL but not in LINEAGE: application.sk_id_curr -> extra_model.SK_ID_CURR",
    ]


def test_unbuilt_model(built):
    _, models = built
    assert check(built, dict(models, ghost="SELECT 1 AS x")) == ["ghost: table not found in risk.duckdb"]


def test_count_star_needs_row_count_entry(built, monkeypatch):
    monkeypatch.setattr(lineage, "ROW_COUNT_COLUMNS", lineage.ROW_COUNT_COLUMNS - {"bureau_agg.n_loans"})
    assert check(built) == [
        "in LINEAGE but not in SQL: bureau.SK_ID_BUREAU -> bureau_agg.n_loans",
        "bureau_agg.n_loans: input is not a column; add it to ROW_COUNT_COLUMNS if it is a COUNT(*)",
    ]


def test_stale_row_count_entry(built, monkeypatch):
    monkeypatch.setattr(lineage, "ROW_COUNT_COLUMNS", lineage.ROW_COUNT_COLUMNS | {"bureau_agg.avg_amount"})
    assert check(built) == [
        "bureau_agg.avg_amount: in ROW_COUNT_COLUMNS but sqlglot traces its input; remove it",
    ]


def test_unknown_table(built, monkeypatch):
    monkeypatch.setattr(lineage, "LINEAGE", replace_edge(
        "stg_application.TARGET", "risk_mart.TARGET", "stg_aplication.TARGET", "risk_mart.TARGET"))
    problems = check(built)
    assert "stg_aplication: not a dbt model or source" in problems
    assert "stg_aplication: table not found in risk.duckdb" in problems


def test_edge_into_source_table(built, monkeypatch):
    monkeypatch.setattr(lineage, "LINEAGE", lineage.LINEAGE + [
        ("application.TARGET", "application.SK_ID_CURR", "invalid")])
    assert check(built) == [
        "application.TARGET -> application.SK_ID_CURR: target is a dbt source, not a model",
    ]


def test_trace_follows_every_upstream_edge():
    sources = {source for source, _, _ in lineage.trace("risk_mart.credit_income_ratio")}
    assert sources == {
        "stg_application.AMT_CREDIT", "stg_application.AMT_INCOME_TOTAL",
        "application.AMT_CREDIT", "application.AMT_INCOME_TOTAL",
    }


def test_impact_follows_every_downstream_edge():
    targets = {target for _, target, _ in lineage.impact("application.DAYS_EMPLOYED")}
    assert targets == {
        "stg_application.days_employed", "stg_application.is_not_employed",
        "risk_mart.days_employed", "risk_mart.is_not_employed",
    }
