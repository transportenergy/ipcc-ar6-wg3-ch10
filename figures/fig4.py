import plotnine as p9

from ..data import compute_descriptives, compute_ratio
from .common import COMMON, figure


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
        # Axis labels
        p9.labs(y="", fill="IAM/sectoral scenarios"),
        # Appearance
        COMMON["theme"],
        p9.theme(panel_grid_major_x=p9.element_blank(),),
        p9.guides(color=None),
    ]
)


@figure(region=["World"])
def plot(data, sources, overshoot, **kwargs):
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

    units = sorted(map(str, data["iam"]["unit"].unique()))

    data["plot"] = data["iam"].pipe(compute_descriptives, groupby=["type"])

    # Compute energy intensity for sectoral scenarios
    data["item"] = data["item"].pipe(
        compute_ratio,
        groupby=["type"],
        num="quantity == 'Final Energy'",
        denom="quantity == 'Energy Service'",
    )
    data["plot-item"] = data["item"].pipe(compute_descriptives, groupby=["type"])

    # TODO compute carbon intensity of energy

    plot = (
        p9.ggplot(data=data["plot"])
        + STATIC
        # Aesthetics and scales
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

    plot.units = units

    return plot
