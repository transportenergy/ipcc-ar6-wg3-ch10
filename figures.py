import logging
from pathlib import Path

import matplotlib as mpl
import pandas as pd
from plotnine import (
    aes,
    element_blank,
    element_rect,
    element_text,
    facet_wrap,
    geom_crossbar,
    # geom_linerange,
    geom_point,
    geom_text,
    ggplot,
    ggtitle,
    guides,
    labs,
    scale_color_manual,
    scale_fill_manual,
    scale_x_discrete,
    theme,
)
import yaml

from data import (
    apply_plot_meta,
    compute_descriptives,
    compute_ratio,
    compute_shares,
    get_data,
    restore_dims,
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


# Common components

# Scale for scenario categories
SCALE_CAT = pd.DataFrame([
    ['Below 1.6C', 'green',   '<1.6°C'],
    ['1.6 - 2.0C', '#fca503', '1.6–2°C'],
    ['2.0 - 2.5C', '#ca34de', '2–2.5°C'],
    ['2.5 - 3.5C', 'red',     '2.5–3.5°C'],
    ['Above 3.5C', 'brown',   '>3.5°C'],
    ['policy',     '#eeeeee', 'Policy'],
    ['reference',  '#999999', 'Reference'],
    ], columns=['limit', 'fill', 'label'])


def figure(sources=('AR6', 'iTEM MIP2'), **filters):
    """Decorator to handle common plot tasks.

    Example:

      @figure()
      def fig_N(iam_data, item_data, sources)
          # Generate plot...
          plot.units = 'kg'
          return plot

      fig_N(options)

    A method (here 'fig_N') wrapped with this decorator:

    - Receives 2 arguments, *iam_data* and *item_data*, with pre-loaded data
      for the variables under 'fig_N' in figures.yaml. See inline comments in
      that file.
    - Receives an argument *sources*, a 2-tuple indicating the original data
      sources for IAM and sectoral models.
    - Must return a plotnine.ggplot object with a 'units' attribute.

    The decorated method is then called with a *different* signature, taking
    only one argument: an optional dict of *options*. These include:

    - 'load_only': if True, then the plot is not written to file. Otherwise,
      the returned plot object is saved to 'fig_N.pdf'.

    """
    # Function that decorates the method
    def figure_decorator(func):
        # Information about the figure
        fig_id = func.__name__
        fig_info = INFO[fig_id]
        var_names = fig_info['variables']

        # Wrapped method with new signature
        def wrapped(options={}):
            # Log output
            print('-------')
            log.info(f'{fig_id}')

            # Load IAM and iTEM data
            iam_data = get_data(
                source=sources[0],
                variable=var_names, year=YEARS, **filters) \
                .pipe(restore_dims, fig_info.get('restore dims', None))
            item_data = get_data(
                source=sources[1], conform_to=sources[0],
                variable=var_names, year=YEARS, **filters)

            # Generate the plot
            plot = func(
                iam_data=iam_data,
                item_data=item_data,
                sources=sources)

            if plot:
                # Add a title
                plot += ggtitle(f"{fig_info['short title']} [{plot.units}] "
                                f"({fig_id}/{'/'.join(sources)})")

            # Save to file by default
            if plot and not options.get('load_only', False):
                args = dict(verbose=False, width=190, height=100, units='mm')
                plot.save(OUTPUT_PATH / f'{fig_id}.pdf', **args)
                plot.save(OUTPUT_PATH / f'{fig_id}.png', **args, dpi=300)

        return wrapped
    return figure_decorator


FIG1_STATIC = [
    # Aesthetic mappings
    aes(x='category', color='category'),

    # Horizontal panels by the years shown
    facet_wrap('year', ncol=4, scales='free_x'),

    # Ranges of data as vertical bars
    geom_crossbar(aes(ymin='min', y='50%', ymax='max'),
                  color='black', fill='white', width=None),
    geom_crossbar(aes(ymin='25%', y='50%', ymax='75%', fill='category'),
                  color='black', width=None),

    # Labels with group counts
    geom_text(
        aes(label='count', y='max', color='category'),
        format_string='{:.0f}',
        va='bottom',
        size=7),

    # Scales
    scale_x_discrete(limits=SCALE_CAT['limit'], labels=SCALE_CAT['label']),
    scale_fill_manual(limits=SCALE_CAT['limit'], values=SCALE_CAT['fill']),
    scale_color_manual(limits=SCALE_CAT['limit'], values=SCALE_CAT['fill']),

    # Axis labels
    labs(x='', y='', fill='IAM range', shape='Sectoral'),
    theme(axis_text_x=element_text(rotation=90)),

    # Appearance
    theme(
        plot_background=element_rect(alpha=0),
        panel_background=element_rect(fill='#fef6e6'),
        strip_background=element_rect(fill='#fef6e6'),

        panel_grid_major_x=element_blank(),

        axis_text_x=element_blank(),
        strip_text=element_text(weight='bold'),
    ),

    guides(color=None),
]


@figure(region=['World'])
def fig_1(iam_data, item_data, sources):
    # TODO handle optional normalization

    # Not normalized: discard 2020 data
    iam_data = iam_data[iam_data.year != 2020]
    item_data = item_data[~item_data.year.isin([2020, 2100])]

    log.info('Units: {} {}'.format(
        sorted(iam_data['unit'].unique()),
        sorted(item_data['unit'].unique())))

    # Transform from individual data points to descriptives
    plot_data = iam_data.pipe(compute_descriptives)
    item_range_data = item_data.pipe(compute_descriptives)

    plot = (
        ggplot(aes(x='model'), plot_data)
        + FIG1_STATIC
        + geom_crossbar(
            aes(ymin='min', y='50%', ymax='max', fill='category'),
            item_range_data,
            color='black', fatten=0, width=None)
        + geom_point(
            aes(y='value'), item_data,
            color='black', size=1, shape='x', fill=None)
    )
    plot.units = sorted(iam_data['unit'].unique())[0]

    return plot


@figure()
def fig_2(iam_data, item_data, sources):
    # Restore the 'type' dimension to each data set
    item_data['type'] = item_data['variable'].replace({'tkm': 'Freight',
                                                       'pkm': 'Passenger'})

    # TODO handle optional normalization

    # Not normalized: discard 2020 data
    iam_data = iam_data[iam_data.year != 2020]
    item_data = item_data[~item_data.year.isin([2020, 2100])]

    # Transform from individual data points to descriptives
    plot_data = iam_data.pipe(compute_descriptives) \
                        .pipe(apply_plot_meta, sources[0])
    item_plot_data = item_data.pipe(apply_plot_meta, sources[1])

    plot = (
        ggplot(aes(x='model'), plot_data)
        + FIG1_STATIC
        + geom_point(
            mapping=aes(y='value', shape='model'),
            data=item_plot_data,
            color='black', size=2, fill=None)
    )

    plot.units = '—'

    return plot


@figure()
def fig_3(iam_data, item_data, sources):
    iam_data = iam_data \
        .pipe(compute_shares, 'mode')

    # TODO mode shares from individual variables
    plot_data = iam_data.pipe(compute_descriptives) \
                        .pipe(apply_plot_meta, sources[0])

    plot = ggplot(aes(x='model'), plot_data)

    plot.units = '—'

    return plot


FIG4_STATIC = [
    aes(x='category + year', color='category'),

    facet_wrap('type'),

    # Ranges of data as vertical bars
    geom_crossbar(aes(ymin='min', y='50%', ymax='max'),
                  color='black', fill='white', width=None),
    geom_crossbar(aes(ymin='25%', y='50%', ymax='75%', fill='category'),
                  color='black', width=None),

    # Labels with group counts
    geom_text(
        aes(label='count', y='max', color='category'),
        format_string='{:.0f}',
        va='bottom',
        size=7),

    # Scales
    scale_x_discrete(limits=SCALE_CAT['limit'], labels=SCALE_CAT['label']),
    scale_fill_manual(limits=SCALE_CAT['limit'], values=SCALE_CAT['fill']),
    scale_color_manual(limits=SCALE_CAT['limit'], values=SCALE_CAT['fill']),
]


@figure()
def fig_4(iam_data, item_data, sources):
    # Compute energy intensity
    plot_data = iam_data \
        .pipe(compute_ratio, groupby=['type'],
              num="quantity == 'Final Energy'",
              denom="quantity == 'Energy Service'")

    # TODO compute carbon intensity of energy
    # TODO compute energy intensity of sectoral models
    plot_data = iam_data.pipe(compute_descriptives) \
                        .pipe(apply_plot_meta, sources[0])

    plot = ggplot(aes(x='model'), plot_data) + FIG4_STATIC

    plot.units = '—'

    return plot


@figure()
def fig_5(iam_data, item_data, sources):
    # Restore the 'fuel' dimension to the IAM data
    expr = (r'Final Energy\|Transportation'
            r'(?:\|(?P<fuel>.*))?')
    iam_data = restore_dims(iam_data, expr)

    # TODO compute fuel shares from individual variables
    plot_data = iam_data.pipe(compute_descriptives) \
                        .pipe(apply_plot_meta, sources[0])

    plot = ggplot(aes(x='model'), plot_data)

    plot.units = '—'

    return plot
