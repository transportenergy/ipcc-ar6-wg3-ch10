import logging

import plotnine as p9

from .data import compute_descriptives, normalize_if, select_indicator_scenarios
from .common import COMMON, Figure
from .util import groupby_multi

log = logging.getLogger(__name__)


# Non-dynamic features of fig_2
STATIC = (
    [
        # Horizontal panels by type; vertical panels by years
        p9.facet_grid("type ~ year", scales="free_y"),
        # Geoms
    ]
    + COMMON["ranges"]
    + [
        COMMON["counts"],
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios", shape="Indicator scenario"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank(),),
        p9.guides(color=None),
    ]
)


class Fig2(Figure):
    id = "fig_2"
    title = "Transport activity — {{group}}"
    caption = """
      Global passenger (billion p-km/yr) and freight (billion t-km/yr) demand
      projections, 2020 index, based on integrated models for selected stabilization
      temperatures by 2100. Also included are global transport models Ref and Policy
      scenarios."""
    normalized_version = True

    # Data preparation
    variables = [
        # "Population",  # for per-capita calculation
        "Energy Service|Transportation|Freight",
        "Energy Service|Transportation|Passenger",
    ]
    restore_dims = r"Energy Service\|Transportation\|(?P<type>Freight|Passenger)"

    # Plotting
    aspect_ratio = 1
    geoms = STATIC

    def prepare_data(self, data):
        # Restore the 'type' dimension to sectoral data
        data["item"]["type"] = data["item"]["variable"].replace(
            {"tkm": "Freight", "pkm": "Passenger"}
        )

        # Normalize
        data["iam"] = normalize_if(data["iam"], self.normalize, year=2020)

        # Select indicator scenarios
        data["indicator"] = select_indicator_scenarios(data["iam"])

        # Transform from individual data points to descriptives
        data["plot"] = compute_descriptives(data["iam"], groupby=["type", "region"])

        # Discard 2100 sectoral data
        data["item"] = data["item"][data["item"].year != 2100]

        if self.normalize:
            # Store the absolute data
            data["item-absolute"] = data["item"]

        # Replace with the normalized data
        data["item"] = normalize_if(data["item"], self.normalize, year=2020)

        data["plot-item"] = compute_descriptives(
            data["item"], groupby=["type", "region"]
        )

        if self.normalize:
            scale_y = [
                p9.scale_y_continuous(limits=(-0.2, 4.8), minor_breaks=4),
                p9.expand_limits(y=[0])
            ]
            units = "Index, 2020 level = 1.0"
        else:
            scale_y = []
            units = "; ".join(data["iam"]["unit"].str.replace("bn", "10⁹").unique())

        self.formatted_title = self.formatted_title.format(units=units)
        self.geoms.extend(scale_y)

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
            + p9.ggtitle(self.formatted_title.format(group=group))
            + self.geoms
            # Aesthetics and scales
            + COMMON["x category"](self.overshoot)
            + COMMON["color category"](self.overshoot)
            + COMMON["fill category"](self.overshoot)
            # Points for indicator scenarios
            + p9.geom_point(
                p9.aes(y="value", shape="scenario"),
                data[1],
                color="cyan",
                size=1,
                fill=None,
            )
        )

        if len(data[2]):
            # Points and bar for sectoral models
            p = p + [
                p9.geom_crossbar(
                    p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
                    data[2],
                    color="black",
                    fatten=0,
                    width=None,
                ),
                p9.geom_point(
                    p9.aes(y="value"),
                    data[3],
                    color="black",
                    size=1,
                    shape="x",
                    fill=None,
                )
            ]

        return p


def save(options):
    return Fig2(options).save()
