import logging
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
import plotnine as p9
import yaml

from .data import get_data, restore_dims

log = logging.getLogger(f"root.{__name__}")

# Matplotlib style
mpl.rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})


OUTPUT_PATH = Path("output")

YEARS = [2020, 2030, 2050, 2100]

INFO = yaml.safe_load(open(Path(__file__).parents[1] / "data" / "figures.yaml"))

# Scale for scenario categories
SCALE_CAT = pd.DataFrame(
    [
        # # Earlier categorization
        # ["Below 1.6C", "green", "green", "<1.6°C"],
        # ["1.6 - 2.0C", "#fca503", "#fca503", "1.6–2°C"],
        # ["2.0 - 2.5C", "#ca34de", "#ca34de", "2–2.5°C"],
        # ["2.5 - 3.5C", "red", "red", "2.5–3.5°C"],
        # ["Above 3.5C", "brown", "brown", ">3.5°C"],

        # Current categorization
        ["C2: 1.5°C with high OS", "green", "green", "1.5°C"],
        ["C3: lower 2°C", "#fca503", "#fca503", "low 2°C"],
        ["C4: higher 2°C", "#fe5302", "#fe5302", "hi 2°C"],
        ["C5: below 2.5°C", "red", "red", "<2.5°C"],
        ["C6: below 3.0°C", "brown", "brown", "<3.0°C"],
        ["C7: above 3.0°C", "purple", "purple", ">3.0°C"],

        # Sectoral scenarios
        ["policy", "#eeeeee", "#999999", "Policy"],
        ["reference", "#999999", "#111111", "Reference"],
    ],
    columns=["limit", "fill", "color", "label"],
)

# Same, with overshoot
SCALE_CAT_OS = pd.concat(
    [
        SCALE_CAT.loc[:0, :],
        pd.DataFrame(
            [["Below 1.6C OS", "green", "green", "<1.6°C*"]],
            columns=["limit", "fill", "color", "label"],
        ),
        SCALE_CAT.loc[1:, :],
    ],
    ignore_index=True,
)


SCALE_FUEL = pd.DataFrame(
    [
        ["Liquids|Oil", "#f7a800", "Oil"],
        ["Liquids|Biomass", "#de4911", "Biofuels"],
        ["Gases", "#9e2b18", "Gas"],
        ["Electricity", "#9fca71", "Electricity"],
        ["Hydrogen", "#59a431", "Hydrogen"],
    ],
    columns=["limit", "fill", "label"],
)


# Common plot components.

COMMON = {
    # Ranges of data as vertical bars
    "ranges": [
        p9.geom_crossbar(
            p9.aes(ymin="min", y="50%", ymax="max"),
            color="black",
            fill="white",
            width=None,
        ),
        p9.geom_crossbar(
            p9.aes(ymin="25%", y="50%", ymax="75%", fill="category"),
            color="black",
            width=None,
        ),
    ],
    "theme": p9.theme(
        # Background colours
        panel_background=p9.element_rect(fill="#fef6e6"),
        strip_background=p9.element_rect(fill="#fef6e6"),
        strip_text=p9.element_text(weight="bold"),
        # Y-axis grid lines
        panel_grid_major_y=p9.element_line(color="#bbbbbb"),
        panel_grid_minor_y=p9.element_line(color="#eeeeee", size=0.1),
    ),
    # Labels with group counts
    "counts": p9.geom_text(
        p9.aes(label="count", y="max", color="category"),
        format_string="{:.0f}",
        va="bottom",
        size=7,
    ),
    # Scales
    "x category": lambda os: [
        p9.aes(x="category"),
        p9.scale_x_discrete(
            limits=(SCALE_CAT_OS if os else SCALE_CAT)["limit"],
            labels=(SCALE_CAT_OS if os else SCALE_CAT)["label"],
            drop=True,
        ),
        p9.labs(x=""),
        p9.theme(axis_text_x=p9.element_blank()),
    ],
    "fill category": lambda os: p9.scale_fill_manual(
        limits=(SCALE_CAT_OS if os else SCALE_CAT)["limit"],
        values=(SCALE_CAT_OS if os else SCALE_CAT)["fill"],
        drop=True,
    ),
    "color category": lambda os: [
        p9.aes(color="category"),
        p9.scale_color_manual(
            limits=(SCALE_CAT_OS if os else SCALE_CAT)["limit"],
            values=(SCALE_CAT_OS if os else SCALE_CAT)["color"],
            drop=True,
        ),
    ],
    "x year": [
        p9.aes(x="year"),
        p9.scale_x_continuous(
            limits=(2020, 2100),
            breaks=np.linspace(2020, 2100, 5),
            labels=["", 2040, "", 2080, ""],
        ),
        p9.labs(x=""),
    ],
}


