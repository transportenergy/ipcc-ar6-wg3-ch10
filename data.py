"""Retrieve data from the AR6 WGIII Scenarios Database hosted by IIASA."""
import json
from pathlib import Path

import pandas as pd

from iiasa_se_client import AuthClient


LOCAL_DATA = {
    'ADVANCE':  'advance_compare_20171018-134445.csv',
    'AR5': 'ar5_public_version102_compare_compare_20150629-130000.csv',
    }


config = json.load(open('config.json'))
client = None


def get_client():
    """Return a client for the configured application."""
    global client

    if client:
        return client

    auth_client = AuthClient(**config['credentials'])
    client = auth_client.get_app(config['application'])
    return client


def _filter(df, filters):
    """Helper to filter CSV data."""
    return df[df.isin(filters)[list(filters.keys())].all(axis=1)]


def get_data(drop=('meta', 'runId', 'time'), source='AR6', **filters):
    """Retrieve and return data as a pandas.DataFrame.

    Parameters
    ----------
    source : 'AR6' or 'ADVANCE' or 'AR5'
        Data to load. ADVANCE and AR5 are from local files; see README.
    drop : list of str
        Columns to drop when loading from AR6 web API.

    Other parameters
    ----------------
    runs : list of int
        ID numbers of particular model runs (~scenarios) to retrieve.
    variables : list of str
        Names of variables to retrieve.
    """
    if source in LOCAL_DATA:
        result = pd.read_csv(Path('data', LOCAL_DATA[source])) \
                   .rename(columns=lambda c: c.lower()) \
                   .pipe(_filter, filters) \
                   .melt(id_vars=['model', 'scenario', 'region', 'variable',
                                  'unit'],
                         var_name='year') \
                   .dropna(subset=['value'])
        return result
    else:
        assert source == 'AR6'

        # Get data from the AR6 web API

        get_client()

        # Retrieve all data for some runs
        result = pd.DataFrame.from_dict(client.runs_bulk_ts(**filters))

        if len(result):
            result.drop(list(drop), axis=1, inplace=True)

        return result
