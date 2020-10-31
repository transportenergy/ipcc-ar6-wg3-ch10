import logging

import numpy as np
import plotnine as p9

from .common import COMMON, SCALE_FUEL, figure
from .data import compute_descriptives, compute_shares, select_indicator_scenarios
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_5
STATIC = [
    # Horizontal panels by 'year'
    p9.facet_wrap("year", nrow=3),
    # Aesthetics and scales
    ] + COMMON["x category short"] + [
    p9.aes(color="fuel"),
    p9.scale_y_continuous(limits=(-0.02, 1), breaks=np.linspace(0, 1, 6)),
    p9.scale_color_manual(
        limits=SCALE_FUEL["limit"],
        values=SCALE_FUEL["fill"],
        labels=SCALE_FUEL["label"],
    ),
    p9.scale_fill_manual(
        limits=SCALE_FUEL["limit"],
        values=SCALE_FUEL["fill"],
        labels=SCALE_FUEL["label"],
    ),
    # Geoms
    # Like COMMON['ranges'], with fill='fuel', position='dodge' and no width=
    p9.geom_crossbar(
        p9.aes(ymin="min", y="50%", ymax="max", group="fuel"),
        position="dodge",
        color="black",
        fill="white",
        width=0.9,
    ),
    p9.geom_crossbar(
        p9.aes(ymin="25%", y="50%", ymax="75%", fill="fuel"),
        position="dodge",
        color="black",
        width=0.9,
    ),
    # # Like COMMON['counts'], except color is 'fuel'
    # p9.geom_text(
    #     p9.aes(label="count", y=-0.01, angle=45, color="fuel"),
    #     position=p9.position_dodge(width=0.9),
    #     # commented: this step is extremely slow
    #     # adjust_text=dict(autoalign=True),
    #     format_string="{:.0f}",
    #     va="top",
    #     size=3,
    # ),
    # Axis labels
    p9.labs(y="", fill="Energy carrier"),
    # Hide legend for 'color'
    p9.guides(color=None),
    # Appearance
    COMMON["theme"],
    p9.theme(
        axis_text_x=p9.element_text(size=7),
        panel_grid_major_x=p9.element_blank(),
    ),
]


@figure
def plot(data, sources, **kwargs):
    # Compute fuel shares by type for IAM scenarios
    data["iam"] = (
        data["iam"].pipe(compute_shares, on="fuel", groupby=["region"])
        .assign(variable="Fuel share")
    )

    # Compute fuel shares for sectoral scenarios
    # - Modify labels to match IAM format
    data["item"] = (
        data["item"]
        .replace(
            {
                "fuel": {
                    "All": None,
                    "Biomass Liquids": "Liquids|Biomass",
                    "Fossil Liquids": "Liquids|Oil",
                }
            }
        )
        .pipe(compute_shares, on="fuel", groupby=["region"])
        .assign(variable="Fuel share")
    )

    # Discard 2020 data
    data["iam"] = data["iam"][data["iam"].year != 2020]
    data["item"] = data["item"][data["item"].year != 2020]

    # Select indicator scenarios
    data["indicator"] = data["iam"].pipe(select_indicator_scenarios)

    # Transform from individual data points to descriptives
    data["plot"] = data["iam"].pipe(compute_descriptives, groupby=["fuel", "region"])

    # Omit supercategories ('category+1') from iTEM descriptives
    data["plot-item"] = (
        data["item"]
        .drop("category+1", axis=1)
        .pipe(compute_descriptives, groupby=["fuel", "region"])
    )

    title = kwargs["title"].format(units="share")

    plots = []

    for group, d in groupby_multi(
        (data["plot"], data["indicator"], data["plot-item"], data["item"]), "region"
    ):
        if len(d[0]) == 0:
            log.info(f"Skip {group}; no IAM data")
            continue

        print(list(
            f"{k} {len(v)}" for k, v
            in zip(["plot", "indicator", "plot-item", "item"], d)
        ))
        p = (
            p9.ggplot(data=d[0])
            + STATIC
            + p9.ggtitle(title.format(group=group))
            + kwargs["figure size"]
            + p9.labs(shape="Indicator scenario")
        )

        if len(d[1]):
            # Points for indicator scenarios
            p = p + p9.geom_point(
                p9.aes(y="value", shape="scenario", group="fuel"),
                d[1],
                position=p9.position_dodge(width=0.9),
                color="cyan",
                size=1,
                # shape="x",
                fill=None,
            )

        if len(d[2]):
            # Points and bar for sectoral models
            p = (
                p
                + p9.geom_crossbar(
                    p9.aes(ymin="min", y="50%", ymax="max", fill="fuel"),
                    d[2],
                    position="dodge",
                    color="black",
                    fatten=0,
                    width=0.9,
                )
                + p9.geom_point(
                    p9.aes(y="value", group="fuel"),
                    d[3],
                    position=p9.position_dodge(width=0.9),
                    color="black",
                    size=1,
                    shape="x",
                    fill=None,
                )
            )

        plots.append(p)

    return plots
