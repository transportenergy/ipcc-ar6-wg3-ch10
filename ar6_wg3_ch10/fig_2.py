import plotnine as p9

from .data import compute_descriptives, normalize_if
from .common import COMMON, figure

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
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank(),),
        p9.guides(color=None),
    ]
)


@figure(region=["World"])
def plot(data, sources, normalize, overshoot, **kwargs):
    # Restore the 'type' dimension to sectoral data
    data["item"]["type"] = data["item"]["variable"].replace(
        {"tkm": "Freight", "pkm": "Passenger"}
    )

    # Transform from individual data points to descriptives
    data["plot"] = (
        data["iam"]
        .pipe(normalize_if, normalize, year=2020)
        .pipe(compute_descriptives, groupby=["type"])
    )

    # Discard 2100 sectoral data
    data["item"] = data["item"][data["item"].year != 2100]

    if normalize:
        # Store the absolute data
        data["item-absolute"] = data["item"]
        # Replace with the normalized data
        data["item"] = data["item"].pipe(normalize_if, normalize, year=2020)

    data["plot-item"] = data["item"].pipe(compute_descriptives, groupby=["type"])

    if normalize:
        scale_y = [p9.scale_y_continuous(minor_breaks=4), p9.expand_limits(y=[0])]
    else:
        scale_y = []

    plot = (
        p9.ggplot(data=data["plot"])
        + STATIC
        # Aesthetics and scales
        + scale_y
        + COMMON["x category"](overshoot)
        + COMMON["color category"](overshoot)
        + COMMON["fill category"](overshoot)
        # Points and bar for sectoral models
        + p9.geom_crossbar(
            p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
            data["plot-item"],
            color="black",
            fatten=0,
            width=None,
        )
        + p9.geom_point(
            p9.aes(y="value"), data["item"], color="black", size=1, shape="x", fill=None
        )
    )

    if normalize:
        # plot += ylim(0, 4)
        plot.units = "Index, 2020 level = 1.0"
    else:
        units = data["iam"]["unit"].str.replace("bn", "10⁹")
        plot.units = "; ".join(units.unique())

    return plot
