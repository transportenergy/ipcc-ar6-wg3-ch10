"""Load and process data."""
import logging
from copy import copy
from itertools import chain
from typing import Dict, List, Optional

import pandas as pd

from . import item
from .common import (
    CAT_GROUP,
    DATA_PATH,
    FUEL_GROUP,
    LOCAL_DATA,
    SCENARIOS,
    REMOTE_DATA,
)
from .util import cached, unique_units

log = logging.getLogger(__name__)


def aggregate_fuels(df: pd.DataFrame, groupby=[]) -> pd.DataFrame:
    """Compute a custom aggregation of fuels using `GROUP_FUEL`."""

    # - Assign the "fuel_group" column based on "fuel".
    # - Fill in None/NaN values so they are not ignored by groupby(), below.
    tmp = df.assign(fuel_group=df["fuel"].apply(lambda f: FUEL_GROUP.get(f))).fillna(
        dict(fuel="NONE", fuel_group="NONE")
    )

    id_cols = ["model", "scenario", "region", "fuel_group", "year"] + groupby

    # - Sum within fuel groups.
    # - Merge with original data, discarding original 'fuel' and 'variable' indices and
    #   values. This preserves additional, non-numeric indicators like 'category'.
    # - Transform the "NONE" value back to NaN.
    # - Use the fuel group as new 'fuel' keys.
    return (
        tmp.groupby(id_cols)
        .sum(numeric_only=True)
        .pipe(
            pd.merge,
            tmp.drop(["fuel", "value", "variable"], axis=1).drop_duplicates(),
            left_index=True,
            right_on=id_cols,
        )
        .replace(dict(fuel_group={"NONE": None}))
        .rename(columns={"fuel_group": "fuel"})
    )


