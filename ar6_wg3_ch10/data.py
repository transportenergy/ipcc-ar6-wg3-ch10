"""Load and process data."""
import json
import logging
from copy import copy
from functools import lru_cache

from iam_units import registry as UNITS
import pandas as pd
import pint
import yaml

import item.model

from common import DATA_PATH, CAT_GROUP
from iiasa_se_client import AuthClient
from util import cached

log = logging.getLogger(__name__)


# Filenames for local data
LOCAL_DATA = {
    "ADVANCE": "advance_compare_20171018-134445.csv.gz",
    "AR5": "ar5_public_version102_compare_compare_20150629-130000.csv.gz",
    "AR6 metadata": "raw/ar6_full_metadata_indicators_merge_vetted2020_11_19v5_v2.xlsx",
    "AR6 world": "raw/snapshot_world_with_globalmeantemps_iamc_ar6_2020_11_19.csv.gz",
    "AR6 R5": "raw/snapshot_R5_regions_iamc_ar6_2020_11_19.csv.gz",
    "AR6 R10": "raw/snapshot_R10_regions_iamc_ar6_2020_11_19.csv.gz",
    "AR6 country": "raw/snapshot_ISOs_iamc_ar6_2020_10_14.csv.gz",
    "iTEM MIP2": "iTEM-MIP2.csv",
    "iTEM MIP3": "raw/2019_11_19_item_region_data.csv",
}

# IIASA Scenario Explorer names for remote data
REMOTE_DATA = {
    "AR6 raw": "IXSE_AR6",
    "SR15 raw": "IXSE_SR15",
}

CONFIG = json.load(open("config.json"))
client = None

# Mapping between variable names in different data sources
VARIABLES = yaml.safe_load(open(DATA_PATH / "variables-map.yaml"))

for definition in [
    "bn = 10**9",
    # "person = [person]",
    # "pkm = person * kilometer",
    # "tkm = tonne * kilometre",
    # "yr = year",
]:
    UNITS.define(definition)


# Mapping from groups to fuels included.
GROUP_FUEL = {
    "Electricity": ["Electricity"],
    "Gases": ["Gases"],
    "Hydrogen": ["Hydrogen"],
    "Liquids|Oil": ["Liquids|Oil"],
    "Biofuels": ["Liquids|Bioenergy", "Liquids|Biomass"],
    "Other": [
        "Other",
        "Liquids|Coal",
        "Liquids|Fossil synfuel",
        "Liquids|Gas",
        "Liquids|Natural Gas",
        "Solar",
        "Solids|Biomass",
        "Solids|Coal",
    ],
}

# Reversed mapping
FUEL_GROUP = dict()
for group, fuels in GROUP_FUEL.items():
    FUEL_GROUP.update({fuel: group for fuel in fuels})


def aggregate_fuels(df, groupby=[]):
    """Compute a custom aggregation of fuels using `GROUP_FUEL`."""

    # - Assign the "fuel_group" column based on "fuel".
    # - Fill in None/NaN values so they are not ignored by groupby(), below.
    tmp = df.assign(fuel_group=df["fuel"].apply(lambda f: FUEL_GROUP.get(f))).fillna(
        dict(fuel="NONE", fuel_group="NONE")
    )

    id_cols = ["model", "scenario", "region", "fuel_group", "year"] + groupby

    return (
        tmp.groupby(id_cols)
        .sum(numeric_only=True)
        .pipe(pd.merge, tmp, left_index=True, right_on=id_cols, suffixes=("", "_y"))
        .replace(dict(fuel_group={"NONE": None}))
        .drop(columns=["fuel", "value_y"])
        .rename(columns={"fuel_group": "fuel"})
    )


