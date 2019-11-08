"""Retrieve data from the AR6 WGIII Scenarios Database hosted by IIASA."""
import json
import logging
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from iiasa_se_client import AuthClient


log = logging.getLogger(__name__)

data_path = Path('.', 'data').resolve()

LOCAL_DATA = {
    'ADVANCE':  'advance_compare_20171018-134445.csv',
    'AR5': 'ar5_public_version102_compare_compare_20150629-130000.csv',
    }

REMOTE_DATA = {
    'AR6': 'IXSE_AR6',
    'SR15': 'IXSE_SR15',
}


config = json.load(open('config.json'))
client = None


def get_client(source):
    """Return a client for the configured application."""
    global client

    if client:
        return client

    auth_client = AuthClient(**config['credentials'])
    client = auth_client.get_app(REMOTE_DATA[source])
    return client


def _filter(df, filters):
    """Helper to filter CSV data."""
    return df[df.isin(filters)[list(filters.keys())].all(axis=1)]


def get_data(source='AR6', drop=('meta', 'runId', 'time'), use_cache=False,
             vars_from_file=False, **filters):
    """Retrieve and return data as a pandas.DataFrame.

    Parameters
    ----------
    source : 'AR6' or 'SR15' or 'ADVANCE' or 'AR5'
        Data to load. ADVANCE and AR5 are from local files; see README.
    drop : list of str
        Columns to drop when loading from web API.

    Other parameters
    ----------------
    runs : list of int
        ID numbers of particular model runs (~scenarios) to retrieve.
    variables : list of str
        Names of variables to retrieve.
    """
    if vars_from_file:
        variables = (data_path / f'variables-{source}.txt').read_text() \
            .strip().split('\n')
        filters['variable'] = sorted(filters.get('variable', []) + variables)

    if source in LOCAL_DATA:
        result = pd.read_csv(Path('data', LOCAL_DATA[source])) \
                   .rename(columns=lambda c: c.lower()) \
                   .pipe(_filter, filters) \
                   .melt(id_vars=['model', 'scenario', 'region', 'variable',
                                  'unit'],
                         var_name='year') \
                   .dropna(subset=['value'])
    elif source in REMOTE_DATA and not use_cache:
        # Get data from the web API
        client = get_client(source)

        # Retrieve all data for some runs
        result = pd.DataFrame.from_dict(client.runs_bulk_ts(**filters))
    elif source in REMOTE_DATA:
        # Load data from cache
        result = pd.concat(
            (pd.read_csv(f, index_col=0).pipe(_filter, filters)
             for f in (data_path / 'cache' / source).glob('*.csv')),
            ignore_index=True)
    else:
        raise ValueError(source)

    # Drop unneeded columns
    result.drop(list(d for d in drop if d in result.columns), axis=1,
                inplace=True)

    # Read and apply category metadata, if any
    try:
        metadata = pd.read_csv(data_path / f'categories-{source}.csv')
        result = result.merge(metadata, how='left', on=['model', 'scenario'])
    except FileNotFoundError:
        pass

    return result


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


def cache_data(source):
    cache_path = data_path / 'cache' / source
    cache_path.mkdir(parents=True, exist_ok=True)

    client = get_client(source)

    # Display a progress bar while downloading
    runs_iter = tqdm(client.runs())

    for run in runs_iter:
        filename = cache_path / '{run_id:03}.csv'.format(**run)

        # Update the progress bar
        runs_iter.set_postfix_str('{model}/{scenario}'.format(**run))

        # Retrieve, convert to CSV, and write
        pd.DataFrame.from_dict(
            client.runs_bulk_ts(runs=[run['run_id']])) \
            .to_csv(filename)
