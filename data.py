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

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

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
    ('variable', 'category+1', 'year').
    """
    dfs = []

    # Compute descriptive statistics, by category
    dfs.append(
        df
        .groupby(['variable', 'category', 'year'])
        .apply(lambda g: g.describe()['value'])
        .reset_index())

    # by supercategory. The rename creates a new category named '2C' when
    # concat()'d below
    if 'category+1' in df.columns:
        supercat = df \
            .groupby(['variable', 'category+1', 'year']) \
            .apply(lambda g: g.describe()['value']) \
            .reset_index() \
            .rename(columns={'category+1': 'category'})

        # Discard the statistics for scenarios not part of either supercategory
        supercat = supercat[supercat.category != '']

        dfs.append(supercat)

    return pd.concat(dfs)


def _filter(df, filters):
    """Filter *df*."""
    return df[df.isin(filters)[list(filters.keys())].all(axis=1)]


def get_client(source):
    """Return a client for the configured application."""
    global client

    if client:
        return client

    auth_client = AuthClient(**config['credentials'])
    client = auth_client.get_app(REMOTE_DATA[source])
    return client


def get_data(source='AR6', vars_from_file=True, drop=('meta', 'runId', 'time'),
             **filters):
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
    log.info(f'Get data for {source} with {filters}')

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
                   .pipe(_filter, filters) \
                   .dropna(subset=['value'])
    elif source in REMOTE_DATA:
        # Load data from cache
        log.info('  from cache')
        result = pd.read_hdf(data_path / 'cache' / source / 'all.h5')
        log.info('  done.')
    else:
        raise ValueError(source)

    # - Drop unneeded columns,
    # - Read and apply category metadata, if any
    return result.drop(list(d for d in drop if d in result.columns), axis=1) \
                 .pipe(apply_categories, source)


def apply_categories(df, source, **options):
    """Modify *df* from *source* to add 'category' columns."""
    if source in ('SR15',):
        # Read a CSV file
        cat_data = pd.read_csv(data_path / f'categories-{source}.csv')
        result = df.merge(cat_data, how='left', on=['model', 'scenario'])
    elif source == 'AR6':
        # Read an Excel file
        cat_data = pd.read_excel(data_path / 'ar6_metadata_indicators.xlsx') \
                     .rename({'Temperature-in-2100_bin': 'category'}) \
                     .loc[:, ['model', 'scenario', 'category']]
        result = df.merge(cat_data, how='left', on=['model', 'scenario'])
    elif source in ('iTEM MIP2',):
        # From the iTEM database metadata
        df['category'] = df.apply(_item_cat_for_scen, axis=1)
        # Directly
        df['category+1'] = 'item'
        result = df
    else:
        pass

    return result


def apply_plot_meta(df, source):
    """Add plot metadata columns 'color' and 'label' *df* from *source*."""
    try:
        meta = pd.read_csv(data_path / f'meta-{source}.csv')
    except FileNotFoundError:
        return df
    else:
        return df.merge(meta, how='left', on=['category'])


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
    data['value'] = data['value'] * scale

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
    """Return the iTEM scenario category for model & scenario info."""
    return _item_scen_info(row['model'])[row['scenario']]['category']


@lru_cache()
def item_var_info(source, name):
    """Return iTEM variable info corresponding to *name* in *source*."""
    for v_info in VARIABLES:
        if v_info[source] == name:
            result = v_info['iTEM MIP2'].copy()
            return result.get('select', dict()), float(result.get('scale', 1))
    raise KeyError(name)


def cache_data(source):
    """Retrieve data from *source* and cache it locally."""
    cache_path = data_path / 'cache' / source
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

    # Concatenate and pickle
    h5_path = cache_path / 'all.h5'
    log.info(f'Compiling {h5_path}')
    store = pd.HDFStore(h5_path)
    dtypes = {c: int for c in 'year meta runId version'.split()}
    dtypes['time'] = float  # runID 1202 contains NaN (empty)
    dtypes['scenario'] = str  # runID 0274 contains float '1.0'
    sizes = dict(model=44, region=94, scenario=54, unit=39, variable=88)
    for f in tqdm(sorted(cache_path.glob('*.csv'))):
        # print(f)
        df = pd.read_csv(f, index_col=0, dtype=dtypes).reset_index(drop=True)
        # print(df.dtypes)
        try:
            store.append(source, df, min_itemsize=sizes)
        except ValueError as e:
            print(e, f)
            raise
    store.close()
