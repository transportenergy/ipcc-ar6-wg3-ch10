import logging
from pathlib import Path

import click
import pandas as pd
import plotnine as p9

from data import get_client, get_data


log = logging.getLogger()


# Individual figures

FIG1_STATIC = [
    # Ranges of data as vertical bars
    p9.geom_linerange(p9.aes(ymin='min', ymax='max'), size=4, color='#999999'),
    p9.geom_linerange(p9.aes(ymin='25%', ymax='75%', color='model'), size=4),

    # Median
    p9.geom_point(p9.aes(y='50%'), color='black', shape='_', size=3.5),

    # Counts
    p9.geom_text(p9.aes(label='count'), y=0, size=5),

    # Axis labels
    p9.labs(x='', y='Transport CO₂ emissions [Mt/y]', color='Model'),
    p9.theme(axis_text_x=p9.element_text(rotation=90)),

    p9.theme(plot_background=p9.element_rect(alpha=0)),
]


def fig_1():
    source = 'ADVANCE'
    data = get_data(source=source, variable=['Transport|CO2|All'],
                    region=['World'])

    years = ['2020', '2030', '2050', '2100']
    data = data[data['year'].isin(years)]

    data = data.groupby(['model', 'year']) \
               .describe()['value'] \
               .reset_index() \
               .astype({'count': int})
    print(data)

    plot = (
        p9.ggplot(p9.aes(x='model'), data)
        + p9.facet_wrap('year', ncol=len(years))
        + p9.ggtitle(f'Figure 1 ({source} database)')
        + FIG1_STATIC
        )
    plot.save(Path('output', '1.pdf'))


# Utility methods

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
    fig_1()


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
