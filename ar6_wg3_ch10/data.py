"""Load and process data."""
import json
import logging
from copy import copy
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pint
import yaml

import item.model
from iiasa_se_client import AuthClient

log = logging.getLogger("root." + __name__)

DATA_PATH = (Path(__file__).parents[1] / "data").resolve()

DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# Filenames for local data
LOCAL_DATA = {
    "ADVANCE": "advance_compare_20171018-134445.csv",
    "AR5": "ar5_public_version102_compare_compare_20150629-130000.csv",
    "iTEM MIP2": "iTEM-MIP2.csv",
    "iTEM MIP3": "2019_11_19_item_region_data.csv",
}

# IIASA Scenario Explorer names for remote data
REMOTE_DATA = {
    "AR6": "IXSE_AR6",
    "SR15": "IXSE_SR15",
}

CONFIG = json.load(open("config.json"))
client = None

# Mapping between variable names in different data sources
VARIABLES = yaml.safe_load(open(DATA_PATH / "variables-map.yaml"))

UNITS = pint.UnitRegistry()
UNITS.define(
    """bn = 10**9
person = [person]
pkm = person * kilometer
tkm = tonne * kilometre
yr = year"""
)


def compute_descriptives(df, on=["variable"], groupby=[]):
    """Compute descriptive statistics on *df*.

    Descriptives are returned for each ('variable', 'category', 'year') and
    ('variable', 'category+1', 'year').
    """

    def _describe(df, col):
        return (
            df.groupby(on + ["year", col] + groupby)
            .describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
            .loc[:, "value"]
            .reset_index()
        )

    # Compute descriptive statistics, by category
    dfs = [df.pipe(_describe, "category")]

    # by supercategory. The rename creates a new category named '2C' when
    # concat()'d below
    if "category+1" in df.columns:
        supercat = df.pipe(_describe, "category+1").rename(
            columns={"category+1": "category"}
        )

        # Discard the statistics for scenarios not part of either supercategory
        supercat = supercat[supercat.category != ""]

        dfs.append(supercat)

    return pd.concat(dfs)


def compute_ratio(df, num, denom, groupby=[]):
    log.info(f"Compute ratio of {num!r} / {denom!r} from {len(df)} obs")

    id_cols = ["model", "scenario", "version", "region", "year"]
    results = []
    for group, group_df in df.groupby(groupby):
        tmp = {}
        unit = {}
        for n, query in ("num", num), ("denom", denom):
            # Subset the data
            tmp[n] = group_df.set_index(id_cols + groupby).query(query)

            # Retrieve units
            unit[n] = tmp[n]["unit"].unique()
            assert len(unit[n]) == 1, f"Units {unit[n]} in {tmp[n]}"
            unit[n] = UNITS(unit[n][0])

        # Compute the ratio
        log.info(
            f"  ({len(tmp['num'])} obs) [{unit['num']}] / "
            f"  ({len(tmp['denom'])} obs) [{unit['denom']}]"
        )

        result = (tmp["num"]["value"] / tmp["denom"]["value"]).dropna()
        result_unit = unit["num"] / unit["denom"]

        log.info(f"  {len(result)} result obs [{result_unit}]")

        results.append(
            pd.merge(
                tmp["num"], result.rename("result"), left_index=True, right_index=True
            )
            .drop(columns=["quantity", "variable"] + ["value"])
            .rename(columns={"result": "value"})
            .assign(unit=result_unit)
            .reset_index()
        )

    return pd.concat(results)


def compute_shares(df, on, groupby=[]):
    log.info(f"Compute {on} shares from {len(df)} obs")

    id_cols = ["model", "scenario", "region", "year"]
    results = []
    grouped = df.groupby(groupby) if len(groupby) else ((None, df),)
    for group, group_df in grouped:
        tmp = group_df.set_index(id_cols + groupby)
        num = tmp[~tmp[on].isna()].set_index(on, append=True)
        denom = tmp[tmp[on].isna()]

        # Compute the ratio
        log.info(f"  ({len(num)} obs) / ({len(denom)} obs)")

        result = (num["value"] / denom["value"]).dropna()

        log.info(f"  {len(result)} result obs")

        results.append(
            pd.merge(num, result.rename("result"), left_index=True, right_index=True)
            .drop(columns=["value", "variable"])
            .rename(columns={"result": "value"})
            .reset_index()
        )

    return pd.concat(results)


