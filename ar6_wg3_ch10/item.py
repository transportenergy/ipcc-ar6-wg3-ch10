"""Compatibility for the iTEM databases."""
import logging
from functools import lru_cache
from typing import Dict, Tuple

import item.model
import pandas as pd

from .common import VARIABLES

log = logging.getLogger(__name__)


def cat_for_scen(row: pd.Series, mip: str):
    """Return the iTEM scenario category for model & scenario info."""
    return scen_info(row["model"], mip)[row["scenario"]]["category"]


def clean_data(df: pd.DataFrame, source: str, scale: float) -> pd.DataFrame:
    """Clean iTEM data by removing commercial projections and scaling."""
    if "iTEM" not in source:
        return df

    # Apply scaling
    df["value"] = df["value"] * scale
    df["region"] = df["region"].replace({"Global": "World"})

    # Remove private companies' projections
    return df.loc[~df.model.isin(["BP", "ExxonMobil", "Shell"]), :]


@lru_cache()
def scen_info(name, mip):
    """Return iTEM metadata for model *name*."""
    name = {"WEPS+": "EIA", "ITEDD": "EIA"}.get(name, name)
    return item.model.load_model_scenarios(name.lower(), mip)


@lru_cache()
def var_info(source: str, name: str, errors="both") -> Tuple[Dict, float]:
    """Return iTEM variable info corresponding to *name* in *source*."""
    result = None
    for variable in VARIABLES:
        if variable.get(source, None) == name:
            info = variable["iTEM MIP2"].copy()
            result = (info.get("select", dict()), float(info.get("scale", 1)))

    if not result:
        if errors in ("warn", "both"):
            log.warning(f"No iTEM variable matching {source}: {name!r}")
            result = (dict(variable=[]), 1.0)
        if errors in ("raise", "both"):
            raise KeyError(name)

    return result
