"""Command-line interface using 'click'."""
from datetime import datetime
import logging
import logging.config
from pathlib import Path

import click
import pandas as pd
import yaml

from data import (
    DATA_PATH,
    LOCAL_DATA,
    REMOTE_DATA,
    get_client,
    get_data,
    get_references,
)


OUTPUT_PATH = Path('output')
NOW = datetime.now().isoformat(timespec='seconds')


@click.group()
@click.option('--verbose', is_flag=True,
              help='Also print DEBUG log information.')
def cli(verbose):
    """Command-line interface for IPCC AR6 WGIII Ch.10 figures."""
    log_config = yaml.safe_load(open('logging.yaml'))
    log_config['handlers']['file']['filename'] = OUTPUT_PATH / f'{NOW}.log'

    if verbose:
        log_config['handlers']['console']['level'] = 'DEBUG'

    logging.config.dictConfig(log_config)


@cli.command(help=get_references.__doc__)
def refs():
    get_references()


@cli.command()
@click.option('--normalize', is_flag=True, default=False,
              help='Normalize ordinate to 2020.')
@click.option('--load-only', is_flag=True, default=False,
              help='Only load and preprocess data; no output.')
@click.argument('to_plot', metavar='FIGURES', type=int, nargs=-1)
def plot(to_plot, **options):
    """Plot data to output/.

    FIGURES is a sequence of ints, e.g. 1 4 5 to plot figures 1, 4, and 5. If
    omitted, all figures are plotted.

    Option --normalize does not affect the appearance of all figures.
    """
    import figures

    if len(to_plot) == 0:
        # Plot all figures
        to_plot = figures.__all__
    else:
        # Use integer indices to retrieve method names
        to_plot = [figures.__all__[f - 1] for f in to_plot]

    # Plot each figure
    for f in to_plot:
        getattr(figures, f)(options)

    # # Extra plots: Render and save
    # extra_fn = (output_path / f'extra_{now}').with_suffix('.pdf')
    # p9.save_as_pdf_pages(gen_plots(), extra_fn)


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
    """Cache data from the IIASA API in data/cache/SOURCE/.

    An HDF5 file named all.h5 is also created.

    \b
    The download takes:
    - AR6: approximately 60 minutes for 895 scenarios / 3.3 GiB; all.h5 is 9.1
           GiB.
    - SR15: approximately 15 minutes for 416 scenarios / 832 MiB.
    """
    from .cache import cache_data
    if action == 'refresh':
        cache_data(source)
    else:
        print('Please clear the cache manually.')
        raise NotImplementedError


@cli.command()
def variables():
    """Write lists of variables for each data source.

    The lists are written to data/variables-SOURCE-all.txt. These lists are
    *manually* trimmed to variables-SOURCE.txt, which in turn are used to
    filter data imports
    """
    def write_vars(src, vars):
        (DATA_PATH / f'variables-{source}-all.txt').write_text('\n'.join(vars))

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
