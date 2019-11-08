"""Command-line interface using 'click'"""
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
import plotnine as p9

from data import (
    LOCAL_DATA,
    REMOTE_DATA,
    cache_data,
    data_path,
    get_client,
    get_data,
    get_references,
)
from extra import gen_plots
import figures


output_path = Path('output')
now = datetime.now().isoformat(timespec='seconds')


@click.group()
def cli():
    """Command-line interface for IPCC AR6 WGIII Ch.10 figures."""
    pass


@cli.command(help=get_references.__doc__)
def refs():
    get_references()


@cli.command()
def plot():
    """Plot data to output/."""
    figures.fig_1()

    # Extra plots: Render and save
    extra_fn = (output_path / f'extra_{now}').with_suffix('.pdf')
    p9.save_as_pdf_pages(gen_plots(), extra_fn)


@cli.command()
def debug():
    """Demo or debug code."""
    client = get_client()

    # List of all scenarios
    print(pd.DataFrame.from_dict(client.runs()))

    # Data for particular runs
    print(get_data(runs=[746, 791]))


@cli.command()
@click.argument('action', type=click.Choice(['refresh', 'clear']))
@click.argument('source', type=click.Choice(REMOTE_DATA.keys()))
def cache(action, source):
    """Cache data from the IIASA API in data/cache/.

    \b
    The download takes:
    - AR6: approximately 60 minutes for 768 scenarios / 3.2 GiB.
    - SR15: approximately 15 minutes for 416 scenarios / 832 MiB.
    """
    if action == 'refresh':
        cache_data(source)
    else:
        raise NotImplementedError


@cli.command()
def variables():
    """Write lists of variables for each data source.

    The lists are written to data/variables-SOURCE-all.txt. These lists are
    *manually* trimmed to variables-SOURCE.txt, which in turn are used to
    filter data imports
    """
    def write_vars(src, vars):
        (data_path / f'variables-{source}-all.txt').write_text('\n'.join(vars))

    for source in LOCAL_DATA.keys():
        print(f'Processing {source!r}')
        df = get_data(source)
        write_vars(source, sorted(df['variable'].unique()))

    for source in REMOTE_DATA.keys():
        print(f'Processing {source!r}')
        try:
            df = get_data(source, use_cache=True)
        except ValueError as e:
            if e.args[0] == 'No objects to concatenate':
                continue
            else:
                raise
        write_vars(source, sorted(df['variable'].unique()))


# Start the CLI
cli()
