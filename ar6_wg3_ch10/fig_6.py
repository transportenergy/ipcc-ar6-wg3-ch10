import logging

import pandas as pd
import plotnine as p9

from .data import (
    compute_descriptives,
    normalize_if,
    per_capita_if,
    split_scenarios,
)
from .common import BW_STAT, COMMON, Figure, scale_category
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_6
STATIC = (
    [
        # Horizontal panels by 'year'
        p9.facet_wrap("type + ' ' + mode", ncol=3, scales="free_y"),
        # Aesthetics and scales
    ]
    + COMMON["x year"]
    + [
        # Axis labels
        p9.labs(x="", y="", fill="Category"),
        #
        # Appearance
        COMMON["theme"],
        p9.guides(color=None),
        p9.theme(
            axis_text=p9.element_text(size=7),
            panel_grid=p9.element_line(color="#dddddd", size=0.2),
            panel_spacing_x=0.4,
            panel_spacing_y=0.05,
            strip_text=p9.element_text(size=7),
        ),
    ]
)


class Fig6(Figure):
    """Transport activity by mode — {region}"""

    has_option = dict(normalize=True, per_capita=True)

    years = list(range(2020, 2100 + 1, 10))
    variables = [
        "Energy Service|Transportation|Aviation",
        "Energy Service|Transportation|Freight",
        "Energy Service|Transportation|Freight|Aviation",
        "Energy Service|Transportation|Freight|International Shipping",
        "Energy Service|Transportation|Freight|Navigation",
        "Energy Service|Transportation|Freight|Other",
        "Energy Service|Transportation|Freight|Railways",
        "Energy Service|Transportation|Freight|Road",
        "Energy Service|Transportation|Navigation",
        "Energy Service|Transportation|Passenger",
        "Energy Service|Transportation|Passenger|Aviation",
        "Energy Service|Transportation|Passenger|Bicycling and Walking",
        "Energy Service|Transportation|Passenger|Navigation",
        "Energy Service|Transportation|Passenger|Other",
        "Energy Service|Transportation|Passenger|Railways",
        "Energy Service|Transportation|Passenger|Road",
        "Energy Service|Transportation|Passenger|Road|2W and 3W",
        "Energy Service|Transportation|Passenger|Road|Bus",
        "Energy Service|Transportation|Passenger|Road|LDV",
    ]
    restore_dims = (
        r"Energy Service\|Transportation\|"
        r"(?P<type>Freight|Passenger)(?:\|(?P<mode>.*))?"
    )

    bandwidth_default = 8

    # Plotting
    aspect_ratio = 1
    geoms = STATIC

    def prepare_data(self, data):
        replace_mode = dict(
            mode={
                "2W and 3W": "Road: 2/3W",
                "Bus": "Road: Bus",
                "Freight Rail": "Rail",
                "HDT": "Road: HDT",
                "Passenger Rail": "Rail",
                "Railways": "Rail",
                "Road|2W and 3W": "Road: 2/3W",
                "Road|Bus": "Road: Bus",
                "Road|LDV": "Road: LDV",
            }
        )

        # - Add 'All' to the 'mode' column for IAM data
        # - Remove "Road|" from 'mode' labels
        data["iam"] = data["iam"].fillna(dict(mode="All")).replace(replace_mode)

        # Restore the 'type' dimension to sectoral data
        # Convert sectoral 'mode' data to common label
        data["tem"] = (
            data["tem"]
            .fillna(dict(mode="All"))
            .assign(
                variable=lambda df: df["variable"].str.replace(
                    r"Energy Service\|Transportation\|([^\|]*).*",
                    r"\1",
                ),
                type=lambda df: df["variable"],
            )
            .replace(replace_mode)
        )

        if self.normalize:
            # Store the absolute data
            data["iam-absolute"] = data["iam"]
            data["tem-absolute"] = data["tem"]

        # Combine all data to a single data frame; optionally normalize
        data["plot"] = (
            pd.concat([data["iam"], data["tem"]], sort=False)
            .pipe(
                per_capita_if,
                data["population"],
                self.per_capita,
                groupby=["type", "mode"],
            )
            .pipe(normalize_if, self.normalize, year=2020, drop=False)
        )

        # Select IPs
        data["ip"], _ = split_scenarios(data["plot"], groups=["indicator"])

        data["descriptives"] = compute_descriptives(
            data["plot"], on=["type", "mode"], groupby=["region"]
        )

        if self.normalize:
            self.units = "Index, 2020 level = 1.0"
        else:
            self.units = "; ".join(
                data["iam"]["unit"].str.replace("bn", "10⁹").unique()
            )

        return data

    def generate(self):
        # Select statistics for edges of bands
        lo, hi = BW_STAT[self.bandwidth]

        for region, d in groupby_multi(
            (self.data["descriptives"], self.data["ip"]), "region"
        ):
            log.info(f"Region: {region}")
            yield (
                p9.ggplot(data=d[0])
                + self.format_title(region=region)
                + self.geoms
                + [
                    # commented: 1 line per scenario
                    # p9.geom_line(
                    #     p9.aes(y='value', group='model + scenario + category'),
                    #     alpha=0.6
                    # ),
                    # 1 band per category
                    p9.geom_ribbon(
                        p9.aes(ymin=lo, ymax=hi, fill="category"), alpha=0.2, color=None
                    ),
                    # Median and edge lines
                    p9.geom_line(p9.aes(y="50%", color="category"), alpha=1, size=0.2),
                    p9.geom_line(p9.aes(y=lo, color="category"), alpha=1, size=0.1),
                    p9.geom_line(p9.aes(y=hi, color="category"), alpha=1, size=0.1),
                ]
                + scale_category("color", self)
                + scale_category("fill", self)
                # + p9.geom_line(p9.aes(x="year", y="value"), d[1], color="yellow")
            )
