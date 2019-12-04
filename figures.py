import logging
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
from plotnine import (
    aes,
    element_blank,
    element_rect,
    element_text,
    facet_grid,
    facet_wrap,
    geom_crossbar,
    geom_line,
    geom_point,
    # geom_ribbon,
    geom_text,
    ggplot,
    ggtitle,
    guides,
    labs,
    position_dodge,
    scale_color_brewer,
    scale_color_manual,
    scale_fill_manual,
    scale_x_discrete,
    scale_x_continuous,
    scale_y_continuous,
    theme,
)
import yaml

from data import (
    compute_descriptives,
    compute_ratio,
    compute_shares,
    get_data,
    normalize_if,
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


# Common plot components.

COMMON = {
    # Ranges of data as vertical bars
    'ranges': [
        geom_crossbar(
            aes(ymin='min', y='50%', ymax='max'),
            color='black', fill='white', width=None),
        geom_crossbar(
            aes(ymin='25%', y='50%', ymax='75%', fill='category'),
            color='black', width=None),
        ],

    # Background colours
    'theme': theme(
        panel_background=element_rect(fill='#fef6e6'),
        strip_background=element_rect(fill='#fef6e6'),
        strip_text=element_text(weight='bold'),
        ),

    # Labels with group counts
    'counts': geom_text(
        aes(label='count', y='max', color='category'),
        format_string='{:.0f}',
        va='bottom',
        size=7),

    # Scales
    'x category': [
        aes(x='category'),
        scale_x_discrete(limits=SCALE_CAT['limit'], labels=SCALE_CAT['label']),
        labs(x=''),
        theme(axis_text_x=element_blank()),
        ],
    'fill category': scale_fill_manual(
        limits=SCALE_CAT['limit'], values=SCALE_CAT['fill']),
    'color category': [
        aes(color='category'),
        scale_color_manual(limits=SCALE_CAT['limit'],
                           values=SCALE_CAT['fill']),
        ],
}


def figure(sources=('AR6', 'iTEM MIP2'), **filters):
    """Decorator to handle common plot tasks.

    Example:

      @figure()
      def fig_N(data, sources)
          # Generate plot...
          plot.units = 'kg'
          return plot

      fig_N(options)

    A method (here 'fig_N') wrapped with this decorator:

    - Receives a dict *data*, with pre-loaded data for the variables under
      'fig_N' in figures.yaml. See inline comments in that file.
    - Receives a 2-tuple *sources*,  indicating the original data sources for
      IAM and sectoral models.
    - Must return a plotnine.ggplot object with a 'units' attribute.

    The decorated method is then called with a *different* signature, taking
    only one argument: an optional dict of *options*. These include:

    - 'load_only': if True, then the plot is not written to file. Otherwise,
      the returned plot object is saved to 'fig_N.pdf'.

    """
    # Function that decorates the method
    def figure_decorator(func):
        # Information about the figure.
        # NB this code is run at the moment that the function is decorated.
        fig_id = func.__name__
        fig_info = INFO[fig_id]
        var_names = fig_info['variables']

        if not fig_info.get('all years', False):
            filters['year'] = YEARS

        # Wrapped method with new signature
        def wrapped(options={}):
            # NB this code not run until the figure is plotted.

            # Log output
            log.info('-' * 10)
            log.info(f'{fig_id}')

            load_only = options['load_only']
            to_load = load_only or 'iam item'

            # Load IAM and iTEM data
            data = {}
            if 'iam' in to_load:
                data['iam'] = get_data(source=sources[0],
                                       variable=var_names, **filters) \
                    .pipe(restore_dims, fig_info.get('restore dims', None))
            if 'item' in to_load:
                data['item'] = get_data(source=sources[1],
                                        conform_to=sources[0],
                                        variable=var_names,
                                        **filters)

            # Generate the plot
            args = dict(
                data=data,
                sources=sources)
            args['normalize'] = options['normalize']
            plot = func(**args)

            if plot:
                # Add a title
                plot += ggtitle(f"{fig_info['short title']} [{plot.units}] "
                                f"({fig_id}/{'/'.join(sources)})")

            base_fn = OUTPUT_PATH / f'{fig_id}'

            # Save data to file.
            # Do this before plotting, so the data can be inspected even if the
            # plot is not constructed properly and fails.
            for label, df in data.items():
                path = OUTPUT_PATH / 'data' / f'{fig_id}-{label}.csv'
                log.info(f'Dump {len(df):5} obs to {path}')
                df.to_csv(path)

            if fig_info.get('normalized version', False):
                # Distinguish normalized and absolute versions in file name
                base_fn = base_fn.with_name(
                    base_fn.name
                    + ('-normalized' if args['normalize'] else '-absolute'))

            # Save to file unless --load-only was given.
            if plot and not load_only:
                args = dict(
                    verbose=False,
                    width=190,
                    # Aspect ratio from figures.yaml
                    height=190 * fig_info.get('aspect ratio', 100 / 190),
                    units='mm')
                plot.save(base_fn.with_suffix('.pdf'), **args)
                plot.save(base_fn.with_suffix('.png'), **args, dpi=300)

        return wrapped
    return figure_decorator


# Non-dynamic features of fig_1
FIG1_STATIC = [
    # Horizontal panels by the years shown
    facet_wrap('year', ncol=4, scales='free_x'),

    # Aesthetics and scales
    ] + COMMON['x category'] + COMMON['color category'] + [
    COMMON['fill category'],

    # Geoms
    ] + COMMON['ranges'] + [
    COMMON['counts'],

    # Axis labels
    labs(y='', fill='IAM/sectoral scenarios'),

    # Appearance
    COMMON['theme'],
    theme(
        panel_grid_major_x=element_blank(),
    ),
    guides(color=None),
]


@figure(region=['World'])
def fig_1(data, sources, **kwargs):

    # Transform from individual data points to descriptives
    data['plot'] = data['iam'] \
        .pipe(normalize_if, kwargs['normalize'], year=2020) \
        .pipe(compute_descriptives)

    # Discard 2100 sectoral data
    data['item'] = data['item'][data['item'].year != 2100]

    if kwargs['normalize']:
        # Store the absolute data
        data['item-absolute'] = data['item']
        # Replace with the normalized data
        data['item'] = data['item'] \
            .pipe(normalize_if, kwargs['normalize'], year=2020)

    data['plot-item'] = data['item'].pipe(compute_descriptives)

    plot = (
        ggplot(data=data['plot']) + FIG1_STATIC

        # Points and bar for sectoral models
        + geom_crossbar(
            aes(ymin='min', y='50%', ymax='max', fill='category'),
            data['plot-item'],
            color='black', fatten=0, width=None)
        + geom_point(
            aes(y='value'), data['item'],
            color='black', size=1, shape='x', fill=None)
    )

    if kwargs['normalize']:
        plot.units = 'Index, 2020 level = 1.0'
    else:
        plot.units = sorted(data['iam']['unit'].unique())[0]

    return plot


# Non-dynamic features of fig_2
FIG2_STATIC = [
    # Horizontal panels by type; vertical panels by years
    facet_grid('type ~ year', scales='free_x'),

    # Aesthetics and scales
    ] + COMMON['x category'] + COMMON['color category'] + [
    COMMON['fill category'],

    # Geoms
    ] + COMMON['ranges'] + [
    COMMON['counts'],

    # Axis labels
    labs(y='', fill='IAM/sectoral scenarios'),

    # Appearance
    COMMON['theme'],
    theme(
        panel_grid_major_x=element_blank(),
    ),
    guides(color=None),
]


@figure(region=['World'])
def fig_2(data, sources, **kwargs):
    # TODO compute per-capita quantity
    # TODO handle 'normalize' option

    # Restore the 'type' dimension to each data set
    data['item']['type'] = data['item']['variable'] \
        .replace({'tkm': 'Freight', 'pkm': 'Passenger'})

    if kwargs['normalize']:
        data['iam'] = normalize(data['iam'], year=2020)

    # Discard 2020 data
    data['iam'] = data['iam'][data['iam'].year != 2020]
    data['item'] = data['item'][~data['item'].year.isin([2020, 2100])]

    # Transform from individual data points to descriptives
    data['plot'] = data['iam'].pipe(compute_descriptives, groupby=['type'])
    data['plot-item'] = data['item'].pipe(compute_descriptives,
                                          groupby=['type'])

    plot = (
        ggplot(data=data['plot']) + FIG2_STATIC

        # Points and bar for sectoral models
        + geom_crossbar(
            aes(ymin='min', y='50%', ymax='max', fill='category'),
            data['plot-item'],
            color='black', fatten=0, width=None)
        + geom_point(
            aes(y='value'), data['item'],
            color='black', size=1, shape='x', fill=None)
    )

    units = data['iam']['unit'].str.replace('bn', '10⁹')
    plot.units = '; '.join(units.unique())

    return plot


# Non-dynamic features of fig_3
FIG3_STATIC = [
    # Horizontal panels by scenario category; vertical panels by pax./freight
    facet_grid('type ~ category', scales='free_x'),

    # Aesthetics and scales
    aes(x='year', color='mode'),
    scale_x_continuous(limits=(2020, 2100), breaks=np.linspace(2020, 2100, 5),
                       labels=['', 2040, '', 2080, '']),
    scale_y_continuous(limits=(0, 1), breaks=np.linspace(0, 1, 6)),
    scale_color_brewer(type='qual', palette='Dark2'),
    # ] + COMMON['color category'] + [

    # Geoms
    # geom_ribbon(aes(ymin='25%', ymax='75%', fill='mode'), alpha=0.25),
    # geom_line(aes(y='50%')),
    geom_line(aes(y='value', group='model + scenario + mode'), alpha=0.6),

    # Axis labels
    labs(x='', y='', color='Mode'),

    # Appearance
    COMMON['theme'],
    guides(group=None),
]


@figure(region=['World'])
def fig_3(data, sources, **kwargs):
    # Compute mode shares by type for IAM scenarios
    data['iam'] = data['iam'] \
        .pipe(compute_shares, on='mode', groupby=['type']) \
        .assign(variable='Mode share')

    # Compute fuel shares for sectoral scenarios
    # - Modify labels to match IAM format
    data['item'] = data['item'] \
        .assign(type=data['item']['variable'].replace(
            {'pkm': 'Passenger', 'tkm': 'Freight'})) \
        .replace({'mode': {
            'All': None,
            'Passenger Rail': 'Railways',
            'Freight Rail': 'Railways',
            '2W and 3W': 'Road|2-/3W',
            'Bus': 'Road|Bus',
            'HDT': 'Road|HDT',
            }}) \
        .pipe(compute_shares, on='mode', groupby=['type']) \
        .assign(variable='Mode share')

    # # Separate the IAM and sectoral modes so they can be coloured differently
    # for k in data.keys():
    #     data[k]['mode'] = k + '|' + data[k]['mode']

    plot = (
        ggplot(data=data['iam']) + FIG3_STATIC

        + geom_line(
            aes(y='value', group='model + scenario + mode'),
            data['item'],
            alpha=0.6)
    )

    plot.units = '0̸'

    return plot


# Non-dynamic features of fig_4
FIG4_STATIC = [
    # Horizontal panels by freight/passenger
    facet_grid('type ~ year'),

    # Aesthetics and scales
    ] + COMMON['x category'] + COMMON['color category'] + [
    COMMON['fill category'],

    # Geoms
    ] + COMMON['ranges'] + [
    COMMON['counts'],

    # Axis labels
    labs(y='', fill='IAM/sectoral scenarios'),

    # Appearance
    COMMON['theme'],
    theme(
        panel_grid_major_x=element_blank(),
    ),
    guides(color=None),
]


@figure(region=['World'])
def fig_4(data, sources, **kwargs):
    # Compute energy intensity for IAM scenarios
    data['iam'] = data['iam'] \
        .pipe(compute_ratio, groupby=['type'],
              num="quantity == 'Final Energy'",
              denom="quantity == 'Energy Service'") \
        .assign(variable='Energy intensity of transport')

    units = sorted(map(str, data['iam']['unit'].unique()))

    data['plot'] = data['iam'].pipe(compute_descriptives, groupby=['type'])

    # Compute energy intensity for sectoral scenarios
    data['item'] = data['item'] \
        .pipe(compute_ratio, groupby=['type'],
              num="quantity == 'Final Energy'",
              denom="quantity == 'Energy Service'")
    data['plot-item'] = data['item'].pipe(compute_descriptives,
                                          groupby=['type'])

    # TODO compute carbon intensity of energy

    plot = ggplot(data=data['plot']) + FIG4_STATIC + [
        # Points and bar for sectoral models
        + geom_crossbar(
            aes(ymin='min', y='50%', ymax='max', fill='category'),
            data['plot-item'],
            color='black', fatten=0, width=None)
        + geom_point(
            aes(y='value'), data['item'],
            color='black', size=1, shape='x', fill=None)
    ]

    plot.units = units

    return plot


# Non-dynamic features of fig_5
SCALE_FUEL = pd.DataFrame([
    ['Liquids|Oil', '#f7a800', 'Oil'],
    ['Liquids|Biomass', '#de4911', 'Biofuels'],
    ['Gases', '#9e2b18', 'Gas'],
    ['Electricity', '#9fca71', 'Electricity'],
    ['Hydrogen', '#59a431', 'Hydrogen'],
    ], columns=['limit', 'fill', 'label'])


FIG5_STATIC = [
    # Horizontal panels by 'facet', combining 'year' and 'category'
    facet_wrap('year', ncol=3, scales='free_x'),

    # Aesthetics and scales
    aes(x='category', color='fuel'),
    scale_x_discrete(limits=SCALE_CAT['limit'],
                     labels=SCALE_CAT['label']),
    scale_y_continuous(limits=(-0.02, 1), breaks=np.linspace(0, 1, 6)),
    scale_color_manual(limits=SCALE_FUEL['limit'],
                       values=SCALE_FUEL['fill'],
                       labels=SCALE_FUEL['label']),
    scale_fill_manual(limits=SCALE_FUEL['limit'],
                      values=SCALE_FUEL['fill'],
                      labels=SCALE_FUEL['label']),

    # Geoms
    # Like COMMON['ranges'], with fill='fuel', position='dodge' and no width=
    geom_crossbar(
        aes(ymin='min', y='50%', ymax='max', group='fuel'), position='dodge',
        color='black', fill='white', width=0.9),
    geom_crossbar(
        aes(ymin='25%', y='50%', ymax='75%', fill='fuel'), position='dodge',
        color='black', width=0.9),
    # Like COMMON['counts'], except color is 'fuel'
    geom_text(
        aes(label='count', y=-0.01, angle=45, color='fuel'),
        position=position_dodge(width=0.9),
        # commented: this step is extremely slow
        # adjust_text=dict(autoalign=True),
        format_string='{:.0f}',
        va='top', size=3),

    # Axis labels
    labs(x='', y='', fill='Energy carrier'),
    # theme(axis_text_x=element_blank()),

    # Hide legend for 'color'
    guides(color=None),

    # Appearance
    COMMON['theme'],
    theme(
        axis_text_x=element_text(rotation=45),
        panel_grid_major_x=element_blank(),
    ),
]


@figure(region=['World'])
def fig_5(data, sources, **kwargs):
    # TODO reorder colours from Oil -> Hydrogen per AR6

    # Compute fuel shares by type for IAM scenarios
    data['iam'] = data['iam'] \
        .pipe(compute_shares, on='fuel') \
        .assign(variable='Fuel share')

    # Compute fuel shares for sectoral scenarios
    # - Modify labels to match IAM format
    data['item'] = data['item'] \
        .replace({'fuel': {
            'All': None,
            'Biomass Liquids': 'Liquids|Biomass',
            'Fossil Liquids': 'Liquids|Oil',
            }}) \
        .pipe(compute_shares, on='fuel') \
        .assign(variable='Fuel share')

    # Discard 2020 data
    data['iam'] = data['iam'][data['iam'].year != 2020]
    data['item'] = data['item'][data['item'].year != 2020]

    # Plot descriptives
    data['plot'] = data['iam'].pipe(compute_descriptives, groupby=['fuel'])
    # Omit supercategories ('category+1') from iTEM descriptives
    data['plot-item'] = data['item'] \
        .drop('category+1', axis=1) \
        .pipe(compute_descriptives, groupby=['fuel'])

    plot = (
        ggplot(data=data['plot']) + FIG5_STATIC +

        # Points and bar for sectoral models
        geom_crossbar(
            aes(ymin='min', y='50%', ymax='max', fill='fuel'),
            data['plot-item'],
            position='dodge',
            color='black', fatten=0, width=0.9)
        + geom_point(
            aes(y='value', group='fuel'), data['item'],
            position=position_dodge(width=0.9),
            color='black', size=1, shape='x', fill=None)
    )

    plot.units = '0̸'

    return plot
