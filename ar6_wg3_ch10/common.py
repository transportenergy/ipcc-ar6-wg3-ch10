import logging
from abc import abstractmethod
from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib as mpl
import numpy as np
import pandas as pd
import plotnine as p9
import yaml

log = logging.getLogger(f"root.{__name__}")


# Matplotlib style
mpl.rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})


DATA_PATH = (Path(__file__).parents[1] / "data").resolve()

OUTPUT_PATH = Path("output")

YEARS = [2020, 2030, 2050, 2100]

DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

with open(DATA_PATH / "figures.yaml") as f:
    INFO = yaml.safe_load(f)

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
        ["C0: 1.5°C with no OS", "green", "green", "1.5°C no OS", "C0"],
        ["C1: 1.5°C with no or low OS1.6", "green", "green", "1.5°C lo OS", "C1"],
        ["C2: 1.5°C with high OS_1.6", "green", "green", "1.5°C hi OS", "C2"],
        ["C3: likely 2°C", "#fca503", "#fca503", "lo 2°C", "C3"],
        ["C4: below 2°C", "#fe5302", "#fe5302", "hi 2°C", "C4"],
        ["C5: below 2.5°C", "red", "red", "<2.5°C", "C5"],
        ["C6: below 3.0°C", "brown", "brown", "<3.0°C", "C6"],
        ["C7: above 3.0°C", "purple", "purple", ">3.0°C", "C7"],
        ["no-climate-assessment", "#eeeeee", "#999999", "nca", "NCA"],

        # Sectoral scenarios
        ["policy", "#eeeeee", "#999999", "Sectoral/policy", "P"],
        ["reference", "#999999", "#111111", "Sectoral/ref", "R"],
    ],
    columns=["limit", "fill", "color", "label", "short"],
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
        text=p9.element_text(font="Fira Sans"),
        # Background colours
        panel_background=p9.element_rect(fill="#fef6e6"),
        strip_background=p9.element_rect(fill="#fef6e6"),
        # Y-axis grid lines
        panel_grid_major_y=p9.element_line(color="#bbbbbb"),
        panel_grid_minor_y=p9.element_line(color="#eeeeee", size=0.1),
        # Plot title
        plot_title=p9.element_text(size=10),
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
        ),
        p9.labs(x=""),
        p9.theme(axis_text_x=p9.element_blank(), axis_ticks_major_x=p9.element_blank()),
    ],
    "x category short": [
        p9.aes(x="category"),
        p9.scale_x_discrete(limits=SCALE_CAT["limit"], labels=SCALE_CAT["short"]),
        p9.labs(x=""),
        p9.theme(axis_ticks_major_x=p9.element_blank()),
    ],
    "fill category": lambda os: p9.scale_fill_manual(
        limits=(SCALE_CAT_OS if os else SCALE_CAT)["limit"],
        values=(SCALE_CAT_OS if os else SCALE_CAT)["fill"],
        labels=(SCALE_CAT_OS if os else SCALE_CAT)["label"],
    ),
    "color category": lambda os: [
        p9.aes(color="category"),
        p9.scale_color_manual(
            limits=(SCALE_CAT_OS if os else SCALE_CAT)["limit"],
            values=(SCALE_CAT_OS if os else SCALE_CAT)["color"],
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


def remove_categoricals(df):
    """Convert categorical columns in `df` to string."""
    cols = [n for n, dt in df.dtypes.items() if isinstance(dt, pd.CategoricalDtype)]
    return df.astype({c: str for c in cols})


def figure(func):
    """Decorator to handle common plot tasks.

    Example:

      @figure
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
    filters = dict()
    # filters = dict(region=["World"])

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
        from .data import get_data, restore_dims

        sources = options.pop("sources")

        # Log output
        log.info("-" * 10)
        log.info(f"{fig_id}")

        # Load IAM and iTEM data
        data = {}
        args = dict(variable=var_names, categories=options["categories"])
        args.update(filters)
        data["iam"] = (
            get_data(source=sources[0], **args)
            .pipe(restore_dims, fig_info.get("restore dims", None))
            .pipe(remove_categoricals)
        )
        data["item"] = (
            get_data(source=sources[1], conform_to="AR6", **args)
            .pipe(remove_categoricals)
        )

        # Base filename
        base_fn = f"{fig_id}-{sources[0].replace(' ', '_')}"

        if fig_info.get("normalized version", False):
            # Distinguish normalized and absolute versions in file name
            base_fn += "-norm" if options["normalize"] else "-abs"

        # Generate the plot
        args = dict(data=data, sources=sources)
        args["normalize"] = options["normalize"]
        args["overshoot"] = options["categories"] == "T+os"
        args["figure size"] = p9.theme(
            # 190 mm, in inches; aspect ratio from figures.yaml
            figure_size=(7.48, 7.48 * fig_info.get("aspect ratio", 1. / 1.9))
        )
        args["title"] = (
            f"{fig_info['short title']} [{{units}}] ({base_fn})"
        )

        plot = func(**args)

        # Save data to file.
        # Do this before plotting, so the data can be inspected even if the
        # plot is not constructed properly and fails.

        for label, df in data.items():
            path = OUTPUT_PATH / "data" / (base_fn + f"-{label}.csv")
            log.info(f"Dump {len(df):5} obs to {path}")
            df.to_csv(path)

        # Save to file unless --load-only was given
        if plot and not options["load_only"]:
            base_fn = OUTPUT_PATH / base_fn

            log.info(f"Save {base_fn.with_suffix('.pdf')}")

            try:
                # Single plot
                plot.save(base_fn.with_suffix(".pdf"), verbose=False)
                plot.save(base_fn.with_suffix(".png"), verbose=False, dpi=300)
            except AttributeError:
                # Iterator containing multiple plots
                p9.save_as_pdf_pages(plot, base_fn.with_suffix(".pdf"), verbose=False)

    return wrapped


class Figure:
    # Required
    id: str
    title: str
    aspect_ratio: float
    variables: List[str]

    #: Names of sources for IAM and sectoral model data. Length 2.
    sources: Sequence[str]

    # Optional
    #: :obj:`True` if the figure respects a "normalize" option.
    normalized_version = False
    #: Filters for loading data
    filters = dict()
    #: :obj:`True` to load data for all years, not merely :data:`YEARS`.
    all_years = False
    #: Regular expression to unpack dimensions from variable names.
    restore_dims = None
    #: :mod:`plotnine` geoms/layers to add to all plots.
    geoms = []
    #: Aspect ratio for output
    aspect_ratio = 1. / 1.9

    def __init__(self, options: Dict):
        # Log output
        log.info("-" * 10)
        log.info(f"{self.id}: {self.title}")

        # Update properties from options
        self.__dict__.update(options)

        # Base filename
        self.base_fn = f"{self.id}-{self.sources[0].replace(' ', '_')}"
        if self.normalized_version:
            # Distinguish normalized and absolute versions in file name
            self.base_fn += "-norm" if options.get("normalize", True) else "-abs"

        # Set filters based on all years property.
        if not self.all_years:
            self.filters["year"] = YEARS

        self.overshoot = self.categories == "T+os"

        # Store figure size: 190 mm in inches, aspect ratio from a property
        self.geoms.append(p9.theme(figure_size=(7.48, 7.48 * self.aspect_ratio)))

        # Title template
        self.formatted_title = f"{self.title} [{{units}}] ({self.base_fn})"

    def _prepare_data(self):
        from .data import get_data, restore_dims

        # Temporary storage for data
        data = {}

        # Arguments for get_data()
        args = dict(variable=self.variables, categories=self.categories)
        args.update(self.filters)

        # Load IAM data
        data["iam"] = (
            get_data(source=self.sources[0], **args)
            .pipe(restore_dims, self.restore_dims)
            .pipe(remove_categoricals)
        )
        # Load iTEM data
        data["item"] = (
            get_data(source=self.sources[1], conform_to="AR6", **args)
            .pipe(remove_categoricals)
        )

        # Use a subclass method to further prepare data
        self.data = self.prepare_data(data)

        # Dump data for reference
        for label, df in self.data.items():
            path = OUTPUT_PATH / "data" / f"{self.base_fn}-{label}.csv"
            log.info(f"Dump {len(df):5} obs to {path}")
            df.to_csv(path)

    @staticmethod
    @abstractmethod
    def prepare_data(data):
        """Must be implemented by subclasses."""

    @abstractmethod
    def generate(self):
        """Must be implemented by subclasses."""

    def save(self):
        self._prepare_data()

        if self.load_only:
            return

        # Generate 1 or more plots
        plot = list(self.generate())

        # Save to file
        base_fn = OUTPUT_PATH / self.base_fn

        log.info(f"Save {base_fn.with_suffix('.pdf')}")

        try:
            # Single plot
            plot.save(base_fn.with_suffix(".pdf"), verbose=False)
            plot.save(base_fn.with_suffix(".png"), verbose=False, dpi=300)
        except AttributeError:
            # Iterator containing multiple plots
            p9.save_as_pdf_pages(plot, base_fn.with_suffix(".pdf"), verbose=False)