def normalize_if(df, condition, year, drop=True):
    """Normalize if *condition* is True.

    Parameters
    ----------
    df : pd.DataFrame
        Data to normalize.
    condition : bool
        If True, return *df* normalized as of *year*.
        If False, simply discard observations for *year*.
    year : int
        Year to normalize against.
    drop : bool, optional
        If True and *condition* is True, discard the observations from the
        normalization year; otherwise, retain these observations (all equal to
        1.0).
    """
    if not condition:
        log.info(f"Discard data for {year}")
        return df[df["year"] != year]

    log.info(f"Normalize {len(df)} obs")

    # Move all but 'value' columns to index
    id_cols = list(filter(lambda c: c != "value", df.columns))
    tmp = df.set_index(id_cols)

    # bool mask for numerator/denominator
    mask = tmp.index.isin([year], level="year")

    if drop:
        num = tmp[~mask]
    else:
        num = tmp

    # Remove 'year' index from denominator so it divides all values; compute;
    # return with all data as columns
    return (num / tmp[mask].droplevel("year")).reset_index()


def _filter(df, filters):
    """Filter *df*."""
    return df[df.isin(filters)[list(filters.keys())].all(axis=1)]


def get_client(source):
    """Return a client for the configured application."""
    global client

    if client:
        return client

    auth_client = AuthClient(**CONFIG["scenario explorer credentials"])
    client = auth_client.get_app(REMOTE_DATA[source])
    return client


@lru_cache()
def _raw_local_data(path, id_vars):
    """Cache loaded CSV files in memory, for performance."""
    return (
        pd.read_csv(path)
        .rename(columns=lambda c: c.lower())
        .melt(id_vars=id_vars, var_name="year")
    )


def get_data(
    source="AR6",
    vars_from_file=True,
    drop=("meta", "runId", "time"),
    conform_to=None,
    default_item_filters=True,
    categories=None,
    **filters,
):
    """Retrieve and return data as a pandas.DataFrame.

    Parameters
    ----------
    source : str
        Source of data; one of the keys in LOCAL_DATA or REMOTE_DATA. In the
        latter case, the data must have first been cached using ``$ python
        main.py cache SOURCE``; they are read from the corresponding file
        all.h5.
    drop : list of str
        Columns to drop.
    vars_from_file : bool, optional
        Use the list from "data/variables-*source*.txt" if no variables are
        given with *filters*.

    Other parameters
    ----------------
    runs : list of int
        For remote sources, ID numbers of particular model runs (~scenarios) to
        retrieve.
    variables : list of str or str
        Names of variables to retrieve. When *source* includes 'iTEM', a bare
        str for *variables* is used to retrieve *filters* from
        data/variables-map.yaml.
    """
    if vars_from_file and "variable" not in filters:
        variables = (
            (DATA_PATH / f"variables-{source}.txt").read_text().strip().split("\n")
        )
        filters["variable"] = sorted(variables)

    if "iTEM" in source and not isinstance(filters["variable"], str):
        # Recurse: handle each iTEM variable individually
        dfs = []
        for var_name in filters["variable"]:
            _filters = copy(filters)
            _filters["variable"] = var_name
            try:
                dfs.append(get_data(source, conform_to=conform_to, **_filters))
            except KeyError:
                continue
        return pd.concat(dfs) if len(dfs) else pd.DataFrame()
    elif "iTEM" in source:
        # Single iTEM variable

        # Default filters for iTEM data
        if default_item_filters:
            filters.setdefault("mode", ["All"])
            filters.setdefault("fuel", ["All"])
            filters.setdefault("region", ["Global"])
            filters.setdefault("technology", ["All"])

        # Change name 'World' to 'Global'
        if "region" in filters:
            filters["region"] = [
                ("Global" if r == "World" else r) for r in filters["region"]
            ]

        # Combine additional filters for the particular iTEM variable; also
        # retrieve a scaling factor
        _filters, scale = _item_var_info(conform_to, filters["variable"])
        filters.update(_filters)
    else:
        scale = None

    log.info(f"Get {source} data for {len(filters['variable'])} variable(s)")

    if source in LOCAL_DATA:
        # Variables for pandas melt()
        id_vars = ["model", "scenario", "region", "variable", "unit"]
        if "iTEM" in source:
            id_vars.extend(["mode", "technology", "fuel"])

        result = _raw_local_data(DATA_PATH / LOCAL_DATA[source], tuple(id_vars))
    elif source in REMOTE_DATA:
        from cache import load_csv
        # Load data from cache
        result = load_csv(source, filters)
        log.info(f"  done; {len(result)} observations.")
    else:
        raise ValueError(source)

    # Finalize:
    # - Year column as integer,
    # - Apply filters,
    # - Apply iTEM-specific cleaning and scaling
    # - Drop missing values,
    # - Drop undesired columns,
    # - Read and apply category metadata, if any.
    return (
        result.astype({"year": int})
        .pipe(_filter, filters)
        .pipe(_item_clean_data, source, scale)
        .dropna(subset=["value"])
        .drop(list(d for d in drop if d in result.columns), axis=1)
        .pipe(categorize, source, categories=categories, drop_uncategorized=True)
    )