def compute_descriptives(df, on=["variable"], groupby=[]):
    """Compute descriptive statistics on `df`."""
    return (
        df.groupby(on + ["year", "category"] + groupby)
        .describe(percentiles=[0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
        .loc[:, "value"]
        .reset_index()
    )


def filter_fuel_shares(data: pd.DataFrame, groupby=[], atol=0.01) -> pd.DataFrame:
    """Filter and infill fuel shares.

    Applies two operations to `data`:

    1. Discard groups on (model, scenario, region, year) where the sum of fuel shares is
       different from 1.0 by more than `atol`. This has the effect of excluding groups
       that do not report fuels totaling to reported transport final energy.
    2. Insert 0 values for non-reported fuels. For groups that pass (1), existing data
       sum to 1.0, so the remainder is implicitly 0, even when not reported.

    Parameters
    ----------
    groupby : list of str
        Additional dimensions/columns for grouping `data`.
    atol : float
        Absolute tolerance for the difference between the sum of fuel shares and 1.0.
    """
    # Dimensions for grouping
    id_cols = ["model", "scenario", "region", "year"] + groupby
    # All fuels expected in the output
    fuels = set(data["fuel"].unique())

    def _key(df):
        return ", ".join(map(str, df[id_cols].iloc[0, :]))

    def _filter(df):
        """Filter one group, `df`."""
        check = df["value"].sum()
        if abs(check - 1) > atol:
            log.debug(f"{_key(df)}: drop all data; sum |{check:.3f} - 1| > {atol}")
            return df.iloc[0:0, :]  # Exclude: return an empty data frame

        # Set of missing fuels
        missing = fuels - set(df["fuel"])
        if missing:
            # Infill using existing data in `df`; overwrite 'fuel' and 'value'
            log.debug(f"{_key(df)}: infill 0 for non-reported fuel(s) {missing}")
            return pd.concat(
                [df, df.iloc[: len(missing), :].assign(value=0, fuel=sorted(missing))],
            )
        else:
            return df

    return data.groupby(id_cols).apply(_filter).reset_index(drop=True)


def per_capita_if(
    data: pd.DataFrame, population: Optional[pd.DataFrame], condition: bool, groupby=[]
) -> pd.DataFrame:
    """Compute per-capita values of `data` (using `population`) if `condition`

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

    return pd.concat(results) if len(results) else pd.DataFrame(columns=df.columns)


def compute_shares(df, on, groupby=[]):
    log.info(f"Compute {on} shares from {len(df)} obs")

    id_cols = ["model", "scenario", "region", "year"]
    to_drop = list({"value", "variable"} & set(df.columns))
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
            .drop(columns=to_drop)
            .rename(columns={"result": "value"})
            .reset_index()
        )

    return pd.concat(results)


def normalize_if(
    df: pd.DataFrame, condition: bool, year: int, drop: bool = True
) -> pd.DataFrame:
    """Normalize if `condition` is True.

    Parameters
    ----------
    df
        Data to normalize.
    condition
        If True, return `df` normalized as of `year`.
        If False, simply discard observations for `year`.
    year
        Year to normalize against.
    drop
        If True and `condition` is True, discard the observations from the normalization
        year; otherwise, retain these observations (all equal to 1.0).
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

    # Drop the reference year from the numerator if indicated
    num = tmp[~mask] if drop else tmp

    # Remove 'year' index from denominator so it divides all values; compute;
    # return with all data as columns
    return (num / tmp[mask].droplevel("year")).reset_index()


def apply_filters(df: pd.DataFrame, dims, filters: Dict) -> pd.DataFrame:
    """Filter `df`.

    Return only rows that satisfy all `filters`.

    If `df` is in ‘wide’ format (with the "year" dimension as columns, such as from
    raw_local_data()), additionally melt the data from ‘wide’ to ‘long’ format.
    """
    if "value" not in df.columns:
        # Wide format
        # Columns to retain: dims and any columns matching the "year" filter
        years = list(map(str, filters.get("year", [])))
        columns = list(
            filter(lambda c: c in dims or not years or c in years, df.columns)
        )
        # - Select matching columns.
        # - Melt.
        # - Convert "year" to integer.
        # - Drop NaNs.
        base = (
            df[columns]
            .melt(dims, var_name="year")
            .astype({"year": int})
            .dropna(subset=["value"])
        )
    else:
        base = df

    # - Compute a boolean mask using DataFrame.isin().
    # - Use all() on rows for a 1D mask of where all filter conditions are met.
    # - Use this mask to select from `base`
    return base[base.isin(filters)[list(filters.keys())].all(axis=1)]


@cached
def raw_local_data(path, dims: List[str], mtime: float = 0.0) -> pd.DataFrame:
    """Load raw local data from a CSV file at `path`.

    - Column names matching `dims` except for case are renamed to lower case and
      returned as categoricals.
    - Cached data is used if it exists and unless SKIP_CACHE is True.

    The returned data frame is in ‘wide’ format, i.e. with the "year" dimension as
    columns; the tranformation to ‘long’ format is done in apply_filters(), above.
    This is done because the data frame is large before filtering, so melt() is slow.

    Parameters
    ----------
    path :
        Path to load.
    dims :
        Dimension names.
    mtime :
        Last modification time of `path`.
    """
    # Peek at column names
    dtype = {}  # Columns to read as categorical
    rename = {}  # Map for renaming columns
    for name in filter(lambda c: c.lower() in dims, pd.read_csv(path, nrows=0).columns):
        rename[name] = name.lower()
        dtype[name] = "category"

    # Apply dtypes as data is read, instead of in a separate step
    return pd.read_csv(path, dtype=dtype).rename(columns=rename)


@cached
def get_data(
    source: str = "AR6",
    vars_from_file=True,
    drop=("meta", "runId", "time"),
    conform_to=None,
    default_item_filters=True,
    recategorize=None,
    **filters,
) -> pd.DataFrame:
    """Retrieve and return data for `source`.

    Parameters
    ----------
    source
        Source of data; one of the keys in LOCAL_DATA or REMOTE_DATA. In the latter
        case, the data must have first been cached using ``$ python main.py cache
        SOURCE``; they are read from the corresponding file all.h5.
    drop : list of str
        Columns to drop.
    vars_from_file : bool, optional
        Use the list from "data/variables-*source*.txt" if no variables are given with
        `filters`.
    recategorize :
        Passed to categorize().

    Other parameters
    ----------------
    runs : list of int
        For remote sources, ID numbers of particular model runs (~scenarios) to
        retrieve.
    variables : list of str or str
        Names of variables to retrieve. When *source* includes 'iTEM', a bare
        str for *variables* is used to retrieve *filters* from data/variables-map.yaml.
    """
    if vars_from_file and "variable" not in filters:
        # Only load a subset of variables, as defined in a particular file
        variables = (
            (DATA_PATH / f"variables-{source}.txt").read_text().strip().split("\n")
        )
        filters["variable"] = sorted(variables)

    # Variable name replacements, if any.
    replace_var = None

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
        # Single iTEM variable: construct filters

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
        _filters, scale = item.var_info(conform_to, filters["variable"])

        # Store the mapping for later use
        assert len(_filters["variable"]) == 1
        replace_var = {_filters["variable"][0]: filters["variable"]}

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

        # Path to data
        path = DATA_PATH / LOCAL_DATA[source]
        result = raw_local_data(path, id_vars, path.stat().st_mtime)
    elif source in REMOTE_DATA:
        # Load remote data from a local cache
        from cache import load_csv

        result = load_csv(source, filters)
        log.info(f"  done; {len(result)} observations.")
    else:
        raise ValueError(source)

    # Finalize:
    # - Apply filters,
    # - Apply iTEM-specific cleaning and scaling; rename "variable" entries.
    # - Drop missing values,
    # - Drop undesired columns,
    # - Read and apply category metadata, if any.
    return (
        result.pipe(apply_filters, id_vars, filters)
        .astype({"year": int})
        .pipe(item.clean_data, source, scale, replace_var)
        .dropna(subset=["value"])
        .drop(list(d for d in drop if d in result.columns), axis=1)
        .pipe(categorize, source, recategorize=recategorize, drop_uncategorized=True)
    )


def categorize(df, source, **options):
    """Modify `df` from `source` to add 'category' columns.

    This involved merging the contents of `df` with appropriate metadata.

    `options` include:

    - ``vetted_only``: if :obj:`True`, remove scenarios for which the "vetted"
      attribute contains the string "FAIL"; retain all others. NB this column name has
      varied, so the code below maps the varying name to "vetted". This gives the same
      result as excluding scenarios for which the "exclude" attribute is "True".
    - ``recategorize``: either "A" or "B". Values from :data:`CAT_GROUP` are used to
      recategorize, i.e. by merging together categories from the base data.
    """
    if source in ("SR15",):
        # Read a CSV file
        cat_data = pd.read_csv(DATA_PATH / f"categories-{source}.csv")
        result = df.merge(cat_data, how="left", on=["model", "scenario"])

    elif source.startswith("AR6"):
        # Load category data for IAMs from a file
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
                    #
                    # Appears in snapshot from 2021-06-14
                    "Vetting_historical": "vetted",
                    # Older name(s)
                    # "normal_v5_vetting_normal_v5": "vetted",
                }
            ).set_index(["model", "scenario"])
        )

        if cat_data.index.has_duplicates:
            dupe = cat_data.index.duplicated()
            log.info(f"Drop {dupe.sum()} duplicated (model, scenario) from metadata")
            cat_data = cat_data[~dupe]

        # Add categories for national and sectoral scenario data in the database
        for info in chain(SCENARIOS["national"], SCENARIOS["sectoral"]):
            key = (info["model"], info["scenario"])
            cat_data.loc[key, :] = pd.Series(
                dict(category=info["category"], vetted="N/A")
            )

        # Merge the metadata columns with the data
        result = df.merge(
            cat_data[["category", "vetted"]],
            how="left",
            left_on=["model", "scenario"],
            right_index=True,
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
            category=df.apply(item.cat_for_scen, axis=1, args=(mip_number,)).replace(
                "policy-extra", "policy"
            )
        )

    elif source == "IMO":
        result = df.assign(category="IMO")

    else:
        result = df

    if options.get("drop_uncategorized", False):
        result = result.dropna(subset=["category"])

    return result


def split_scenarios(df: pd.DataFrame, groups=[]):
    """Split `df` into two data frames using `groups`.

    `groups` contains 0 or more names of groups found in scenarios.yaml. Scenarios with
    model and scenario names that match those in the group are returned in one data
    frame; all others in a second.
    """
    # Identifiers of desired scenarios
    names = set(
        [
            "{model}/{scenario}".format(**s)
            for s in chain(*[SCENARIOS[g] for g in groups])
        ]
    )

    # Binary mask of rows in `df` with matching identifiers
    mask = (df["model"] + "/" + df["scenario"]).isin(names)

    log.info(
        f"Split {mask.sum()}, {len(df) - mask.sum()} obs using {repr(groups)} groups"
    )

    return df[mask], df[~mask]
