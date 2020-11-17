import logging

import pandas as pd
import plotnine as p9

from .data import compute_descriptives, compute_ratio
from .common import COMMON, Figure, scale_category
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_4
STATIC = (
    [
        # Horizontal panels by freight/passenger
        p9.facet_grid("type ~ year"),
        # Geoms
    ]
    + COMMON["ranges"]
    + [
        COMMON["counts"],
        p9.scale_y_continuous(limits=(0, 0.0045)),
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(
            panel_grid_major_x=p9.element_blank(),
        ),
        p9.guides(color=None),
    ]
)


class Fig4(Figure):
    """Energy intensity of transport

    TODO compute passenger/freight aggregates of sectoral data by mode.

    TODO add emissions intensity computed as:

    - "Emissions|CO2|Energy|Demand|Transportation" divided by
      "Final Energy|Transportation"
    - "Emissions|CO2|Energy|Demand|Transportation|Passenger" divided by
      "Final Energy|Transportation|Passenger"
    - "Emissions|CO2|Energy|Demand|Transportation|Freight" divided by
      "Final Energy|Transportation|Freight"
    """

    title = "Energy intensity of transport — {{group}}"

    # Data preparation
    variables = [
        "Energy Service|Transportation|Freight",
        "Energy Service|Transportation|Passenger",
        "Final Energy|Transportation|Freight",
        "Final Energy|Transportation|Passenger",
    ]
    restore_dims = r"(?P<quantity>[^\|]*)\|Transportation(?:\|(?P<type>.*))?"

    # Plotting
    aspect_ratio = 1.33

    def prepare_data(self, data):
        # Compute energy intensity for IAM scenarios
        data["iam"] = (
            data["iam"]
            .pipe(
                compute_ratio,
                groupby=["type"],
                num="quantity == 'Final Energy'",
                denom="quantity == 'Energy Service'",
            )
            .assign(variable="Energy intensity of transport")
        )

        data["plot"] = compute_descriptives(data["iam"], groupby=["type", "region"])

        # Restore the 'type' dimension to sectoral data
        # TODO "energy": "Passenger" is incorrect; fix
        data["item"]["type"] = data["item"]["variable"].replace(
            {"tkm": "Freight", "pkm": "Passenger", "energy": "Passenger"}
        )
        data["item"]["quantity"] = data["item"]["variable"].replace(
            {"tkm": "Energy Service", "pkm": "Energy Service", "energy": "Final Energy"}
        )
        # Duplicate energy data
        # TODO this is incorrect; fix
        data["item"] = pd.concat(
            [
                data["item"],
                data["item"].query("variable == 'energy'").assign(type="Freight"),
            ]
        )

        # Compute energy intensity for sectoral scenarios
        data["item"] = (
            data["item"]
            .pipe(
                compute_ratio,
                groupby=["type"],
                num="quantity == 'Final Energy'",
                denom="quantity == 'Energy Service'",
            )
            .assign(variable="Energy intensity of transport")
        )
        data["plot-item"] = compute_descriptives(
            data["item"], groupby=["type", "region"]
        )

        # TODO compute carbon intensity of energy

        units = sorted(map(str, data["iam"]["unit"].unique()))
        self.formatted_title = self.formatted_title.format(units=units)

        return data

    def generate(self):
        keys = ["plot", "plot-item", "item"]
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
            + p9.ggtitle(self.formatted_title.format(group=group))
            + STATIC
            # Aesthetics and scales
            + scale_category("x", overshoot=self.overshoot)
            + scale_category("color", overshoot=self.overshoot)
            + scale_category("fill", overshoot=self.overshoot)
        )

        if len(data[1]):
            # Points and bar for sectoral models
            p = p + [
                p9.geom_crossbar(
                    p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
                    self.data["plot-item"],
                    color="black",
                    fatten=0,
                    width=None,
                ),
                p9.geom_point(
                    p9.aes(y="value"),
                    self.data["item"],
                    color="black",
                    size=1,
                    shape="x",
                    fill=None,
                ),
            ]

        return p
