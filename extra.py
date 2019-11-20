"""Extra figures for reference, comparing IPCC SR1.5 and iTEM2 data.

Repurposed from P.N. Kishimoto code for iTEM4, October 2018.
"""
from functools import lru_cache

import item.model
import matplotlib as mpl
import pandas as pd
import plotnine as p9

from data import compute_descriptives, data_path, get_data


# Metadata for categories and 'super'categories
# - The colour for 2C is midway between the colours for 'Higher-' and 'Lower
#   2C', etc.
cat_meta = pd.DataFrame([
    ('Above 2C',            'red',     r'>2°',   ''),
    ('2C',                  '#ca34de', r'2°',    ''),  # Supercategory
    ('Higher 2C',           'purple',  r'hi',    '2C'),
    ('Lower 2C',            'magenta', r'lo',    '2C'),
    ('1.5C',                '#fca503', r'1.5°',  ''),  # Supercategory
    ('1.5C high overshoot', '#f97306', r'hi',    '1.5C'),
    ('1.5C low overshoot',  'gold',    r'lo',    '1.5C'),
    ('Below 1.5C',          'green',   r'<1.5°', ''),
    ('reference',           'black',   'Ref',    'item'),
    ('policy',              'black',   'Pol',    'item'),
    ], columns=['category', 'color',   'label',  'supercategory'])


# Variables
# - Keys are SR1.5 variable strings.
# - Values are tuples of (iTEM2 selectors dict, conversion factor)
variables_to_plot = {
    # 'Emissions|CO2': (None, 1),
    # 'Emissions|CO2|Energy': (None, 1),
    # 'Emissions|CO2|Energy|Demand': (None, 1),
    'Emissions|CO2|Energy|Demand|Transportation':
        (dict(Variable='ttw_co2e'), 1),
    # 'Final Energy', None, 1),
    'Final Energy|Transportation':
        (dict(Variable='energy'), 1e-3),
    'Final Energy|Transportation|Electricity':
        (dict(Variable='energy', Fuel='Electricity'), 1e-3),
    # 'Final Energy|Transportation|Fossil': (None, 1),
    # 'Final Energy|Transportation|Gases': (None, 1),
    # 'Final Energy|Transportation|Geothermal': (None, 1),
    # 'Final Energy|Transportation|Hydrogen': (None, 1),
    # 'Final Energy|Transportation|Heat': (None, 1),
    'Final Energy|Transportation|Freight':
        (None, None),  # Sum of several categories
    'Energy Service|Transportation|Freight':
        (dict(Variable='tkm'), 1),
    'Energy Service|Transportation|Freight|Aviation':
        (None, None),  # Not in iTEM2 database
    'Energy Service|Transportation|Freight|Navigation':
        (None, None),  # NB sum of 'Domestic-' and 'International Shipping'
    'Energy Service|Transportation|Freight|Railways':
        (dict(Variable='tkm', Mode='Freight Rail'), 1),
    'Energy Service|Transportation|Freight|Road':
        (dict(Variable='tkm', Mode='HDT'), 1),
    'Energy Service|Transportation|Passenger':
        (dict(Variable='pkm'), 1),
    'Energy Service|Transportation|Passenger|Aviation':
        (dict(Variable='pkm', Mode='Aviation'), 1),
    'Energy Service|Transportation|Passenger|Railways':
        (dict(Variable='pkm', Mode='Passenger Rail'), 1),
    'Energy Service|Transportation|Passenger|Road':
        (dict(Variable='pkm', Mode='Road'), 1),
    }


def prepare_data_sr15():
    source = 'SR15'

    # Read SR15 data from local cache using a subset of variables;
    # drop scenarios that belong to no recognized category
    data = get_data(source, use_cache=True, vars_from_file=True,
                    year=[2030, 2050, 2100], region=['World']) \
        .dropna(subset=['category'])

    # Filter further by category;
    # add plotting metadata: color, label, supercategory
    data = data[~data.category.isin(['no-climate-assessment', 'reference'])] \
        .merge(cat_meta, how='left', on='category')

    # Compute descriptives by variable, then re-merge the category-level
    # metadata
    result = data.pipe(compute_descriptives) \
                 .reset_index() \
                 .merge(cat_meta, how='left', on='category')

    # Return both scenario-level data and descriptives by variable
    return data, result


