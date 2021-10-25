"""Variant of fig_5 with type/service (freight / passenger) dimension."""
import logging

import pandas as pd
import plotnine as p9

from .common import COMMON, Figure, ranges, scale_category
from .data import (
    aggregate_fuels,
    compute_descriptives,
    compute_shares,
    split_scenarios,
)
from .fig_5 import STATIC
from .util import groupby_multi

log = logging.getLogger(__name__)


class Fig7(Figure):
    """Fuel shares of transport final energy by service — {region}

    Based on integrated models grouped by CO2eq concentration levels by 2100 and
    compared with sectoral models (grouped by baseline and policies) in 2050. Box plots
    show full bandwidth (according to the option: either min/max, 5/95th, or 10/90th
    precentiles), 25/75th percentiles, and median. Marks show illustrative pathways.
    Numbers above each bar represent the # of scenarios.
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
    aspect_ratio = 1
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

        # Filter erroneous data, e.g. from model "WITCH 5.0", with high hydrogen fuel
        # share. These result from erroneous high absolute values (tentatively,
        # overstated by a factor of ~10³) for energy from this fuel only.
        h2_max = 0.99
        mask = data["iam"].eval(f"fuel == 'Hydrogen' and value > {h2_max}")
        log.info(f"Discard {mask.sum()} obs in which hydrogen fuel share is > {h2_max}")
        # Include in the data dump
        data["h2-debug"] = data["iam"][mask]
        # Remove from the plotted data
        data["iam"] = data["iam"][~mask]

        # NB G-/NTEM data are discarded here, since they do not have the 'type'
        # (freight, passenger) dimension necessary to appear in this plot
        data["tem"] = pd.DataFrame(columns=data["iam"].columns)

        # (Here we would compute fuel shares for sectoral scenarios, if data existed.)

        # Discard 2020 data
        data["iam"] = data["iam"][data["iam"].year != 2020]
        # data["tem"] = data["tem"][data["tem"].year != 2020]

        # Select IPs
        data["ip"], _ = split_scenarios(data["iam"], groups=["indicator"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(
            data["iam"], groupby=["fuel", "region", "type"]
        )

        return data

    def generate(self):
        keys = ["plot", "ip"]
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
            + scale_category("x", self, short_label=True, without_tem=True)
        )

        if len(data[1]):
            # Points for IPs
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

        return p
