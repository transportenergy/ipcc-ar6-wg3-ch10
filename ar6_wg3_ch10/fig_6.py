import logging

import pandas as pd
import plotnine as p9

from .data import (
    compute_descriptives,
    normalize_if,
    per_capita_if,
    select_indicator_scenarios,
)
from .common import COMMON, Figure, scale_category
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

    all_years = True
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

    # Plotting
    aspect_ratio = 1
    geoms = STATIC

    def prepare_data(self, data):
        # Drop years 2095, 2085, etc. for which only a subset of scenarios include data
        years_to_drop = [y for y in data["iam"]["year"].unique() if y % 10 != 0]
        data["iam"] = data["iam"][~data["iam"]["year"].isin(years_to_drop)]

        # Drop data with no climate assessment; these contain erroneous high values
        data["iam"] = data["iam"][~(data["iam"]["category"] == "no-climate-assessment")]

        # Add 'All' to the 'mode' column for IAM data
        data["iam"]["mode"] = data["iam"]["mode"].where(
            ~data["iam"]["mode"].isna(), "All"
        )

        # Restore the 'type' dimension to sectoral data
        data["item"]["type"] = data["item"]["variable"].replace(
            {"tkm": "Freight", "pkm": "Passenger"}
        )
        # Convert sectoral 'mode' data to common label
        data["item"] = data["item"].replace(
            {"mode": {"Freight Rail": "Railways", "Passenger Rail": "Railways"}}
        )

        if self.normalize:
            # Store the absolute data
            data["iam-absolute"] = data["iam"]
            data["item-absolute"] = data["item"]

        # Combine all data to a single data frame; optionally normalize
        data["plot"] = (
            pd.concat([data["iam"], data["item"]], sort=False)
            .pipe(
                per_capita_if,
                data["population"],
                self.per_capita,
                groupby=["type", "mode"],
            )
            .pipe(normalize_if, self.normalize, year=2020, drop=False)
        )

        # Select indicator scenarios
        data["indicator"] = select_indicator_scenarios(data["plot"])

        data["descriptives"] = compute_descriptives(
            data["plot"], on=["type", "mode"], groupby=["region"]
        )

        if self.normalize:
            self.units = "Index, 2020 level = 1.0"
        else:
            self.units = "; ".join(
                data["iam"]["unit"].str.replace("bn", "10⁹").unique()
            )

        # Adjust filename to reflect bandwidth
        fn_parts = self.base_fn.split("-", maxsplit=1)
        self.base_fn = "-".join([fn_parts[0], f"bw{self.bandwidth}", fn_parts[1]])

        # Select statistics for edges of bands
        lo, hi = {5: ("25%", "75%"), 8: ("10%", "90%"), 9: ("5%", "95%")}[
            self.bandwidth
        ]

        self.geoms.extend(
            [
                # # 1 lines per scenario
                # p9.geom_line(p9.aes(y='value', group='model + scenario + category'),
                #           alpha=0.6),
                #
                # 1 band per category
                p9.geom_ribbon(
                    p9.aes(ymin=lo, ymax=hi, fill="category"), alpha=0.2, color=None
                ),
                # Median and edge lines
                p9.geom_line(p9.aes(y="50%", color="category"), alpha=1, size=0.2),
                p9.geom_line(p9.aes(y=lo, color="category"), alpha=1, size=0.1),
                p9.geom_line(p9.aes(y=hi, color="category"), alpha=1, size=0.1),
            ]
        )

        return data

    def generate(self):
        for region, d in groupby_multi(
            (self.data["descriptives"], self.data["indicator"]), "region"
        ):
            yield (
                p9.ggplot(data=d[0])
                + self.format_title(region=region)
                + self.geoms
                + scale_category("color", self)
                + scale_category("fill", self)
                # + p9.geom_line(
                #     p9.aes(x="year", y="value"),
                #     d[1],
                #     color="yellow",
                # )
            )
