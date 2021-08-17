import logging
from typing import Callable

import genno.caching
import pandas as pd

from .data import DATA_PATH

log = logging.getLogger(__name__)


SKIP_CACHE = False


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