def compute_descriptives(df, on=["variable"], groupby=[]):
    """Compute descriptive statistics on *df*."""
    return (
        df.groupby(on + ["year", "category"] + groupby)
        .describe(percentiles=[0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
        .loc[:, "value"]
        .reset_index()
    )


def unique_units(df):
    units = df["unit"].unique()
    assert len(units) == 1, f"Units {units} in {df}"
    try:
        return UNITS(units[0])
    except pint.UndefinedUnitError:
        if "CO2" in units[0]:
            log.info(f"Remove 'CO2' from unit expression {repr(units[0])}")
            return UNITS(units[0].replace("CO2", ""))
        else:
            return units[0]


def per_capita_if(data, population, condition, groupby=[]):
    """

    Parameters
    ----------
    condition : bool
        If True, return `data` divided by `population`.
        If False, simply return `data`.
    """
    if not condition:
        return data

    id_cols = ["model", "scenario", "region", "year"]

    results = []
    for group, group_df in data.groupby(groupby) if len(groupby) else ((None, data),):
        num = group_df.set_index(id_cols)
        unit_num = unique_units(num)

        denom = population.set_index(id_cols)
        unit_denom = unique_units(denom)

        log.info(
            f"  ({len(num)} obs) [{unit_num}] / " f"  ({len(denom)} obs) [{unit_denom}]"
        )

        result = num["value"] / denom["value"]
        unit_result = unit_num / unit_denom

        log.info(f"  {len(result)} result obs [{unit_result}]")

        results.append(
            pd.merge(num, result.rename("result"), left_index=True, right_index=True)
            .drop(columns=["value"])
            .rename(columns={"result": "value"})
            .assign(unit=unit_result)
            .reset_index()
        )

    return pd.concat(results)


def compute_ratio(df: pd.DataFrame, num: str, denom: str, groupby=[]) -> pd.DataFrame:
    """Compute ratio of data in `df`

    Parameters
    ----------
    df
        Data frame containing both the numerator and denominator.
    num
        Argument to :meth:`pandas.DataFrame.query` the numerator.
    denom
        Argument to :meth:`pandas.DataFrame.query` the denominator.
    """
    log.info(f"Compute ratio of {num!r} / {denom!r} from {len(df)} obs")

    id_cols = ["model", "scenario", "region", "year"]
    results = []

    groups = df.groupby(groupby) if groupby else ((None, df),)
    for group, group_df in groups:
        tmp = {}
        unit = {}
        skip = False

        for n, query in ("num", num), ("denom", denom):
            # Subset the data
            tmp[n] = group_df.set_index(id_cols + groupby).query(query)

            if len(tmp[n]) == 0:
                log.info(f"  Group {repr(group)}: 0 {n} obs; skip")
                skip = True
                break

            # Retrieve units
            unit[n] = unique_units(tmp[n])

        if skip:
            continue

        # Compute the ratio
        log.info(
            f"  Group {repr(group)}: ({len(tmp['num'])} obs) [{unit['num']}] / "
            f"({len(tmp['denom'])} obs) [{unit['denom']}]"
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
        tmp = group_df.set_index(id_cols)
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

    log.info(f"Normalize {len(df)} obs on year {year}")

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


@cached
def _raw_local_data(path, id_vars):
    """Cache loaded CSV files in memory, for performance."""
    return (
        pd.read_csv(path)
        .rename(columns=lambda c: c.lower())
        .astype({c: "category" for c in id_vars})
        .melt(id_vars=id_vars, var_name="year")
        .dropna(subset=["value"])
    )


@cached
def get_data(
    source="AR6",
    vars_from_file=True,
    drop=("meta", "runId", "time"),
    conform_to=None,
    default_item_filters=True,
    recategorize=None,
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
            # Additional columns in iTEM MIP2 and MIP3
            id_vars.extend(["mode", "technology", "fuel"])
        if "MIP3" in source:
            # Additional columns in iTEM MIP3 data only
            id_vars.extend(["service", "vehicle_type", "liquid_fuel_type"])

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
        .pipe(categorize, source, recategorize=recategorize, drop_uncategorized=True)
    )


def categorize(df, source, **options):
    """Modify *df* from *source* to add 'category' columns."""
    if source in ("SR15",):
        # Read a CSV file
        cat_data = pd.read_csv(DATA_PATH / f"categories-{source}.csv")
        result = df.merge(cat_data, how="left", on=["model", "scenario"])

    elif source.startswith("AR6"):
        cat_data = (
            # Read from file
            pd.read_excel(DATA_PATH / LOCAL_DATA["AR6 metadata"], sheet_name="meta")
            # Simplify column names
            .rename(
                columns={
                    # Appears in older file
                    "Temperature-in-2100_bin": "category",
                    # Appears in newer file(s) (1587047839051 and later)
                    "Category_name": "category",
                    "overshoot years|1.5°C": "os15",
                    "overshoot years|2.0°C": "os2",
                    # Appears in file #1605622065355 and later
                    "normal_v5_vetting_normal_v5": "vetted",
                }
            )
        )

        # Merge the metadata columns with the data
        result = df.merge(
            cat_data[["model", "scenario", "category", "vetted"]],
            how="left",
            on=["model", "scenario"],
        )

        if options.get("vetted_only", True):
            # Drop all but vetted scenarios
            N = len(result)
            result = result.query("vetted != 'FAIL'")
            log.info(
                f"Drop {N - len(result)} / {N} obs from scenarios that failed vetting"
            )

        recategorize = options.get("recategorize")
        if recategorize:
            # Mapping from original categories to new
            cg = CAT_GROUP[recategorize]

            log.info(f"Recategorize scenarios using scheme {repr(recategorize)}")

            # Split 'category' column on ":", look up the first part in `cg`
            result = result.assign(
                category=result["category"].str.split(":", expand=True)[0].replace(cg)
            )

    elif source.startswith("iTEM"):
        # From the iTEM database metadata

        # Version of the iTEM database, e.g. 2 for MIP2
        mip_number = int(source[-1])
        result = df.assign(
            category=df.apply(_item_cat_for_scen, axis=1, args=(mip_number,)).replace(
                "policy-extra", "policy"
            )
        )

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
        dict(model=[s["model"] for s in info], scenario=[s["scenario"] for s in info]),
    )


def _item_cat_for_scen(row, mip):
    """Return the iTEM scenario category for model & scenario info."""
    return _item_scen_info(row["model"], mip)[row["scenario"]]["category"]


def _item_clean_data(df, source, scale):
    """Clean iTEM data by removing commercial projections and scaling."""
    if "iTEM" not in source:
        return df

    # Apply scaling
    df["value"] = df["value"] * scale
    df["region"] = df["region"].replace({"Global": "World"})

    # Remove private companies' projections
    return df.loc[~df.model.isin(["BP", "ExxonMobil", "Shell"]), :]


@lru_cache()
def _item_scen_info(name, mip):
    """Return iTEM metadata for model *name*."""
    name = {"WEPS+": "EIA", "ITEDD": "EIA"}.get(name, name)
    return item.model.load_model_scenarios(name.lower(), mip)


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
