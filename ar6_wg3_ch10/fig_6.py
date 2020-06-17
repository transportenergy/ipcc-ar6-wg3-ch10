import pandas as pd
import plotnine as p9

from .data import compute_descriptives, normalize_if
from .common import COMMON, figure

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
        # Variant: 1 band per category
        p9.geom_ribbon(
            p9.aes(ymin="5%", ymax="95%", fill="category"), alpha=0.25, color=None
        ),
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


@figure(region=["World"])
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

    # Variant: bands per category
    data["plot"] = compute_descriptives(data["plot"], on=["type", "mode"])

    plot = (
        p9.ggplot(data=data["plot"])
        + STATIC
        + COMMON["color category"](overshoot)
        # Variant:
        + COMMON["fill category"](overshoot),
    )

    if normalize:
        plot.units = "Index, 2020 level = 1.0"
    else:
        units = data["iam"]["unit"].str.replace("bn", "10⁹")
        plot.units = "; ".join(units.unique())

    return plot
