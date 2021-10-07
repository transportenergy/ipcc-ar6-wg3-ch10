import logging

import pandas as pd
import plotnine as p9

from .data import compute_descriptives, compute_ratio, normalize_if
from .common import BW_STAT, COMMON, Figure, ranges, scale_category
from .util import groupby_multi

log = logging.getLogger(__name__)


PANEL_VAR = {
    "0": "Passenger energy intensity",
    "1": "Freight energy intensity",
    "2": "Fuel carbon intensity",
}
VAR_PANEL = {v: p for p, v in PANEL_VAR.items()}


class Fig4(Figure):
    """Energy/CO₂ intensity of transport — {region}"""

    has_option = dict(normalize=True)

    # Data preparation
    variables = [
        "Emissions|CO2|Energy|Demand|Transportation",
        "Energy Service|Transportation|Freight",
        "Energy Service|Transportation|Passenger",
        "Final Energy|Transportation",
        "Final Energy|Transportation|Freight",
        "Final Energy|Transportation|Passenger",
    ]
    restore_dims = r"^(?P<quantity>.*)\|Transportation(?:\|(?P<type>.*))?"

    # Plotting
    aspect_ratio = 1.33
    # Non-dynamic features
    geoms = [
        # Horizontal panels by freight/passenger
        p9.facet_grid(
            "panel ~ year", scales="free_y", labeller=lambda v: PANEL_VAR.get(v, v)
        ),
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank()),
        p9.guides(color=None),
    ]

    def prepare_data(self, data):
        # Fill 'type' column in IAM data
        data["iam"] = data["iam"].fillna(dict(type="All"))

        # Restore the 'type' dimension to sectoral data
        data["tem"] = data["tem"].assign(
            type=lambda df: df["variable"]
            .str.replace(r".*\|(Transportation|Freight|Passenger)", r"\1")
            .replace("Transportation", "All"),
            quantity=lambda df: df["variable"].str.replace(
                r"^(.*)\|Transportation(|\|Passenger|\|Freight)$", r"\1"
            ),
            unit=lambda df: df["unit"].replace("PJ/yr", "EJ/yr"),
        )

        # Same calculations for both IAMs and sectoral models
        for key in "iam", "tem":
            # Compute energy intensity
            ei = (
                data[key]
                .pipe(
                    compute_ratio,
                    groupby=["type"],
                    num="quantity == 'Final Energy'",
                    denom="quantity == 'Energy Service'",
                )
                .assign(variable=lambda df: df["type"] + " energy intensity")
            )

            # Compute emissions intensity
            co2i = (
                data[key]
                .query("type == 'All'")
                .pipe(
                    compute_ratio,
                    num="quantity == 'Emissions|CO2|Energy|Demand'",
                    denom="quantity == 'Final Energy'",
                )
                .assign(variable="Fuel carbon intensity")
            )

            tmp = (
                pd.concat([ei, co2i])
                .pipe(normalize_if, self.normalize, year=2020)
                .assign(panel=lambda df: df["variable"].replace(VAR_PANEL))
                .sort_values("panel")
            )

            # Drop erroneous energy intensity values
            threshold = 1.5

            mask = tmp["variable"].str.contains("energy intensity") & (
                tmp["value"] >= threshold
            )
            log.info(
                f"Drop {sum(mask)} / {len(tmp)} energy intensity values >= {threshold}"
            )
            tmp = tmp[~mask]

            if key == "tem" and self.normalize:
                data.update({"tem-abs": data["tem"], "tem": tmp})

            data[f"plot-{key}"] = compute_descriptives(
                tmp, groupby=["type", "region", "panel"]
            )

        if self.normalize:
            # Free scales
            self.units = "Index, 2020 level = 1.0"
        else:
            scale_y = (p9.scale_y_continuous(limits=(0, 0.0045)),)
            self.geoms.append(scale_y)
            self.units = sorted(map(str, data["iam"]["unit"].unique()))

        return data

    def generate(self):
        keys = ["plot-iam", "plot-tem", "tem"]
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
            + scale_category("x", self)
            + scale_category("color", self)
            + scale_category("fill", self)
        )

        if len(data[1]):
            # Points and bar for sectoral models
            # Select statistics for edges of bands
            lo, hi = BW_STAT[self.bandwidth]

            p = p + [
                p9.geom_crossbar(
                    p9.aes(
                        ymin=lo, y="50%", ymax=hi, color="category", fill="category"
                    ),
                    self.data["plot-tem"],
                    fatten=1,
                    width=None,
                ),
                p9.geom_point(
                    p9.aes(y="value"),
                    self.data["tem"],
                    color="black",
                    size=3,
                    shape="_",
                    fill=None,
                ),
            ]

        return p