@lru_cache()
def load_data_item2():
    # Read iTEM2 model database
    data = pd.read_csv(data_path / 'iTEM-MIP2.csv')

    # Remove private companies' projections
    data = data[~data.Model.isin(['BP', 'ExxonMobil', 'Shell'])]

    # Filter data
    return data \
        .set_index(['Model', 'Scenario', 'Region', 'Mode',
                   'Technology', 'Fuel', 'Variable', 'Unit']) \
        .xs(('Global', 'All'), level=('Region', 'Technology')) \
        .filter(items=['2030', '2050']) \
        .rename_axis('year', axis=1) \
        .stack() \
        .rename('value')


@lru_cache()
def scen_info(name):
    """Return iTEM metadata for model *name*."""
    name = {'WEPS+': 'EIA'}.get(name, name)
    return item.model.load_model_scenarios(name.lower(), 2)


def prepare_data_item2(var):
    """Retrieve iTEM2 data for *var*."""
    sel, cf = variables_to_plot[var]
    if sel is None:
        raise KeyError(var)

    # Select relevant data
    selectors = dict(Mode='All', Fuel='All')
    selectors.update(sel)
    levels = list(selectors.keys())
    labels = list(selectors.values())

    # Apply the conversion factor and convert a pd.Series to pd.DataFrame
    df = (load_data_item2().xs(labels, level=levels).copy() * cf) \
        .reset_index() \
        .astype({'year': int})

    # Store category
    df['supercategory'] = 'item'

    # Determine scenario category
    def cat_for_scen(row):
        result = scen_info(row['Model'])[row['Scenario']]['category']
        return result
    df['category'] = df.apply(cat_for_scen, axis=1)

    return df


# Matplotlib style
mpl.rc('font', **{'family': 'sans-serif', 'sans-serif': ['Helvetica']})

# Common plot features
plot_common = [
    # Aesthetic mappings
    p9.aes(x='category', color='category'),

    # Two panels wide by the two years shown
    p9.facet_wrap('year'),

    # Vertical bars showing range of projections
    p9.geom_linerange(p9.aes(ymin='min', ymax='max'), size=6, color='#bbbbbb'),
    p9.geom_linerange(p9.aes(ymin='25%', ymax='75%'), size=6),

    # Median
    p9.geom_point(p9.aes(y='50%'), color='black', shape='_', size=6),

    # Vertical lines to separate scenario groups
    p9.geom_vline(xintercept=1.5, color='#bbbbbb'),
    p9.geom_vline(xintercept=4.5, color='#bbbbbb'),
    p9.geom_vline(xintercept=7.5, color='#bbbbbb'),
    p9.geom_vline(xintercept=8.5, color='#999999'),

    # # Counts of number of scenarios included
    p9.geom_text(p9.aes(label='count', y='max'), format_string='{:.0f}',
                 va='bottom',),

    # x-scale order and labels. Use 'expand' to leave room on right for iTEM2
    p9.scale_x_discrete(limits=cat_meta['category'],
                        labels=cat_meta['label'],
                        expand=(0, 0.5, 0, 1)),
    # color scale values
    p9.scale_color_manual(cat_meta['color'], limits=cat_meta['category']),

    # Axis labels
    p9.labs(x='', color='SR1.5 IAM scenarios',
            shape='Global transport models'),
    p9.guides(color=p9.guide_legend(ncol=2),
              shape=p9.guide_legend(ncol=2)),

    p9.theme(plot_background=p9.element_rect(alpha=0)),
    ]


# Create plot objects
def gen_plots():
    data, plot_data = prepare_data_sr15()

    for var in variables_to_plot.keys():
        # Select data
        df = plot_data[plot_data.variable == var]

        # Y-axis label
        row = data[data.variable == var]
        if not len(row):
            # No SR1.5 data for this variable
            continue

        labels = p9.labs(y=row.iloc[0, :]['unit']) + p9.ggtitle(var)

        # Create the plot
        plot = p9.ggplot(df) + plot_common + labels
        try:
            plot += p9.geom_point(mapping=p9.aes(y='value', shape='Model'),
                                  data=prepare_data_item2(var),
                                  color='black', size=2, fill=None)
        except KeyError:
            # No iTEM2 data for this variable
            pass

        print('Plotting {}'.format(var))

        yield plot
