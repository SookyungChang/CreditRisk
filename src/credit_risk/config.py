from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
    DB_PATH: Path = PROJECT_ROOT / "risk.duckdb"  # same file as risk_dbt/profiles.yml

config = Config()
