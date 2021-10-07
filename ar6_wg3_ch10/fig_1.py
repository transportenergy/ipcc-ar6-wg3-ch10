import logging

import plotnine as p9

from .data import (
    compute_descriptives,
    normalize_if,
    per_capita_if,
    split_scenarios,
    unique_units,
)
from .common import BW_STAT, COMMON, Figure, ranges, scale_category, scale_y_clip
from .util import groupby_multi

log = logging.getLogger(__name__)


class Fig1(Figure):
    """Direct transport CO₂ emissions — {region}

    IAM results are grouped by temperature targets. Sectoral studies are grouped by
    baseline and policy categories because they don’t track global emissions so cannot
    solve for achieving temperature targets. Numbers above the bars indicate the number
    of scenarios.

    Sources: IAMs —IPCC WGIII AR6 Scenario Database (Annex II.10). Sectoral models:
    MoMo (IEA), EPPA5 (MIT), Roadmap (ICCT), GCAM (PNNL), and MESSAGE (IIASA). The
    policy scenarios in global transport models (GTMs) cover a wide range of “non-BAU”
    scenarios (to be defined) that are not necessarily designed to achieve the targets
    set in the Paris Agreements.
    """

    has_option = dict(normalize=True, per_capita=True)

    # Data preparation
    variables = ["Emissions|CO2|Energy|Demand|Transportation"]

    # Plotting
    aspect_ratio = 0.75
    # Non-dynamic features of fig_1
    geoms = [
        # Horizontal panels by the years shown
        p9.facet_wrap("year", ncol=4),
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank()),
        p9.guides(color=None),
    ]

    def prepare_data(self, data):
        data["iam"] = (
            data["iam"]
            .pipe(per_capita_if, data["population"], self.per_capita)
            .pipe(normalize_if, self.normalize, year=2020)
        )

        # Select indicator scenarios
        data["ip"], _ = split_scenarios(data["iam"], groups=["indicator"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(data["iam"], groupby=["region"])

        # Discard 2100 G-/NTEM data
        data["tem"] = data["tem"].query("year in [2020, 2030, 2050]")

        if self.normalize:
            # Store the absolute data
            data["tem-absolute"] = data["tem"]

        data["tem"] = (
            data["tem"]
            .pipe(per_capita_if, data["population"], self.per_capita)
            .pipe(normalize_if, self.normalize, year=2020)
        )

        data["plot-tem"] = compute_descriptives(data["tem"], groupby=["region"])

        # Set the y scale
        if self.normalize:
            scale_y = scale_y_clip(
                limits=(-0.5, 2.5), minor_breaks=4, expand=(0, 0, 0, 0.08)
            )
            self.units = "Index, 2020 level = 1.0"
        elif self.per_capita:
            scale_y = scale_y_clip(limits=(-1, 5), minor_breaks=3)
            self.units = unique_units(data["iam"])
        else:
            # NB if this figure is re-added to the text, re-check this scale
            scale_y = scale_y_clip(limits=(-5000, 20000))
            self.units = unique_units(data["iam"])

        self.geoms.append(scale_y)

        return data

    def generate(self):
        keys = ["plot", "ip", "plot-tem", "tem"]
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
            + ranges(self)
            + scale_category("x", self, short_label=True)
            + scale_category("color", self)
            + scale_category("fill", self)
        )

        if len(data[1]):
            # Points for IPs
            p = (
                p
                + p9.geom_point(
                    p9.aes(y="value", shape="scenario"),
                    data[1],
                    color="magenta",
                    size=2,
                    fill=None,
                )
                + COMMON["shape ip"]
            )

        if len(data[2]):
            # Points and bar for sectoral models
            # Select statistics for edges of bands
            lo, hi = BW_STAT[self.bandwidth]

            p = p + [
                p9.geom_crossbar(
                    p9.aes(
                        ymin=lo, y="50%", ymax=hi, color="category", fill="category"
                    ),
                    data[2],
                    fatten=1,
                    width=None,
                ),
                p9.geom_point(
                    p9.aes(y="value"),
                    data[3],
                    color="black",
                    size=3,
                    shape="_",
                    fill=None,
                ),
                # Counts: disabled
                # p9.geom_text(
                #     p9.aes(label="count", y="max"),
                #     data[2],
                #     color="black",
                #     format_string="{:.0f}",
                #     va="bottom",
                #     size=7,
                # ),
            ]

        return p
