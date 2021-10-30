import logging

import plotnine as p9

from .common import BW_STAT
from .data import compute_descriptives, normalize_if, unique_units
from .fig_9 import Fig9

log = logging.getLogger(__name__)


class Fig10(Fig9):
    """Direct CO₂ emissions from {mode} (IMO)"""

    def prepare_data(self, data):
        # Discard IAM data
        data.pop("iam")

        # - Drop values that are exactly '0'.
        # - Normalize.
        data["imo"] = (
            data.pop("tem")
            .assign(mode="Maritime")
            .query("value > 0")
            .pipe(normalize_if, self.normalize, year=2020, drop=False)
        )

        data["plot"] = compute_descriptives(
            data["imo"], on=["mode"], groupby=["region"]
        )

        if self.normalize:
            self.units = "Index, 2020 level = 1.0"
        else:
            assert "megametric_ton / year" == unique_units(data["tem"])
            self.units = "Mt / a"

        return data

    def generate(self):
        yield (
            self.plot_bands(
                self.data["plot"],
                self.format_title(mode="shipping"),
                # Select statistics for edges of bands
                *BW_STAT[self.bandwidth]
            )
            + p9.lims(y=(0, 2.25), x=(2020, 2100))
            + p9.scale_color_manual(values=["#0000ff"], limits=["IMO"])
            + p9.scale_fill_manual(values=["#0000ff"], limits=["IMO"])
            + p9.guides(fill=None)
        )
