import logging

import numpy as np
import plotnine as p9

from .common import COMMON, SCALE_FUEL, Figure
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


class Fig5(Figure):
    id = "fig_5"
    title = "Fuel shares of transport final energy — {{group}}"
    caption = """
        Based on integrated models grouped by CO2eq concentration levels by 2100 and
        compared with sectoral models (grouped by baseline and policies) in 2050.
        Box plots show minimum/maximum, 25th/75th percentile and median.
        Numbers above each bar represent the # of scenarios."""

    # Data preparation
    variables = [
        # See data/variables-AR6.txt for a fuller list
        "Final Energy|Transportation",  # denominator in shares
        "Final Energy|Transportation|Electricity",
        # "Final Energy|Transportation|Fossil",
        "Final Energy|Transportation|Gases",
        # "Final Energy|Transportation|Gases|Bioenergy",
        # "Final Energy|Transportation|Gases|Fossil",
        # "Final Energy|Transportation|Geothermal",
        # "Final Energy|Transportation|Heat",
        "Final Energy|Transportation|Hydrogen",
        # "Final Energy|Transportation|Liquids",
        # "Final Energy|Transportation|Liquids|Bioenergy",
        "Final Energy|Transportation|Liquids|Biomass",
        # "Final Energy|Transportation|Liquids|Coal",
        # "Final Energy|Transportation|Liquids|Fossil synfuel",
        # "Final Energy|Transportation|Liquids|Gas",
        # "Final Energy|Transportation|Liquids|Natural Gas",
        "Final Energy|Transportation|Liquids|Oil",
        # "Final Energy|Transportation|Solar",
        # "Final Energy|Transportation|Solids|Biomass",
        # "Final Energy|Transportation|Solids|Coal",
    ]
    restore_dims = r"Final Energy\|Transportation(?:\|(?P<fuel>.*))?"

    # Plotting
    geoms = STATIC
    aspect_ratio = 2

    def prepare_data(self, data):
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
        data["indicator"] = select_indicator_scenarios(data["iam"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(data["iam"], groupby=["fuel", "region"])

        # Omit supercategories ('category+1') from iTEM descriptives
        data["plot-item"] = (
            data["item"]
            .drop("category+1", axis=1)
            .pipe(compute_descriptives, groupby=["fuel", "region"])
        )

        self.formatted_title = self.formatted_title.format(units="share")

        return data

    def generate(self):
        keys = ["plot", "indicator", "plot-item", "item"]
        for group, d in groupby_multi([self.data[k] for k in keys], "region"):
            if len(d[0]) == 0:
                log.info(f"Skip {group}; no IAM data")
                continue

            log.info(f"Plot: {group}")

            yield self.plot_single(group, d)

    def plot_single(self, group, data):
        # Base plot
        p = (
            p9.ggplot(data=data[0])
            + self.geoms
            + p9.ggtitle(self.formatted_title.format(group=group))
            + p9.labs(shape="Indicator scenario")
        )

        if len(data[1]):
            # Points for indicator scenarios
            p += p9.geom_point(
                p9.aes(y="value", shape="scenario", group="fuel"),
                data[1],
                position=p9.position_dodge(width=0.9),
                color="cyan",
                size=1,
                # shape="x",
                fill=None,
            )

        if len(data[2]):
            # Points and bar for sectoral models
            p = p + [
                p9.geom_crossbar(
                    p9.aes(ymin="min", y="50%", ymax="max", fill="fuel"),
                    data[2],
                    position="dodge",
                    color="black",
                    fatten=0,
                    width=0.9,
                ),
                p9.geom_point(
                    p9.aes(y="value", group="fuel"),
                    data[3],
                    position=p9.position_dodge(width=0.9),
                    color="black",
                    size=1,
                    shape="x",
                    fill=None,
                ),
            ]

        return p


def save(options):
    return Fig5(options).save()
