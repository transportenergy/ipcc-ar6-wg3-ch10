import plotnine as p9

from .data import compute_descriptives, compute_ratio
from .common import COMMON, Figure

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


class Fig4(Figure):
    id = "fig_4"
    title = "Energy intensity of transport"

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

        units = sorted(map(str, data["iam"]["unit"].unique()))
        self.formatted_title = self.formatted_title.format(units=units)

        return data

    def generate(self):
        yield (
            p9.ggplot(data=self.data["plot"])
            + STATIC
            # Aesthetics and scales
            + COMMON["x category"](self.overshoot)
            + COMMON["color category"](self.overshoot)
            + COMMON["fill category"](self.overshoot)
            # Points and bar for sectoral models
            + p9.geom_crossbar(
                p9.aes(ymin="min", y="50%", ymax="max", fill="category"),
                self.data["plot-item"],
                color="black",
                fatten=0,
                width=None,
            )
            + p9.geom_point(
                p9.aes(y="value"),
                self.data["item"],
                color="black",
                size=1,
                shape="x",
                fill=None
            )
        )
