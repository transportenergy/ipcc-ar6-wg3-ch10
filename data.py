"""Load and process data."""
from copy import copy
from functools import lru_cache
import json
import logging
from pathlib import Path

import item.model
import pandas as pd
import yaml

from iiasa_se_client import AuthClient


log = logging.getLogger('root.' + __name__)

DATA_PATH = Path('.', 'data').resolve()

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

# Filenames for local data
LOCAL_DATA = {
    'ADVANCE': 'advance_compare_20171018-134445.csv',
    'AR5': 'ar5_public_version102_compare_compare_20150629-130000.csv',
    'iTEM MIP2': 'iTEM-MIP2.csv',
    'iTEM MIP3': '2019_11_19_item_region_data.csv',
    }

# IIASA Scenario Explorer names for remote data
REMOTE_DATA = {
    'AR6': 'IXSE_AR6',
    'SR15': 'IXSE_SR15',
}


config = json.load(open('config.json'))
client = None


# Mapping between variable names in different data sources
VARIABLES = yaml.safe_load(open(DATA_PATH / 'variables-map.yaml'))


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
             conform_to=None, **filters):
    """Retrieve and return data as a pandas.DataFrame.

    Parameters
    ----------
    source : str
        Data to load. ADVANCE and AR5 are from local files; see README.
    drop : list of str
        Columns to drop when loading from web API.
    vars_from_file : bool, optional
        Use the list from "data/variables-*source*.txt" if no variables are
        given with *filters*.

    Other parameters
    ----------------
    runs : list of int
        For remote sources, ID numbers of particular model runs (~scenarios) to
        retrieve.
    variables : list of str
        Names of variables to retrieve.
    """
    if vars_from_file and 'variable' not in filters:
        variables = (DATA_PATH / f'variables-{source}.txt').read_text() \
            .strip().split('\n')
        filters['variable'] = sorted(variables)

    if 'iTEM' in source and not isinstance(filters['variable'], str):
        # Recurse: handle each iTEM variable individually
        dfs = []
        for var_name in filters['variable']:
            _filters = copy(filters)
            _filters['variable'] = var_name
            try:
                dfs.append(get_data(source, conform_to=conform_to, **_filters))
            except KeyError:
                continue
        return pd.concat(dfs)
    elif 'iTEM' in source:
        # Default filters for iTEM data
        filters.setdefault('mode', ['All'])
        filters.setdefault('fuel', ['All'])
        filters.setdefault('region', ['Global'])
        filters.setdefault('technology', ['All'])

        # Change name 'World' to 'Global'
        if 'region' in filters:
            filters['region'] = ['Global' if r == 'World' else r
                                 for r in filters['region']]

        _filters, scale = _item_var_info(conform_to, filters['variable'])
        filters.update(_filters)
    else:
        scale = None

    log.info(f"Get {source} data for {len(filters['variable'])} variable(s)")

    if source in LOCAL_DATA:
        # Variables for pandas melt()
        id_vars = ['model', 'scenario', 'region', 'variable', 'unit']
        if 'iTEM' in source:
            id_vars.extend(['mode', 'technology', 'fuel'])

        result = pd.read_csv(DATA_PATH / LOCAL_DATA[source]) \
                   .rename(columns=lambda c: c.lower()) \
                   .melt(id_vars=id_vars, var_name='year')

    elif source in REMOTE_DATA:
        # Load data from cache
        cache_path = DATA_PATH / 'cache' / source / 'all.h5'
        arg = dict(
            where=' | '.join(f'variable == {v!r}' for v in filters['variable'])
        )
        log.debug(f'  from {cache_path}')
        log.debug(f"  where: {arg['where']}")

        result = pd.read_hdf(cache_path, source, **arg)

        log.info(f'  done; {len(result)} observations.')
    else:
        raise ValueError(source)

    # Finalize:
    # - Year column as integer,
    # - Apply filters,
    # - Apply iTEM-specific cleaning and scaling
    # - Drop missing values,
    # - Drop undesired columns,
    # - Read and apply category metadata, if any.
    return result.astype({'year': int}) \
                 .pipe(_filter, filters) \
                 .pipe(_item_clean_data, source, scale) \
                 .dropna(subset=['value']) \
                 .drop(list(d for d in drop if d in result.columns), axis=1) \
                 .pipe(apply_categories, source, drop_uncategorized=True)


def apply_categories(df, source, **options):
    """Modify *df* from *source* to add 'category' columns."""
    if source in ('SR15',):
        # Read a CSV file
        cat_data = pd.read_csv(DATA_PATH / f'categories-{source}.csv')
        result = df.merge(cat_data, how='left', on=['model', 'scenario'])
    elif source == 'AR6':
        # Read an Excel file
        cat_data = pd.read_excel(DATA_PATH / 'ar6_metadata_indicators.xlsx') \
                     .rename(columns={'Temperature-in-2100_bin': 'category'}) \
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

    if options.get('drop_uncategorized', False):
        result = result.dropna(subset=['category'])

    return result


def apply_plot_meta(df, source):
    """Add plot metadata columns 'color' and 'label' *df* from *source*."""
    try:
        meta = pd.read_csv(DATA_PATH / f'meta-{source}.csv')
    except FileNotFoundError:
        return df
    else:
        return df.merge(meta, how='left', on=['category'])


def restore_dims(df, expr):
    return pd.concat([df, df['variable'].str.extract(expr)], axis=1)


def _item_clean_data(df, source, scale):
    if 'iTEM' not in source:
        return df

    # Apply scaling
    df['value'] = df['value'] * scale

    # Remove private companies' projections
    df = df.loc[~df.model.isin(['BP', 'ExxonMobil', 'Shell']), :]

    return df


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
def _item_var_info(source, name, errors='both'):
    """Return iTEM variable info corresponding to *name* in *source*."""
    result = None
    for variable in VARIABLES:
        if variable.get(source, None) == name:
            info = variable['iTEM MIP2'].copy()
            result = (info.get('select', dict()), float(info.get('scale', 1)))

    if not result:
        if errors in ('warn', 'both'):
            log.warning(f'no iTEM variable info for {source}: {name!r}')
            result = (dict(variable=[]), 1)
        if errors in ('raise', 'both'):
            raise KeyError(name)

    return result
