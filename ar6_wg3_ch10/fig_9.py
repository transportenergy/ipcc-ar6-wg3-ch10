import logging

import plotnine as p9

from .common import BW_STAT, Figure, scale_category
from .data import compute_descriptives, normalize_if, unique_units

log = logging.getLogger(__name__)


class Fig9(Figure):
    """Direct transport CO₂ emissions from {mode}"""

    has_option = dict(normalize=True)

    # Data preparation

    # Version 'A': use all periods
    # years = list(range(2020, 2100 + 1, 5))
    # Version 'B': use only periods on decade boundaries, for consistent coverage
    years = list(range(2020, 2100 + 1, 10))

    variables = [
        "Emissions|CO2|Energy|Demand|Transportation|Aviation",
        "Emissions|CO2|Energy|Demand|Transportation|Maritime",
        #
        # Omitted: do not plot by service (pax/freight). This may omit scenarios which
        # have submitted data for these variables but not their totals, above.
        # "Emissions|CO2|Energy|Demand|Transportation|Aviation|Freight",
        # "Emissions|CO2|Energy|Demand|Transportation|Aviation|Passenger",
        # "Emissions|CO2|Energy|Demand|Transportation|Maritime|Freight",
        # "Emissions|CO2|Energy|Demand|Transportation|Maritime|Passenger",
    ]
    restore_dims = r"Emissions\|CO2\|Energy\|Demand\|Transportation\|(?P<mode>.*)"

    def prepare_data(self, data):
        # Discard G-/NTEM data
        data.pop("tem")

        # - Drop values that are exactly '0'.
        # - Use "{model name} {scenario name}" to label lines (for version 'A').
        # - Drop high-side outliers.
        #   TODO reimplement as > median + 1.5 × IQR.
        # - Normalize.
        data["iam"] = (
            data["iam"]
            .query("value > 0")
            .assign(label=lambda df: df["model"] + " " + df["scenario"])
            .query("label != 'IMAGE 3.2 SSP5-baseline'")
            .pipe(normalize_if, self.normalize, year=2020, drop=False)
        )

        data["plot"] = compute_descriptives(
            data["iam"], on=["mode"], groupby=["region"]
        )

        if self.normalize:
            self.units = "Index, 2020 level = 1.0"
        else:
            assert "megametric_ton / year" == unique_units(data["iam"])
            self.units = "Mt / a"

        return data

    def generate(self):
        for mode, data in self.data["plot"].groupby("mode"):
            yield self.plot_single(
                data,
                self.format_title(
                    mode="shipping" if mode == "Maritime" else mode.lower()
                ),
                # Select statistics for edges of bands
                *BW_STAT[self.bandwidth]
            )

    def plot_single(self, data, title, lo, hi):
        return (
            #
            # Version 'A' with 1 line per (model, scenario)
            # p9.ggplot(
            #     p9.aes(x="year", y="value", color="label"),
            #     self.data["iam"],
            # )
            # + p9.geom_line()
            #
            # Version 'B' with bands by climate outcome category
            p9.ggplot(p9.aes(x="year", color="category", fill="category"), data)
            # 1 band per category
            + p9.geom_ribbon(
                p9.aes(ymin=lo, ymax=hi, fill="category"), alpha=0.2, color=None
            )
            # Median and edge lines
            + p9.geom_line(p9.aes(y="50%", color="category"), alpha=1, size=0.2)
            + p9.geom_line(p9.aes(y=lo, color="category"), alpha=1, size=0.1)
            + p9.geom_line(p9.aes(y=hi, color="category"), alpha=1, size=0.1)
            + scale_category("color", self, without_tem=True)
            + scale_category("fill", self, without_tem=True)
            #
            # Common / appearance
            + title
            + p9.guides(color=None)
            + p9.labs(x="", y="", fill="Model / scenario")
        )
