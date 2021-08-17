import logging
from typing import Callable

import genno.caching
import pandas as pd
import pint
from iam_units import registry

from .common import DATA_PATH, SKIP_CACHE

log = logging.getLogger(__name__)

# Define non-standard units appearing in the AR6 Scenario Explorer snapshots
registry.define("bn = 10**9")


def cached(func: Callable) -> Callable:
    """Decorator to cache selected data.

    Uses genno; see
    https://genno.readthedocs.io/en/latest/cache.html#genno.caching.decorate.
    """
    # TODO check that this works when SKIP_CACHE changes after the method is decorated
    return genno.caching.decorate(
        func, cache_path=DATA_PATH / "cache", cache_skip=SKIP_CACHE
    )


def groupby_multi(dfs, *args, skip_first_empty=True, **kwargs):
    """Similar to pd.DataFrame.groupby, but aligned across multiple dataframes."""
    gbs = list(map(lambda df: df.groupby(*args, **kwargs), dfs))

    # Compute the set of all group names
    names = set()
    for gb in gbs:
        names |= set(gb.groups.keys())

    for name in sorted(names):
        data = []

        for i, gb in enumerate(gbs):
            try:
                data.append(gb.get_group(name))
            except KeyError:
                log.debug(f"Unbalanced group {repr(name)} for df #{i}")
                data.append(pd.DataFrame(columns=dfs[i].columns))

        if skip_first_empty and len(data[0]) == 0:
            log.info(
                f"Skip {repr(name)}; no data in first dataframe (usually IAM data)"
            )
            continue

        yield name, data


def restore_dims(df: pd.DataFrame, expr: str = None) -> pd.DataFrame:
    """Restore dimensions of `df` from its "variable" column.

    `expr` is a regular expression with one or more named groups. It is applied to the
    "variable" dimension/column of `df`. The returned data frame has one additional
    column for each named group in `expr`. The "variable" column is not modified.
    """
    if not expr:
        # No-op
        return df

    return pd.concat([df, df["variable"].str.extract(expr)], axis=1)


def unique_units(df: pd.DataFrame):
    """Return unique units from `df`."""
    units = df["unit"].unique()
    assert len(units) == 1, f"Units {units} in {df}"
    try:
        return registry(units[0])
    except pint.UndefinedUnitError:
        if "CO2" in units[0]:
            log.info(f"Remove 'CO2' from unit expression {repr(units[0])}")
            return registry(units[0].replace("CO2", ""))
        else:
            return units[0]
