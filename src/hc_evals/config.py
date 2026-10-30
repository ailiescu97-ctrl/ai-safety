"""Load configs/*.yaml. Model names and prices live only there."""

from __future__ import annotations

from pathlib import Path

import yaml

from hc_evals.clauses import REPO_ROOT
from hc_evals.schema import BudgetConfig, ModelsConfig, PricesConfig

CONFIG_DIR = REPO_ROOT / "configs"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_models(path: Path | None = None) -> ModelsConfig:
    return ModelsConfig.model_validate(_load(path or CONFIG_DIR / "models.yaml"))


def load_prices(path: Path | None = None) -> PricesConfig:
    return PricesConfig.model_validate(_load(path or CONFIG_DIR / "prices.yaml"))


def load_budget(path: Path | None = None) -> BudgetConfig:
    return BudgetConfig.model_validate(_load(path or CONFIG_DIR / "budget.yaml"))
