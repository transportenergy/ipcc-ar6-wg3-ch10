import json
import logging
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from common import DATA_PATH, DATE_FORMAT
from data import _filter, get_client
from util import cached

log = logging.getLogger(__name__)


SUFFIX = ".csv.gz"


def cache_data(source):
    """Retrieve data from *source* and cache it locally."""
    cache_path = DATA_PATH / "cache" / source
    cache_path.mkdir(parents=True, exist_ok=True)

    # List of 'runs' (=scenarios)
    client = get_client(source)
    runs = client.runs(get_only_default_runs=False)

    # Also cache the list of 'runs'
    json.dump(runs, open(cache_path / "runs.json", "w"))

    # Display a progress bar while downloading
    runs_iter = tqdm(runs)

    for run in runs_iter:
        if not run["is_default"]:
            # Superseded version of a run; don't download
            continue

        # Modification date or creation date; whichever is more recent
        try:
            updated = datetime.strptime(run["upd_date"], DATE_FORMAT)
        except TypeError:
            # upd_date is None
            updated = datetime.strptime(run["cre_date"], DATE_FORMAT)

        # Cache target file
        filename = cache_path / f"{run['run_id']:04}{SUFFIX}"

        # Update the progress bar
        runs_iter.set_postfix_str("{model}/{scenario}".format(**run))

        try:
            file_mtime = datetime.fromtimestamp(filename.stat().st_mtime)
            if file_mtime > updated:
                continue  # File on disk is newer; skip
        except FileNotFoundError:
            pass  # File doesn't exist

        # Retrieve, convert to CSV, and write
        pd.DataFrame.from_dict(client.runs_bulk_ts(runs=[run["run_id"]])).to_csv(
            filename
        )


def load_csv(source, *args, **kwargs):
    # Inline the run_info into the arguments so that it is used for the cache key
    run_info = json.load(open(DATA_PATH / "cache" / source / "runs.json"))
    return _load_csv(source, run_info, *args, **kwargs)


@cached
def _load_csv(source, run_info, filters, default_only=True, **kwargs):
    cache_path = DATA_PATH / "cache" / source

    runs = json.load(open(cache_path / "runs.json"))

    # Enforce types when reading from CSV
    dtypes = {c: int for c in "year meta runId version".split()}
    dtypes["time"] = float  # runID 1202 are empty -> NaN -> cannot use int
    dtypes["scenario"] = str  # runID 0274 contains '1.0' -> float

    # Display a progress bar while downloading
    runs_iter = tqdm(runs)

    # Iterate over files
    dfs = []
    N_row = 0
    for run in runs_iter:
        if default_only and not run["is_default"]:
            continue

        filename = cache_path / f"{run['run_id']:04}{SUFFIX}"

        df = (
            pd.read_csv(filename, index_col=0, dtype=dtypes)
            .reset_index(drop=True)
            # Changes in the data format
            .rename(columns={"time": "subannual"})
            .pipe(_filter, filters)
        )

        if len(df) == 0:
            continue

        # Update the progress bar
        N_row += len(df)
        runs_iter.set_postfix_str(f"{N_row} obs")

        dfs.append(df)

    if len(dfs):
        return pd.concat(dfs, copy=False, ignore_index=True)
    else:
        return pd.DataFrame()


def get_references():
    """Retrieve reference files listed in ref/urls.txt to ref/."""
    from pathlib import Path
    from urllib.parse import urlparse

    import requests

    ref_dir = Path("ref")

    for url in open(ref_dir / "urls.txt"):
        # Strip trailing newline
        url = url.strip()

        # Name of the file to be written
        name = Path(urlparse(url).path).name
        log.info(name)

        # Retrieve the content from the web and write its contents to a new
        # file in ref/
        with open(ref_dir / name, "wb") as f:
            f.write(requests.get(url, timeout=3).content)
