"""Variant of Fig5 to diaggregate by type (freight / passenger).

This file is substantially similar to fig_5.py, so a violation of DRY (“don't repeat
yourself”). However, as this is a rough discussion item for the benefit of the author
team, it is kept separate to avoid disturbing Figure 5, which in contrast is to appear
in the report.
"""
import logging

import pandas as pd
import plotnine as p9

from .common import Figure
from .data import (
    aggregate_fuels,
    compute_descriptives,
    compute_shares,
    select_indicator_scenarios,
)
from .fig_5 import STATIC
from .util import groupby_multi

log = logging.getLogger(__name__)


class Fig7(Figure):
    """Fuel shares of transport final energy — {type} — {region}

    Based on integrated models grouped by CO2eq concentration levels by 2100 and
    compared with sectoral models (grouped by baseline and policies) in 2050. Box plots
    show minimum/maximum, 25th/75th percentile and median. Numbers above each bar
    represent the # of scenarios.
    """

    # Data preparation
    variables = [
        # The following include only a subset of Final Energy|Transportation| variables
        # where the third element is "Freight" or "Passenger".
        # Denominator in shares
        "Final Energy|Transportation|Freight",
        "Final Energy|Transportation|Freight|Electricity",
        "Final Energy|Transportation|Freight|Gases",
        "Final Energy|Transportation|Freight|Hydrogen",
        "Final Energy|Transportation|Freight|Liquids|Bioenergy",
        "Final Energy|Transportation|Freight|Liquids|Biomass",
        "Final Energy|Transportation|Freight|Liquids|Fossil synfuel",
        "Final Energy|Transportation|Freight|Liquids|Oil",
        "Final Energy|Transportation|Freight|Other",
        "Final Energy|Transportation|Passenger",
        "Final Energy|Transportation|Passenger|Electricity",
        "Final Energy|Transportation|Passenger|Gases",
        "Final Energy|Transportation|Passenger|Hydrogen",
        "Final Energy|Transportation|Passenger|Liquids|Bioenergy",
        "Final Energy|Transportation|Passenger|Liquids|Biomass",
        "Final Energy|Transportation|Passenger|Liquids|Fossil synfuel",
        "Final Energy|Transportation|Passenger|Liquids|Oil",
        "Final Energy|Transportation|Passenger|Other",
    ]
    restore_dims = r"Final Energy\|Transportation\|(?P<type>[^\|]*)(?:\|(?P<fuel>.*))?"

    # Plotting
    geoms = STATIC
    aspect_ratio = 2
    units = "share"

    def prepare_data(self, data):
        # Compute fuel shares by type for IAM scenarios
        data["iam-raw"] = data["iam"].copy()

        data["iam"] = (
            data["iam"]
            .pipe(aggregate_fuels, groupby=["type"])
            .pipe(compute_shares, on="fuel", groupby=["region", "type"])
            .assign(variable="Fuel share")
        )

        # Compute fuel shares for sectoral scenarios
        # - Modify labels to match IAM format
        data["item"] = pd.DataFrame(columns=data["iam"].columns)

        # Discard 2020 data
        data["iam"] = data["iam"][data["iam"].year != 2020]
        # data["item"] = data["item"][data["item"].year != 2020]

        # Select indicator scenarios
        data["indicator"] = select_indicator_scenarios(data["iam"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(
            data["iam"], groupby=["fuel", "region", "type"]
        )

        return data

    def generate(self):
        keys = ["plot", "indicator"]
        for group, d in groupby_multi([self.data[k] for k in keys], ["type", "region"]):
            if len(d[0]) == 0:
                log.info(f"Skip {group}; no IAM data")
                continue

            log.info(f"Type, region: {group}")

            yield self.plot_single(d, self.format_title(type=group[0], region=group[1]))

    def plot_single(self, data, title):
        # Base plot
        p = p9.ggplot(data=data[0]) + title + self.geoms

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

        return p
