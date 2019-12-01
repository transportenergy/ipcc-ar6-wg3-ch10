from datetime import datetime
import logging

import pandas as pd
from tqdm import tqdm

from .data import DATA_PATH, DATE_FORMAT, get_client


log = logging.getLogger(__name__)


def cache_data(source):
    """Retrieve data from *source* and cache it locally."""
    cache_path = DATA_PATH / 'cache' / source
    cache_path.mkdir(parents=True, exist_ok=True)

    # List of 'runs' (=scenarios)
    client = get_client(source)
    runs = client.runs()

    # Display a progress bar while downloading
    runs_iter = tqdm(runs)

    for run in runs_iter:
        # Modification date or creation date; whichever is more recent
        try:
            updated = datetime.strptime(run['upd_date'], DATE_FORMAT)
        except TypeError:
            # upd_date is None
            updated = datetime.strptime(run['cre_date'], DATE_FORMAT)

        # Cache target file
        filename = cache_path / '{run_id:04}.csv'.format(**run)

        # Update the progress bar
        runs_iter.set_postfix_str('{model}/{scenario}'.format(**run))

        try:
            file_mtime = datetime.fromtimestamp(filename.stat().st_mtime)
            if file_mtime > updated:
                continue  # File on disk is newer; skip
        except FileNotFoundError:
            pass  # File doesn't exist

        # Retrieve, convert to CSV, and write
        pd.DataFrame.from_dict(
            client.runs_bulk_ts(runs=[run['run_id']])) \
            .to_csv(filename)

    # Combine files into a single HDF5 file
    h5_path = cache_path / 'all.h5'
    log.info(f'Compiling {h5_path}')
    store = pd.HDFStore(h5_path)

    # Enforce types when reading from CSV
    dtypes = {c: int for c in 'year meta runId version'.split()}
    dtypes['time'] = float  # runID 1202 are empty -> NaN -> cannot use int
    dtypes['scenario'] = str  # runID 0274 contains '1.0' -> float

    # Minimum sizes for HDF5 columns; the longest appearing in the data
    sizes = dict(model=44, region=94, scenario=54, unit=39, variable=88)

    # Iterate over files
    for f in tqdm(sorted(cache_path.glob('*.csv'))):
        df = pd.read_csv(f, index_col=0, dtype=dtypes).reset_index(drop=True)
        try:
            store.append(source, df, min_itemsize=sizes)
        except ValueError as e:
            print(e, f)
            raise

    store.close()


def get_references():
    """Retrieve reference files listed in ref/urls.txt to ref/."""
    from pathlib import Path
    from urllib.parse import urlparse

    import requests

    ref_dir = Path('ref')

    for url in open(ref_dir / 'urls.txt'):
        # Strip trailing newline
        url = url.strip()

        # Name of the file to be written
        name = Path(urlparse(url).path).name
        log.info(name)

        # Retrieve the content from the web and write its contents to a new
        # file in ref/
        with open(ref_dir / name, 'wb') as f:
            f.write(requests.get(url, timeout=3).content)
