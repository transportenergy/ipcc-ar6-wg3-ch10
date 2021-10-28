import logging

import plotnine as p9

from .common import Figure
from .data import unique_units

log = logging.getLogger(__name__)


class Fig9(Figure):
    """Direct transport CO₂ emissions from aviation"""

    has_option = dict(normalize=True)

    # Data preparation
    years = list(range(2020, 2100 + 1, 5))
    variables = [
        "Emissions|CO2|Energy|Demand|Transportation|Aviation",
        # "Emissions|CO2|Energy|Demand|Transportation|Aviation|Freight",
        # "Emissions|CO2|Energy|Demand|Transportation|Aviation|Passenger",
    ]

    def prepare_data(self, data):
        # Discard G-/NTEM data
        data.pop("tem")

        # Use "{model name} {scenario name}" to label lines
        data["iam"] = data["iam"].assign(
            label=lambda df: df["model"] + " " + df["scenario"]
        )

        assert "megametric_ton / year" == unique_units(data["iam"])
        self.units = "Mt / a"

        return data

    def generate(self):
        yield (
            p9.ggplot(p9.aes(x="year", y="value", color="label"), self.data["iam"])
            + p9.geom_line()
            + self.format_title()
            + p9.labs(x="", y="", color="Model / scenario")
        )
