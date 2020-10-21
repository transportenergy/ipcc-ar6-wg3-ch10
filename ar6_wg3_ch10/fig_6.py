import pandas as pd
import plotnine as p9

from .data import compute_descriptives, normalize_if, select_indicator_scenarios
from .common import COMMON, figure
from .util import groupby_multi

# Non-dynamic features of fig_6
STATIC = (
    [
        # Horizontal panels by 'year'
        p9.facet_wrap("type + ' ' + mode", ncol=3, scales="free_y"),
        # Aesthetics and scales
    ]
    + COMMON["x year"]
    + [
        # Geoms
        # # 1 lines per scenario
        # p9.geom_line(p9.aes(y='value', group='model + scenario + category'),
        #           alpha=0.6),
        # 1 band per category
        # p9.geom_ribbon(
        #     p9.aes(ymin="5%", ymax="95%", fill="category"), alpha=0.25, color=None
        # ),
        p9.geom_line(p9.aes(y="5%", color="category"), alpha=0.5, size=0.5),
        p9.geom_line(p9.aes(y="95%", color="category"), alpha=0.5, size=0.5),
        p9.geom_line(p9.aes(y="50%", color="category"), alpha=0.5),
        # Axis labels
        p9.labs(x="", y="", color="IAM/sectoral scenarios"),
        # p9.theme(axis_text_x=p9.element_blank()),
        # Appearance
        COMMON["theme"],
        p9.theme(
            panel_grid_major_x=p9.element_blank(),
            panel_spacing_x=0.4,
            panel_spacing_y=0.05,
        ),
    ]
)


@figure
def plot(data, sources, normalize, overshoot, **kwargs):
    # Add 'All' to the 'mode' column for IAM data
    data["iam"]["mode"] = data["iam"]["mode"].where(~data["iam"]["mode"].isna(), "All")

    # Restore the 'type' dimension to sectoral data
    data["item"]["type"] = data["item"]["variable"].replace(
        {"tkm": "Freight", "pkm": "Passenger"}
    )
    # Convert sectoral 'mode' data to common label
    data["item"] = data["item"].replace(
        {"mode": {"Freight Rail": "Railways", "Passenger Rail": "Railways"}}
    )

    if normalize:
        # Store the absolute data
        data["iam-absolute"] = data["iam"]
        data["item-absolute"] = data["item"]

    # Combine all data to a single data frame; optionally normalize
    data["plot"] = pd.concat([data["iam"], data["item"]], sort=False).pipe(
        normalize_if, normalize, year=2020, drop=False
    )

    # Select indicator scenarios
    data["indicator"] = select_indicator_scenarios(data["plot"])

    data["descriptives"] = compute_descriptives(
        data["plot"], on=["type", "mode"], groupby=["region"]
    )

    title = kwargs["title"]
    if normalize:
        title = title.format(units="Index, 2020 level = 1.0")
    else:
        units = data["iam"]["unit"].str.replace("bn", "10⁹")
        title = title.format(units="; ".join(units.unique()))

    plots = []

    for group, d in groupby_multi(
        (data["descriptives"], data["indicator"]), "region"
    ):
        plots.append(
            p9.ggplot(data=d[0])
            + STATIC
            + COMMON["color category"](overshoot)
            + COMMON["fill category"](overshoot)
            + p9.geom_line(
                p9.aes(x="year", y="value"),
                d[1],
                color="yellow",
            )
            + p9.ggtitle(title.format(group=group))
        )

    return plots
