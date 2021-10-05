import logging

import numpy as np
import plotnine as p9

from .common import COMMON, SCALE_FUEL, Figure, ranges, scale_category
from .data import (
    aggregate_fuels,
    compute_descriptives,
    compute_shares,
    split_scenarios,
)
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_5
STATIC = [
    # Horizontal panels by 'year'
    p9.facet_wrap("year", nrow=3),
    # Aesthetics and scales
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
    # Like COMMON['counts'], except color is 'fuel'
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
    p9.theme(panel_grid_major_x=p9.element_blank()),
]


class Fig5(Figure):
    """Fuel shares of transport final energy — {region}

    Based on integrated models grouped by CO2eq concentration levels by 2100 and
    compared with sectoral models (grouped by baseline and policies) in 2050. Box plots
    show minimum/maximum, 25th/75th percentile and median. Numbers above each bar
    represent the # of scenarios.
    """

    # Data preparation
    variables = [
        # The following include all Final Energy|Transportation|* variables except
        # those with "Freight" or "Passenger" as the third element.
        #
        # Denominator in shares
        "Final Energy|Transportation",
        #
        # aggregate_fuels() preserves these values
        "Final Energy|Transportation|Electricity",
        "Final Energy|Transportation|Gases",
        "Final Energy|Transportation|Hydrogen",
        "Final Energy|Transportation|Liquids|Oil",
        # aggregate_fuels() sums these as "Biofuels"
        "Final Energy|Transportation|Liquids|Bioenergy",
        "Final Energy|Transportation|Liquids|Biomass",
        # aggregate_fuels() sums these as "Other"
        "Final Energy|Transportation|Liquids|Coal",
        "Final Energy|Transportation|Liquids|Fossil synfuel",
        "Final Energy|Transportation|Liquids|Gas",
        "Final Energy|Transportation|Liquids|Natural Gas",
        "Final Energy|Transportation|Solar",
        "Final Energy|Transportation|Solids|Biomass",
        "Final Energy|Transportation|Solids|Coal",
        #
        # Other variables that appear in the template, but are not plotted:
        # # Not used because subsets are aggregated differently
        # "Final Energy|Transportation|Liquids",
        # # Distinct categorizations & partial sums
        # "Final Energy|Transportation|Fossil",
        # "Final Energy|Transportation|Heat",
        # # Omitted
        # "Final Energy|Transportation|Gases|Bioenergy",
        # "Final Energy|Transportation|Gases|Fossil",
        # "Final Energy|Transportation|Geothermal",
    ]
    restore_dims = r"Final Energy\|Transportation(?:\|(?P<fuel>.*))?"

    # Plotting
    geoms = STATIC
    aspect_ratio = 2
    units = "share"

    def prepare_data(self, data):
        # Compute fuel shares by type for IAM scenarios
        data["iam-raw"] = data["iam"].copy()

        data["iam"] = (
            data["iam"]
            .pipe(aggregate_fuels)
            .pipe(compute_shares, on="fuel", groupby=["region"])
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
            .pipe(aggregate_fuels)
            .pipe(compute_shares, on="fuel", groupby=["region"])
            .assign(variable="Fuel share")
        )

        # Discard 2020 data
        data["iam"] = data["iam"][data["iam"].year != 2020]
        data["item"] = data["item"][data["item"].year != 2020]

        # Select indicator scenarios
        data["indicator"], _ = split_scenarios(data["iam"], groups=["indicator"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(data["iam"], groupby=["fuel", "region"])
        data["plot-item"] = compute_descriptives(
            data["item"], groupby=["fuel", "region"]
        )

        return data

    def generate(self):
        keys = ["plot", "indicator", "plot-item", "item"]
        for region, d in groupby_multi([self.data[k] for k in keys], "region"):
            log.info(f"Region: {region}")
            yield self.plot_single(d, self.format_title(region=region))

    def plot_single(self, data, title):
        # Base plot
        p = (
            p9.ggplot(data=data[0])
            + title
            + self.geoms
            # Geoms, aesthetics, and scales that respond to options
            + ranges(self, aes="fuel", counts=False, position="dodge", width=0.9)
            + scale_category("x", self, short_label=True)
        )

        if len(data[1]):
            # Points for indicator scenarios
            p = (
                p
                + p9.geom_point(
                    p9.aes(y="value", shape="scenario", group="fuel"),
                    data[1],
                    position=p9.position_dodge(width=0.9),
                    color="magenta",
                    size=2,
                    fill=None,
                )
                + COMMON["shape ip"]
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
