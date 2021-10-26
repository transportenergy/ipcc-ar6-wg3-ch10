import logging
from functools import lru_cache

import plotnine as p9

from .data import aggregate_fuels, normalize_if, split_scenarios
from .common import SCALE_FUEL, SCENARIOS, Figure
from .fig_1 import Fig1
from .fig_5 import Fig5

log = logging.getLogger(__name__)


class Fig8(Figure):
    """Data for an IP box figure.

    This figure (for now) is not plotted by the code in this file; only the data is
    extracted and dumped.
    """

    has_option = dict(normalize=True)

    # Data preparation
    variables = Fig1.variables + Fig5.variables
    restore_dims = Fig5.restore_dims

    def prepare_data(self, data):
        # Discard G-/NTEM data
        data.pop("tem")

        # Select illustrative pathways data only
        data["ip"], _ = split_scenarios(data.pop("iam"), groups=["indicator"])

        @lru_cache()
        def id_for_scenario(name):
            """Return the IP identifier/label given a scenario `name`.

            Model names are ignored, since the scenario name uniquely identifies.
            """
            for s in SCENARIOS["indicator"]:
                if s["scenario"] == name:
                    return s["id"]

        data["ip"]["id"] = data["ip"]["scenario"].apply(id_for_scenario)

        # Mask to split emissions and energy data
        mask = data["ip"]["variable"].str.contains("Emissions")

        # Emissions in energy units
        data["emi-abs"] = data["ip"][mask]
        # Emissions normalized to 2020
        data["emi"] = data["emi-abs"].pipe(
            normalize_if, self.normalize, year=2020, drop=False
        )

        # - Aggregate energy by fuels
        # - Drop the total
        data["energy"] = (
            data["ip"][~mask]
            .pipe(aggregate_fuels, groupby=["id"])
            .query("variable != 'Final Energy|Transportation'")
        )

        return data

    def generate(self):
        yield self.plot_emi(self.data["emi"])
        for ip, data in self.data["energy"].groupby(["id"]):
            yield self.plot_energy_single(ip, data)

    def plot_emi(self, data):
        return (
            p9.ggplot(p9.aes(x="year", y="value", color="id"), data)
            + p9.geom_line()
            + p9.labs(x="", y="", color="Illustrative pathway")
            + p9.ggtitle("CO₂ emissions from transport [Index, 2020 level = 1.0]")
        )

    def plot_energy_single(self, ip_id, data):
        return (
            p9.ggplot(p9.aes(x="year", y="value", fill="fuel"), data)
            + p9.geom_area()
            + p9.scale_fill_manual(
                limits=SCALE_FUEL["limit"],
                values=SCALE_FUEL["fill"],
                labels=SCALE_FUEL["label"],
            )
            + p9.ylim(-10, 175)
            + p9.labs(x="", y="", fill="Fuel")
            + p9.ggtitle(f"Transport final energy [EJ / year] — {ip_id}")
        )