def categorize(df, source, **options):
    """Modify *df* from *source* to add 'category' columns."""
    if source in ("SR15",):
        # Read a CSV file
        cat_data = pd.read_csv(DATA_PATH / f"categories-{source}.csv")
        result = df.merge(cat_data, how="left", on=["model", "scenario"])

    elif source == "AR6":
        # Read an Excel file
        path = DATA_PATH / "raw" / "ar6_metadata_indicators.xlsx"
        cat_data = pd.read_excel(path).rename(
            columns={
                "Temperature-in-2100_bin": "category",
                "overshoot years|1.5°C": "os15",
                "overshoot years|2.0°C": "os2",
            }
        )

        if options["categories"] == "T+os":
            # Use overshoot columns to adjust categories

            # Criterion
            # NB one can add '2.0 - 2.5C' to this list. There are no overshoot
            #    scenarios in the '1.6 - 2.0C' category, by construction
            os = (
                ~cat_data.os15.isna() | ~cat_data.os2.isna()
            ) & cat_data.category.isin(["Below 1.6C"])

            cat_data["category"] = cat_data["category"].mask(
                cond=os, other=cat_data["category"] + " OS"
            )

        result = df.merge(
            cat_data[["model", "scenario", "category"]],
            how="left",
            on=["model", "scenario"],
        )

    elif source in ("iTEM MIP2",):
        # From the iTEM database metadata
        df["category"] = df.apply(_item_cat_for_scen, axis=1).replace(
            "policy-extra", "policy"
        )
        # Directly
        df["category+1"] = "item"
        result = df

    else:
        pass

    if options.get("drop_uncategorized", False):
        result = result.dropna(subset=["category"])

    return result


def restore_dims(df, expr=None):
    """Restore dimensions of *df* from its 'variable' column.

    *expr* is a regular expression with one or more named groups. It is applied
    to the 'variable' column, and *df* is returned with one additional column
    for each named group. The 'variable' column is not modified.
    """
    if not expr:
        # No-op
        return df

    return pd.concat([df, df["variable"].str.extract(expr)], axis=1)


def select_indicator_scenarios(df):
    info = _ar6_scen_info()
    return df.pipe(
        _filter,
        dict(
            model=[s["model"] for s in info], scenario=[s["scenario"] for s in info],
        )
    )


def _item_cat_for_scen(row):
    """Return the iTEM scenario category for model & scenario info."""
    return _item_scen_info(row["model"])[row["scenario"]]["category"]


def _item_clean_data(df, source, scale):
    """Clean iTEM data by removing commercial projections and scaling."""
    if "iTEM" not in source:
        return df

    # Apply scaling
    df["value"] = df["value"] * scale

    # Remove private companies' projections
    return df.loc[~df.model.isin(["BP", "ExxonMobil", "Shell"]), :]


@lru_cache()
def _item_scen_info(name):
    """Return iTEM metadata for model *name*."""
    name = {"WEPS+": "EIA"}.get(name, name)
    return item.model.load_model_scenarios(name.lower(), 2)


@lru_cache()
def _ar6_scen_info():
    """Return the list of AR6 indicators scenarios."""
    return yaml.safe_load(open(DATA_PATH / "indicator-scenarios.yaml"))


@lru_cache()
def _item_var_info(source, name, errors="both"):
    """Return iTEM variable info corresponding to *name* in *source*."""
    result = None
    for variable in VARIABLES:
        if variable.get(source, None) == name:
            info = variable["iTEM MIP2"].copy()
            result = (info.get("select", dict()), float(info.get("scale", 1)))

    if not result:
        if errors in ("warn", "both"):
            log.warning(f"No iTEM variable matching {source}: {name!r}")
            result = (dict(variable=[]), 1)
        if errors in ("raise", "both"):
            raise KeyError(name)

    return result
