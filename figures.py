import logging

import click
import pandas as pd

from data import get_client, get_data


log = logging.getLogger()


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


# Command-line interface using 'click'

@click.group()
def cli():
    """Command-line interface for IPCC AR6 WGIII Ch.10 figures."""
    pass


@cli.command(help=get_references.__doc__)
def refs():
    get_references()


@cli.command()
def plot():
    """Generate all plots."""
    pass


@cli.command()
def debug():
    """Demonstrate/debug features."""
    client = get_client()

    # List of all scenarios
    print(pd.DataFrame.from_dict(client.runs()))

    # Data for particular runs
    print(get_data(runs=[746, 791]))


if __name__ == '__main__':
    # If this file is run as a script, start the CLI
    cli()
