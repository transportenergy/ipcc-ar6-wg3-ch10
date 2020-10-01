import logging

import plotnine as p9

from .data import compute_descriptives, normalize_if, select_indicator_scenarios
from .common import COMMON, figure
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_2
STATIC = (
    [
        # Horizontal panels by type; vertical panels by years
        p9.facet_grid("type ~ year", scales="free_y"),
        # Geoms
    ]
    + COMMON["ranges"]
    + [
        COMMON["counts"],
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios", shape="Indicator scenario"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank(),),
        p9.guides(color=None),
    ]
)


@figure
def plot(data, sources, normalize, overshoot, **kwargs):
    # Restore the 'type' dimension to sectoral data
    data["item"]["type"] = data["item"]["variable"].replace(
        {"tkm": "Freight", "pkm": "Passenger"}
    )

    # Normalize
    data["iam"] = data["iam"].pipe(normalize_if, normalize, year=2020)

    # Select indicator scenarios
    data["indicator"] = data["iam"].pipe(select_indicator_scenarios)

    # Transform from individual data points to descriptives
    data["plot"] = data["iam"].pipe(compute_descriptives, groupby=["type", "region"])

    # Discard 2100 sectoral data
    data["item"] = data["item"][data["item"].year != 2100]

    if normalize:
        # Store the absolute data
        data["item-absolute"] = data["item"]
        # Replace with the normalized data
        data["item"] = data["item"].pipe(normalize_if, normalize, year=2020)

    data["plot-item"] = data["item"].pipe(
        compute_descriptives, groupby=["type", "region"]
    )

    if normalize:
        scale_y = [
            p9.scale_y_continuous(limits=(-0.2, 4.8), minor_breaks=4),
            p9.expand_limits(y=[0])
        ]
        title = kwargs["title"].format(units="Index, 2020 level = 1.0")
    else:
        scale_y = []
        units = data["iam"]["unit"].str.replace("bn", "10⁹")
        title = kwargs["title"].format(units="; ".join(units.unique()))

    plots = []

    for group, d in groupby_multi(
        (data["plot"], data["indicator"], data["plot-item"], data["item"]), "region"
    ):
        if len(d[0]) == 0:
            log.info(f"Skip {group}; no IAM data")
            continue

        log.info(f"Generate plot for {group}")

        p = (
            p9.ggplot(data=d[0])
            + STATIC
            # Aesthetics and scales
            + scale_y
            + COMMON["x category"](overshoot)
            + COMMON["color category"](overshoot)
            + COMMON["fill category"](overshoot)
            # Points for indicator scenarios
            + p9.geom_point(
                p9.aes(y="value", shape="scenario"),
                d[1],
                color="cyan",
                size=1,
                fill=None,
            )
            + p9.ggtitle(title.format(group=group))
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

        plots.append(p)

    return plots
