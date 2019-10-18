"""Retrieve data from the AR6 WGIII Scenarios Database hosted by IIASA."""
import json

import pandas as pd

from iiasa_se_client import AuthClient


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


def get_data(drop=('meta', 'runId', 'time'), **filters):
    """Retrieve and return data as a pandas.DataFrame.

    Other parameters
    ----------------
    runs : list of int
        ID numbers of particular model runs (~scenarios) to retrieve.
    variables : list of str
        Names of variables to retrieve.
    """
    get_client()

    # Retrieve all data for some runs
    result = pd.DataFrame.from_dict(client.runs_bulk_ts(**filters))

    if len(result):
        result.drop(list(drop), axis=1, inplace=True)

    return result
