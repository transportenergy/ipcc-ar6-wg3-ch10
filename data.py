"""Retrieve data from the AR6 WGIII Scenarios Database hosted by IIASA."""
from datetime import datetime
from functools import lru_cache
import json
import logging
from pathlib import Path

import item.model
import pandas as pd
from tqdm import tqdm
import yaml

from iiasa_se_client import AuthClient


log = logging.getLogger(__name__)

data_path = Path('.', 'data').resolve()

LOCAL_DATA = {
    'ADVANCE':  'advance_compare_20171018-134445.csv',
    'AR5': 'ar5_public_version102_compare_compare_20150629-130000.csv',
    'iTEM MIP2': 'iTEM-MIP2.csv',
    }

REMOTE_DATA = {
    'AR6': 'IXSE_AR6',
    'SR15': 'IXSE_SR15',
}


config = json.load(open('config.json'))
client = None


VARIABLES = yaml.safe_load(open(data_path / 'variables-map.yaml'))


def compute_descriptives(df):
    """Compute descriptive statistics on *df*.

    Descriptives are returned for each ('variable', 'category', 'year') and
    ('variable', 'supercategory', 'year').
    """
    # Compute descriptive statistics, by category
    cat = df \
        .groupby(['variable', 'category', 'year']) \
        .apply(lambda g: g.describe()['value']) \
        .reset_index()

    # by supercategory. The rename creates a new category named '2C' when
    # concat()'d below
    supercat = df \
        .groupby(['variable', 'supercategory', 'year']) \
        .apply(lambda g: g.describe()['value']) \
        .reset_index() \
        .rename(columns={'supercategory': 'category'})

    # Discard the statistics for scenarios not part of either supercategory
    supercat = supercat[supercat.category != '']

    return pd.concat([cat, supercat])


def filter(df, filters):
    """Helper to filter CSV data."""
    return df[df.isin(filters)[list(filters.keys())].all(axis=1)]


def get_client(source):
    """Return a client for the configured application."""
    global client

    if client:
        return client

    auth_client = AuthClient(**config['credentials'])
    client = auth_client.get_app(REMOTE_DATA[source])
    return client


def get_data(source='AR6', drop=('meta', 'runId', 'time'), use_cache=False,
             vars_from_file=False, **filters):
    """Retrieve and return data as a pandas.DataFrame.

    Parameters
    ----------
    source : 'AR6' or 'SR15' or 'ADVANCE' or 'AR5'
        Data to load. ADVANCE and AR5 are from local files; see README.
    drop : list of str
        Columns to drop when loading from web API.
    use_cache : bool, optional
    vars_from_file : bool, optional

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
        id_vars = ['model', 'scenario', 'region', 'variable', 'unit']

        if 'iTEM' in source:
            id_vars.extend(['mode', 'technology', 'fuel'])

        result = pd.read_csv(Path('data', LOCAL_DATA[source])) \
                   .rename(columns=lambda c: c.lower()) \
                   .melt(id_vars=id_vars, var_name='year') \
                   .astype({'year': int}) \
                   .pipe(filter, filters) \
                   .dropna(subset=['value'])
    elif source in REMOTE_DATA and not use_cache:
        # Get data from the web API
        client = get_client(source)

        # Retrieve all data for some runs
        result = pd.DataFrame.from_dict(client.runs_bulk_ts(**filters))
    elif source in REMOTE_DATA:
        # Load data from cache
        result = pd.concat(
            (pd.read_csv(f, index_col=0).pipe(filter, filters)
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
        if 'iTEM' in source:
            result['supercategory'] = 'item'
            print(result.head())
            result['category'] = result.apply(_item_cat_for_scen, axis=1)

    return result


def get_data_item(filters, scale, mip=2):
    """Retrieve iTEM2 data."""
    # Select relevant data
    all_filters = dict(
        mode=['All'],
        fuel=['All'],
        region=['Global'],
        technology=['All'],
        )
    all_filters.update(filters)

    data = get_data(f'iTEM MIP{mip}', **all_filters)

    # Remove private companies' projections
    data = data[~data.model.isin(['BP', 'ExxonMobil', 'Shell'])]

    # Apply the conversion factor
    print(data['value'].unique())
    data['value'] *= scale

    return data


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


@lru_cache()
def _item_scen_info(name):
    """Return iTEM metadata for model *name*."""
    name = {'WEPS+': 'EIA'}.get(name, name)
    return item.model.load_model_scenarios(name.lower(), 2)


def _item_cat_for_scen(row):
    """Return the iTEM scenario category."""
    return _item_scen_info(row['model'])[row['scenario']]['category']


@lru_cache()
def item_var_info(source, name):
    """Return iTEM variable info corresponding to *name* in *source*."""
    for v_info in VARIABLES:
        if v_info[source] == name:
            result = v_info['iTEM MIP2'].copy()
            return result.get('select', dict()), result.get('scale', 1)
    raise KeyError(name)


DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


def cache_data(source):
    cache_path = data_path / 'cache' / source
    cache_path.mkdir(parents=True, exist_ok=True)

    client = get_client(source)

    # Display a progress bar while downloading
    runs_iter = tqdm(client.runs())

    for run in runs_iter:
        try:
            updated = datetime.strptime(run['upd_date'], DATE_FORMAT)
        except TypeError:
            # upd_date is None
            updated = datetime.strptime(run['cre_date'], DATE_FORMAT)

        filename = cache_path / '{run_id:04}.csv'.format(**run)

        # Update the progress bar
        runs_iter.set_postfix_str('{model}/{scenario}'.format(**run))

        try:
            file_mtime = datetime.fromtimestamp(filename.stat().st_mtime)
            if file_mtime > updated:
                # Skip
                continue
        except FileNotFoundError:
            pass

        # Retrieve, convert to CSV, and write
        pd.DataFrame.from_dict(
            client.runs_bulk_ts(runs=[run['run_id']])) \
            .to_csv(filename)
