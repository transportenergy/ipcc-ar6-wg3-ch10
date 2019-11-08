import logging
from pathlib import Path

import plotnine as p9

from data import get_data
from main import output_path

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
                    region=['World'], use_cache=True)

    years = ['2020', '2030', '2050', '2100']
    data = data[data['year'].isin(years)]

    data = data.groupby(['model', 'year']) \
               .describe()['value'] \
               .reset_index() \
               .astype({'count': int})

    plot = (
        p9.ggplot(p9.aes(x='model'), data)
        + p9.facet_wrap('year', ncol=len(years))
        + p9.ggtitle(f'Figure 1 ({source} database)')
        + FIG1_STATIC
        )
    plot.save(output_path, 'fig_1.pdf'))
