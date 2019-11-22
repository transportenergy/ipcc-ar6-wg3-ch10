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

from data import (
    apply_plot_meta,
    compute_descriptives,
    get_data,
    get_data_item,
    item_var_info,
)

log = logging.getLogger()

OUTPUT_PATH = Path('output')


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
    geom_linerange(aes(ymin='25%', ymax='75%', color='model'), size=4),

    # Median
    geom_point(aes(y='50%'), color='black', shape='_', size=3.5),

    # Counts
    geom_text(aes(label='count'), y=0, size=5),

    # Axis labels
    labs(x='', y='Transport CO₂ emissions [Mt/y]', color='Model'),
    theme(axis_text_x=element_text(rotation=90)),

    theme(plot_background=element_rect(alpha=0)),
]


def fig_1():
    var_name = 'Transport|CO2|All'
    years = [2030, 2050, 2100]
    source = 'AR6'
    data = get_data(source=source,
                    variable=[var_name],
                    region=['World'],
                    year=years) \
        .pipe(apply_plot_meta, source)
    plot_data = data.pipe(compute_descriptives) \
                    .pipe(apply_plot_meta, source)

    plot = (
        ggplot(aes(x='model'), plot_data)
        + ggtitle(f'Figure 1 ({source} database)')
        + FIG1_STATIC
        )

    # Info for corresponding iTEM variable
    filters, scale = item_var_info('AR6', var_name)
    filters['year'] = years
    item_data = get_data_item(filters, scale)

    plot += geom_point(
        mapping=aes(y='value', shape='model'), data=item_data,
        color='black', size=2, fill=None)

    print('Plotting Figure 1')

    plot.save(OUTPUT_PATH / 'fig_1.pdf')
