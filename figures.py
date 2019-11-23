import logging
from pathlib import Path

import matplotlib as mpl
from plotnine import (
    aes,
    element_rect,
    element_text,
    facet_wrap,
    geom_linerange,
    geom_point,
    geom_text,
    ggplot,
    ggtitle,
    labs,
    theme,
)
import yaml

from data import (
    apply_plot_meta,
    compute_descriptives,
    get_data,
)


__all__ = [
    'fig_1',
    'fig_2',
    'fig_3',
    'fig_4',
    'fig_5',
]

log = logging.getLogger('root.' + __name__)

OUTPUT_PATH = Path('output')

YEARS = [2020, 2030, 2050, 2100]

INFO = yaml.safe_load(open('figures.yaml'))


# Matplotlib style
mpl.rc('font', **{'family': 'sans-serif', 'sans-serif': ['Helvetica']})


# Components for individual figures

FIG1_STATIC = [
    # Aesthetic mappings
    aes(x='category', color='category'),

    # Horizontal panels by the years shown
    facet_wrap('year'),

    # Ranges of data as vertical bars
    geom_linerange(aes(ymin='min', ymax='max'), size=4, color='#999999'),
    geom_linerange(aes(ymin='25%', ymax='75%'), size=4),

    # Median
    geom_point(aes(y='50%'), color='black', shape='_', size=3.5),

    # Counts
    geom_text(aes(label='count'), y=0, size=5),

    # Axis labels
    labs(x='', y='Transport CO₂ emissions [Mt/y]', color='Model'),
    theme(axis_text_x=element_text(rotation=90)),

    theme(plot_background=element_rect(alpha=0)),
]


def figure(sources=('AR6', 'iTEM MIP2'), **filters):
    """Decorator to handle common plot tasks.

    A method named NAME wrapped with this decorator:

    - Receives 2 arguments, *iam_data* and *item_data*, with pre-loaded data
      given the corresponding variables in figures.yaml.
    - Receives an argument *sources*, a 2-tuple indicating the original data
      sources.
    - Must return a plotnine.ggplot object, which is then saved to NAME.pdf.

    The decorated method can then be called with a different signature, taking
    only an optional dict of *options*. These include:

    - 'load_only': if True, then the plot is not written to file.

    """
    # Function that decorates the method
    def figure_decorator(func):
        # Information about the figure
        fig_name = func.__name__
        fig_info = INFO[fig_name]
        var_names = fig_info['variables']

        # Wrapped method with new signature
        def wrapped(options={}):
            # Log output
            print('\n')
            log.info(f'Plotting {fig_name}')

            # Load IAM and iTEM data
            iam_data = get_data(
                source=sources[0],
                variable=var_names,
                year=YEARS,
                **filters)
            item_data = get_data(
                source=sources[1],
                conform_to=sources[0],
                variable=var_names,
                year=YEARS,
                **filters)

            # Generate the plot
            plot = func(
                iam_data=iam_data,
                item_data=item_data,
                sources=sources)

            if plot:
                # Add a title
                plot += ggtitle(f'{fig_name} {sources!r}')

            # Save to file by default
            if plot and not options.get('load_only', False):
                plot.save(OUTPUT_PATH / f'{fig_name}.pdf')

        return wrapped
    return figure_decorator


@figure(region=['World'])
def fig_1(iam_data, item_data, sources):
    plot_data = iam_data.pipe(compute_descriptives) \
                        .pipe(apply_plot_meta, sources[0])

    plot = ggplot(aes(x='model'), plot_data) + FIG1_STATIC

    # Info for corresponding iTEM variable
    item_plot_data = item_data \
        .pipe(compute_descriptives) \
        .pipe(apply_plot_meta, sources[1])

    plot += geom_point(
        mapping=aes(y='value', shape='model'), data=item_plot_data,
        color='black', size=2, fill=None)

    return plot


@figure()
def fig_2(iam_data, item_data, sources):
    pass


@figure()
def fig_3(iam_data, item_data, sources):
    pass


@figure()
def fig_4(iam_data, item_data, sources):
    pass


@figure()
def fig_5(iam_data, item_data, sources):
    pass
