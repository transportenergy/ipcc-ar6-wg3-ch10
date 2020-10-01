from functools import partial
import logging

import plotnine as p9

from .data import compute_descriptives, normalize_if, select_indicator_scenarios
from .common import COMMON, figure
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_1
STATIC = (
    [
        # Horizontal panels by the years shown
        p9.facet_wrap("year", ncol=4),
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


@figure
def plot(data, sources, normalize, overshoot, **kwargs):
    # Normalize
    data["iam"] = data["iam"].pipe(normalize_if, normalize, year=2020)

    # Select indicator scenarios
    data["indicator"] = data["iam"].pipe(select_indicator_scenarios)

    # Transform from individual data points to descriptives
    data["plot"] = data["iam"].pipe(compute_descriptives, groupby=["region"])

    # Discard 2100 sectoral data
    data["item"] = data["item"].query(
        "year in [2030, 2050] and category in ['policy', 'reference']"
    )

    if normalize:
        # Store the absolute data
        data["item-absolute"] = data["item"]
        # Replace with the normalized data
        data["item"] = data["item"].pipe(normalize_if, normalize, year=2020)

    data["plot-item"] = data["item"].pipe(compute_descriptives, groupby=["region"])

    # Set the y scale
    # Clip out-of-bounds data to the scale limits
    scale_y = partial(p9.scale_y_continuous, oob=lambda s, lim: s.clip(*lim))
    if normalize:
        scale_y = scale_y(limits=(-0.5, 2.5), minor_breaks=4, expand=(0, 0, 0, 0.08))
        title = kwargs["title"].format(units="Index, 2020 level = 1.0")
    else:
        # NB if this figure is re-added to the text, re-check this scale
        scale_y = scale_y(limits=(-5000, 20000))
        title = kwargs["title"].format(units=sorted(data["iam"]["unit"].unique())[0])

    plots = []

    for group, d in groupby_multi(
        (data["plot"], data["indicator"], data["plot-item"], data["item"]), "region"
    ):
        if len(d[0]) == 0:
            log.info(f"Skip {group}; no IAM data")
            continue

        log.info(f"Generate plot for {group}")

        # Base plot
        p = (
            p9.ggplot(data=d[0])
            + STATIC
            # Aesthetics and scales
            + scale_y
            + COMMON["x category"](overshoot)
            + COMMON["color category"](overshoot)
            + COMMON["fill category"](overshoot)
            + p9.ggtitle(title.format(group=group))
        )
        plots.append(p)

        if len(d[1]):
            # Points for indicator scenarios
            p = (
                p
                + p9.geom_point(
                    p9.aes(y="value", shape="scenario"),
                    d[1],
                    color="yellow",
                    size=1,
                    fill=None,
                )
                + p9.labs(shape="Indicator scenario")
            )

        if len(d[2]):
            p = (
                p
                # Points and bar for sectoral models
                + p9.geom_crossbar(
                    p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
                    d[2],
                    color="black",
                    fatten=0,
                    width=None,
                )
                + p9.geom_point(
                    p9.aes(y="value"),
                    d[3],
                    color="black",
                    size=1,
                    shape="x",
                    fill=None,
                )
            )

    return plots