def figure(sources=("AR6", "iTEM MIP2"), **filters):
    """Decorator to handle common plot tasks.

    Example:

      @figure()
      def fig_N(data, sources)
          # Generate plot...
          plot.units = 'kg'
          return plot

      fig_N(options)

    A method (here 'fig_N') wrapped with this decorator:

    - Receives ≥2 arguments:
      - a dict *data*, with pre-loaded data for the variables under
        'fig_N' in figures.yaml. See inline comments in that file.
      - a 2-tuple *sources*, indicating the original data sources for
        IAM and sectoral models.
      - additional keyword arguments from *options*, such as 'normalize'.
    - Must return a plotnine.ggplot object with a 'units' attribute.

    The decorated method is then called with a *different* signature, taking
    only one argument: an optional dict of *options*. These include:

    - 'load_only': if True, then the plot is not written to file. Otherwise,
      the returned plot object is saved to 'fig_N.pdf'.

    """
    # Function that decorates the method
    def figure_decorator(func):
        # Information about the figure.
        # NB this code is run at the moment that the function is decorated.
        fig_id = func.__module__.split(".")[-1]
        fig_info = INFO[fig_id]
        var_names = fig_info["variables"]

        if not fig_info.get("all years", False):
            filters["year"] = YEARS

        # Wrapped method with new signature
        def wrapped(options={}):
            # NB this code not run until the figure is plotted.

            # Log output
            log.info("-" * 10)
            log.info(f"{fig_id}")

            load_only = options["load_only"]
            to_load = load_only or "iam item"

            # Load IAM and iTEM data
            data = {}
            args = dict(variable=var_names, categories=options["categories"])
            args.update(filters)
            if "iam" in to_load:
                data["iam"] = get_data(source=sources[0], **args).pipe(
                    restore_dims, fig_info.get("restore dims", None)
                )
            if "item" in to_load:
                data["item"] = get_data(
                    source=sources[1], conform_to=sources[0], **args
                )

            # Generate the plot
            args = dict(data=data, sources=sources)
            args["normalize"] = options["normalize"]
            args["overshoot"] = options["categories"] == "T+os"
            plot = func(**args)

            if plot:
                # Add a title
                plot += p9.ggtitle(
                    f"{fig_info['short title']} [{plot.units}] "
                    f"({fig_id}/{'/'.join(sources)})"
                )

            base_fn = f"{fig_id}"

            if fig_info.get("normalized version", False):
                # Distinguish normalized and absolute versions in file name
                base_fn += "-normalized" if args["normalize"] else "-absolute"

            # Save data to file.
            # Do this before plotting, so the data can be inspected even if the
            # plot is not constructed properly and fails.

            for label, df in data.items():
                path = OUTPUT_PATH / "data" / (base_fn + f"-{label}.csv")
                log.info(f"Dump {len(df):5} obs to {path}")
                df.to_csv(path)

            # Save to file unless --load-only was given
            if plot and not load_only:
                base_fn = OUTPUT_PATH / base_fn
                args = dict(
                    verbose=False,
                    width=190,
                    # Aspect ratio from figures.yaml
                    height=190 * fig_info.get("aspect ratio", 100 / 190),
                    units="mm",
                )
                plot.save(base_fn.with_suffix(".pdf"), **args)
                plot.save(base_fn.with_suffix(".png"), **args, dpi=300)

        return wrapped

    return figure_decorator
