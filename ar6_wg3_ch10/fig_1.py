from functools import partial

import plotnine as p9

from .data import compute_descriptives, normalize_if, select_indicator_scenarios
from .common import COMMON, figure

# Non-dynamic features of fig_1
STATIC = (
    [
        # Horizontal panels by the years shown
        p9.facet_wrap("year", ncol=4, scales="free_x"),
        # Geoms
    ]
    + COMMON["ranges"]
    + [
        COMMON["counts"],
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank(),),
        p9.guides(color=None),
    ]
)


@figure(region=["World"])
def plot(data, sources, normalize, overshoot, **kwargs):
    # Normalize
    data["iam"] = data["iam"].pipe(normalize_if, normalize, year=2020)

    # Select indicator scenarios
    data["indicator"] = data["iam"].pipe(select_indicator_scenarios)

    # Transform from individual data points to descriptives
    data["plot"] = data["iam"].pipe(compute_descriptives)

    # Discard 2100 sectoral data
    data["item"] = data["item"][data["item"].year != 2100]

    if normalize:
        # Store the absolute data
        data["item-absolute"] = data["item"]
        # Replace with the normalized data
        data["item"] = data["item"].pipe(normalize_if, normalize, year=2020)

    data["plot-item"] = data["item"].pipe(compute_descriptives)

    # Set the y scale
    # Clip out-of-bounds data to the scale limits
    scale_y = partial(p9.scale_y_continuous, oob=lambda s, lim: s.clip(*lim))
    if normalize:
        scale_y = scale_y(limits=(-0.5, 2.5), minor_breaks=4, expand=(0, 0, 0, 0.08))
    else:
        # NB if this figure is re-added to the text, re-check this scale
        scale_y = scale_y(limits=(-5000, 20000))

    plot = (
        p9.ggplot(data=data["plot"])
        + STATIC
        # Aesthetics and scales
        + scale_y
        + COMMON["x category"](overshoot)
        + COMMON["color category"](overshoot)
        + COMMON["fill category"](overshoot)
        # Points for indicator scenarios
        + p9.geom_point(
            p9.aes(y="value", shape="scenario"),
            data["indicator"],
            color="yellow",
            size=1,
            # shape="x",
            fill=None,
        )
        # Points and bar for sectoral models
        + p9.geom_crossbar(
            p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
            data["plot-item"],
            color="black",
            fatten=0,
            width=None,
        )
        + p9.geom_point(
            p9.aes(y="value"), data["item"], color="black", size=1, shape="x", fill=None
        )
    )

    if normalize:
        plot.units = "Index, 2020 level = 1.0"
    else:
        plot.units = sorted(data["iam"]["unit"].unique())[0]

    return plot
