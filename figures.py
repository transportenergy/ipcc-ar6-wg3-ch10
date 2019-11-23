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

YEARS = [2020, 2030, 2050, 2100]

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


def figure(func):
    """Decorator to handle common plot tasks."""
    fig_name = func.__name__

    def wrapped():
        print('\n')
        log.info(f'Plotting {fig_name}')

        # Generate the plot
        plot = func()

        if plot:
            plot.save(OUTPUT_PATH / f'{fig_name}.pdf')

    return wrapped


@figure
def fig_1():
    var_name = 'Emissions|CO2|Energy|Demand|Transportation'
    source = 'AR6'
    data = get_data(source=source,
                    variable=[var_name],
                    region=['World'],
                    year=YEARS) \
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
    filters['year'] = YEARS
    item_data = get_data_item(filters, scale)

    plot += geom_point(
        mapping=aes(y='value', shape='model'), data=item_data,
        color='black', size=2, fill=None)

    return plot


@figure
def fig_2():
    source = 'AR6'
    var_names = [
        'Energy Service|Transportation|Freight',
        'Energy Service|Transportation|Passenger'
    ]

    data = get_data(source=source,
                    variable=var_names,
                    years=YEARS)
    for var_name in var_names:
        try:
            item_filters, scale = item_var_info(source, var_name)
        except KeyError:
            continue
        item_filters['year'] = YEARS
        item_data = get_data_item(item_filters, scale)


@figure
def fig_3():
    source = 'AR6'
    var_names = [
        'Energy Service|Transportation|Aviation',
        'Energy Service|Transportation|Freight',
        'Energy Service|Transportation|Freight|Aviation',
        'Energy Service|Transportation|Freight|International Shipping',
        'Energy Service|Transportation|Freight|Navigation',
        'Energy Service|Transportation|Freight|Other',
        'Energy Service|Transportation|Freight|Railways',
        'Energy Service|Transportation|Freight|Road',
        'Energy Service|Transportation|Navigation',
        'Energy Service|Transportation|Passenger',
        'Energy Service|Transportation|Passenger|Aviation',
        'Energy Service|Transportation|Passenger|Bicycling and Walking',
        'Energy Service|Transportation|Passenger|Navigation',
        'Energy Service|Transportation|Passenger|Other',
        'Energy Service|Transportation|Passenger|Railways',
        'Energy Service|Transportation|Passenger|Road',
        'Energy Service|Transportation|Passenger|Road|2W and 3W',
        'Energy Service|Transportation|Passenger|Road|Bus',
        'Energy Service|Transportation|Passenger|Road|LDV',
    ]

    data = get_data(source=source,
                    variable=var_names,
                    years=YEARS)
    for var_name in var_names:
        try:
            item_filters, scale = item_var_info(source, var_name)
        except KeyError:
            continue
        item_filters['year'] = YEARS
        item_data = get_data_item(item_filters, scale)


@figure
def fig_4():
    source = 'AR6'
    var_names = [
        'Energy Service|Transportation|Freight',
        'Energy Service|Transportation|Passenger',
        'Final Energy|Transportation|Freight',
        'Final Energy|Transportation|Passenger',
    ]

    data = get_data(source=source,
                    variable=var_names,
                    years=YEARS)
    for var_name in var_names:
        try:
            item_filters, scale = item_var_info(source, var_name)
        except KeyError:
            continue
        item_filters['year'] = YEARS
        item_data = get_data_item(item_filters, scale)


@figure
def fig_5():
    source = 'AR6'
    var_names = [
        'Final Energy|Transportation',
        'Final Energy|Transportation|Electricity',
        'Final Energy|Transportation|Fossil',
        'Final Energy|Transportation|Gases',
        'Final Energy|Transportation|Gases|Bioenergy',
        'Final Energy|Transportation|Gases|Fossil',
        'Final Energy|Transportation|Gases|Shipping',
        'Final Energy|Transportation|Geothermal',
        'Final Energy|Transportation|Heat',
        'Final Energy|Transportation|Hydrogen',
        'Final Energy|Transportation|Liquids',
        'Final Energy|Transportation|Liquids|Bioenergy',
        'Final Energy|Transportation|Liquids|Biomass',
        'Final Energy|Transportation|Liquids|Biomass|Shipping',
        'Final Energy|Transportation|Liquids|Coal',
        'Final Energy|Transportation|Liquids|Coal|Shipping',
        'Final Energy|Transportation|Liquids|Fossil synfuel',
        'Final Energy|Transportation|Liquids|Gas',
        'Final Energy|Transportation|Liquids|Natural Gas',
        'Final Energy|Transportation|Liquids|Oil',
        'Final Energy|Transportation|Liquids|Oil|Shipping',
        'Final Energy|Transportation|Liquids|Oil|Shipping|Fuel Oil',
        'Final Energy|Transportation|Liquids|Oil|Shipping|Light Oil',
        'Final Energy|Transportation|Solar',
        'Final Energy|Transportation|Solids|Biomass',
        'Final Energy|Transportation|Solids|Coal',
    ]

    data = get_data(source=source,
                    variable=var_names,
                    years=YEARS)
    for var_name in var_names:
        try:
            item_filters, scale = item_var_info(source, var_name)
        except KeyError:
            continue
        item_filters['year'] = YEARS
        item_data = get_data_item(item_filters, scale)
