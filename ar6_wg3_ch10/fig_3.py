import numpy as np
import plotnine as p9

from .data import compute_shares
from .common import COMMON, figure

# Non-dynamic features of fig_3
STATIC = (
    [
        # Horizontal panels by scenario category; vertical panels by pax./freight
        p9.facet_grid("type ~ category", scales="free_x"),
        # Aesthetics and scales
    ]
    + COMMON["x year"]
    + [
        p9.aes(color="mode"),
        p9.scale_y_continuous(limits=(0, 1), breaks=np.linspace(0, 1, 6)),
        p9.scale_color_brewer(type="qual", palette="Dark2"),
        # Geoms
        # p9.geom_ribbon(p9.aes(ymin='25%', ymax='75%', fill='mode'), alpha=0.25),
        # p9.geom_line(p9.aes(y='50%')),
        p9.geom_line(p9.aes(y="value", group="model + scenario + mode"), alpha=0.6),
        # Axis labels
        p9.labs(y="", color="Mode"),
        # Appearance
        COMMON["theme"],
        p9.guides(group=None),
    ]
)


@figure
def plot(data, sources, **kwargs):
    # Compute mode shares by type for IAM scenarios
    data["iam"] = (
        data["iam"]
        .pipe(compute_shares, on="mode", groupby=["type"])
        .assign(variable="Mode share")
    )

    # Compute fuel shares for sectoral scenarios
    # - Modify labels to match IAM format
    data["item"] = (
        data["item"]
        .assign(
            type=data["item"]["variable"].replace(
                {"pkm": "Passenger", "tkm": "Freight"}
            )
        )
        .replace(
            {
                "mode": {
                    "All": None,
                    "Passenger Rail": "Railways",
                    "Freight Rail": "Railways",
                    "2W and 3W": "Road|2-/3W",
                    "Bus": "Road|Bus",
                    "HDT": "Road|HDT",
                }
            }
        )
        .pipe(compute_shares, on="mode", groupby=["type"])
        .assign(variable="Mode share")
    )

    # # Separate the IAM and sectoral modes so they can be coloured differently
    # for k in data.keys():
    #     data[k]['mode'] = k + '|' + data[k]['mode']

    plot = (
        p9.ggplot(data=data["iam"])
        + STATIC
        + p9.geom_line(
            p9.aes(y="value", group="model + scenario + mode"), data["item"], alpha=0.6
        )
    )

    plot.units = "0̸"

    return plot
