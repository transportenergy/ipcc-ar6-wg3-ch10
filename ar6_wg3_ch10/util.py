import json
import logging
import pathlib
from hashlib import sha1

import pandas as pd

from data import DATA_PATH

log = logging.getLogger(__name__)


SKIP_CACHE = False


class PathEncoder(json.JSONEncoder):
    """JSON Encoder that handles pathlib.Path; used by _arg_hash."""
    def default(self, o):
        if isinstance(o, pathlib.Path):
            return str(o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


def _arg_hash(*args, **kwargs):
    """Return a unique hash for *args, **kwargs; used by cached."""
    if len(args) + len(kwargs) == 0:
        unique = ''
    else:
        unique = json.dumps(args, cls=PathEncoder) + json.dumps(kwargs, cls=PathEncoder)

    # Uncomment for debugging
    # log.debug(f"Cache key hashed from: {unique}")

    return sha1(unique.encode()).hexdigest()


def cached(load_func):
    """Decorator to cache selected data.

    See for instance data._raw_local_data(). On a first call, the data requested is
    returned, but also cached in data/cache/. On subsequent calls, if the cache exists,
    it is used instead of calling the (possibly slow) method; *unless* the *skip_cache*
    configuration option is given, in which case it is loaded again.
    """
    log.debug(f"Wrapping {load_func.__name__} in cached()")

    # Wrap the call to load_func
    def cached_load(*args, **kwargs):
        # Path to the cache file
        name_parts = [load_func.__name__, _arg_hash(*args, **kwargs)]
        cache_path = DATA_PATH / "cache" / ("-".join(name_parts) + ".pkl")

        # Shorter name for logging
        short_name = f"{name_parts[0]}(<{name_parts[1][:8]}…>)"

        if not SKIP_CACHE and cache_path.exists():
            log.info(f"Load {short_name} from cache")
            return pd.read_pickle(cache_path)
        else:
            log.info(f"Load {short_name} from source")
            data = load_func(*args, **kwargs)

            log.info(f"Store {short_name}")
            data.to_pickle(cache_path)

            return data
    return cached_load


def groupby_multi(dfs, *args, **kwargs):
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

        yield name, data
