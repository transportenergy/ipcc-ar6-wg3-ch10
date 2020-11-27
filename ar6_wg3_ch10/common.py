"""Common codes for plotting."""
import logging
from abc import abstractmethod
from collections import ChainMap
from pathlib import Path
from typing import Dict, List, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib as mpl
import numpy as np
import pandas as pd
import plotnine as p9

log = logging.getLogger(f"root.{__name__}")


# Matplotlib style
mpl.rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})


DATA_PATH = (Path(__file__).parents[1] / "data").resolve()

OUTPUT_PATH = Path("output")

YEARS = [2020, 2030, 2050, 2100]

DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# Scale for scenario categories
SCALE_CAT_BASE = pd.DataFrame(
    columns=["short", "limit", "label", "fill", "color"],
    data=[
        # # Earlier categorization
        # ["Below 1.6C", "green", "green", "<1.6°C"],
        # ["1.6 - 2.0C", "#fca503", "#fca503", "1.6–2°C"],
        # ["2.0 - 2.5C", "#ca34de", "#ca34de", "2–2.5°C"],
        # ["2.5 - 3.5C", "red", "red", "2.5–3.5°C"],
        # ["Above 3.5C", "brown", "brown", ">3.5°C"],
        #
        # C0 was removed from metadata as of 2020-11-18
        # ["C0", "C0: 1.5°C with no OS", "C0: 1.5°C no OS", "darkgreen", "darkgreen"],
        #
        # Current categorization
        ["C1", "C1: 1.5°C with no or low OS", "C1: 1.5°C lo OS", "green", "green"],
        [
            "C2",
            "C2: 1.5°C with high OS",
            "C2: 1.5°C hi OS",
            "yellowgreen",
            "yellowgreen",
        ],
        ["C3", "C3: likely 2°C", "C3: lo 2°C", "#fca503", "#fca503"],
        ["C4", "C4: below 2°C", "C4: hi 2°C", "#fe5302", "#fe5302"],
        ["C5", "C5: below 2.5°C", "C5: <2.5°C", "red", "red"],
        ["C6", "C6: below 3.0°C", "C6: <3.0°C", "brown", "brown"],
        ["C7", "C7: above 3.0°C", "C7: >3.0°C", "purple", "purple"],
        ["NCA", "no-climate-assessment", "No assessment", "#eeeeee", "#999999"],
        #
        # Sectoral scenarios
        ["P", "policy", "Sectoral/policy", "#eeeeee", "#999999"],
        ["R", "reference", "Sectoral/ref", "#999999", "#111111"],
    ],
)

# Recategorized/grouped categories
SCALE_CAT_A = pd.DataFrame(
    columns=["short", "limit", "label", "fill", "color"],
    data=[
        ["C1–2", "C1 or C2: 1.5°C", "C1–2: 1.5°C", "green", "green"],
        ["C3–5", "C3, C4, or C5: below 2.5°C", "C3–5: <2.5°C", "#fe5302", "#fe5302"],
        ["C6–7", "C6 or C7: above 2.5°C", "C6–7: ≥3.0°C", "purple", "purple"],
    ],
)

SCALE_CAT_B = pd.DataFrame(
    columns=["short", "limit", "label", "fill", "color"],
    data=[
        ["C1", "C1: 1.5°C with no or low OS", "C1: 1.5°C lo OS", "green", "green"],
        ["C2,4", "C2 or C4", "C2,4", "#fe5302", "#fe5302"],
        ["C3,5", "C3 or C5", "C3,5", "red", "red"],
        ["C6,7", "C6 or C7", "C6,7: ≥2.5°C", "purple", "purple"],
    ],
)

# Mapping of categories to groups for recategorization
_CG = (
    ("C1", "C1–2", "C1"),
    ("C2", "C1–2", "C2,4"),
    ("C3", "C3–5", "C3,5"),
    ("C4", "C3–5", "C2,4"),
    ("C5", "C3–5", "C3,5"),
    ("C6", "C6–7", "C6,7"),
    ("C7", "C6–7", "C6,7"),
)

CAT_GROUP = dict(
    A={c[0]: c[1] for c in _CG},
    B={c[0]: c[2] for c in _CG},
)


# Scale for fuel aggregates; see aggregate_fuels()
SCALE_FUEL = pd.DataFrame(
    columns=["limit", "fill", "label"],
    data=[
        ["Liquids|Oil", "#f7a800", "Oil"],
        ["Biofuels", "#de4911", "Biofuels"],
        ["Gases", "#9e2b18", "Gases"],
        ["Electricity", "#9fca71", "Electricity"],
        ["Hydrogen", "#59a431", "Hydrogen"],
        ["Other", "#999999", "Other"],
    ],
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


def maybe_drop_nca(df, include_nca):
    """Remove data with no climate assessment from `df`."""
    return df if include_nca else df.query("category != 'no-climate-assessment'")


def remove_categoricals(df):
    """Convert categorical columns in `df` to string."""
    cols = [n for n, dt in df.dtypes.items() if isinstance(dt, pd.CategoricalDtype)]
    return df.astype({c: str for c in cols})


def scale_category(aesthetic, plot=None, **options):
    """Generate scales based on the AR6 categories, with options."""
    options = ChainMap(getattr(plot, "__dict__", {}), options)

    data = SCALE_CAT_BASE.copy()

    recategorize = options.get("recategorize")
    if recategorize:
        data = pd.concat([globals()[f"SCALE_CAT_{recategorize}"], data.iloc[-3:, :]])

    if not options.get("include_nca", False):
        # Remove no-climate-assessment point on scale
        data = data.query("short != 'NCA'").reset_index(drop=True)

    short_label = options.get("short_label", False)
    limit = "short" if recategorize else "limit"
    label = "short" if short_label else "label"

    if aesthetic == "x":
        theme_kwarg = dict() if short_label else dict(axis_text_x=p9.element_blank())
        return [
            p9.aes(x="category"),
            p9.scale_x_discrete(limits=data[limit], labels=data[label]),
            p9.labs(x=""),
            p9.theme(axis_ticks_major_x=p9.element_blank(), **theme_kwarg),
        ]
    elif aesthetic == "fill":
        return [
            p9.scale_fill_manual(
                limits=data[limit], values=data["fill"], labels=data[label]
            )
        ]
    elif aesthetic == "color":
        return [
            p9.aes(color="category"),
            p9.scale_color_manual(limits=data[limit], values=data["color"]),
        ]
    else:
        raise ValueError(aesthetic)


class Figure:
    """Class to automate common figure/plot steps."""

    # Required
    id: str
    title: str
    aspect_ratio: float
    variables: List[str]

    #: Names of sources for IAM and sectoral model data. Length 2.
    sources: Sequence[str]

    # Optional
    #: :obj:`True` if the figure respects the following options.
    has_option = dict(
        normalize=False,
        per_capita=False,
    )

    #: :obj:`True` if the ordinate should be normalized.
    normalize = True
    #: :obj:`True` if the ordinate should be divided by population.
    per_capita = False

    #: Filters for loading data
    filters = dict()
    #: :obj:`True` to load data for all years, not merely :data:`YEARS`.
    all_years = False
    #: Regular expression to unpack dimensions from variable names. Captured groups
    #: '(?P<name>...)' are added as new columns in the loaded data.
    restore_dims = None
    #: :mod:`plotnine` geoms/layers to add to all plots.
    geoms = []
    #: Aspect ratio for output
    aspect_ratio = 1.0 / 1.9

    def __init__(self, options: Dict):
        # Log output
        log.info("-" * 10)
        log.info(f"{self.__class__.__name__}: {self.title}")

        # Update properties from options
        self.__dict__.update(options)

        # Base filename
        fn_parts = [
            self.__class__.__name__.lower(),
            self.sources[0].replace(" ", "-"),
            self.sources[1].replace(" ", "-"),
        ]
        # Distintuish optional variants in file name
        if self.has_option.get("per_capita", False) and self.per_capita:
            fn_parts.insert(-2, "percap")
        if self.has_option.get("normalize", False) and not self.normalize:
            fn_parts.insert(-2, "abs")
        if self.recategorize:
            fn_parts.insert(-1, f"recat{self.recategorize}")
        self.base_fn = "-".join(fn_parts)

        # Set filters based on all years property.
        if not self.all_years:
            self.filters["year"] = YEARS

        # Store figure size: 190 mm in inches, aspect ratio from a property
        self.geoms.append(p9.theme(figure_size=(7.48, 7.48 * self.aspect_ratio)))

        # Title template
        self.formatted_title = f"{self.title} [{{units}}] ({self.base_fn})"

    def _prepare_data(self):
        from .data import get_data, restore_dims

        # Temporary storage for data
        data = {}

        # Arguments for get_data()
        args = dict(variable=self.variables, recategorize=self.recategorize)
        args.update(self.filters)

        # - Load IAM data.
        # - Restore additional dimensions, according to class properties.
        # - Remove categorical columns.
        # - Drop NCA data, according to (command-line) option.
        data["iam"] = (
            get_data(source=self.sources[0], **args)
            .pipe(restore_dims, self.restore_dims)
            .pipe(remove_categoricals)
            .pipe(maybe_drop_nca, self.include_nca)
        )
        if self.has_option.get("per_capita", False) and self.per_capita:
            # Load population data for per capita calculations
            pop_args = args.copy()
            pop_args["variable"] = ["Population"]
            data["population"] = get_data(source=self.sources[0], **pop_args)
        else:
            data["population"] = pd.DataFrame()

        # Load iTEM data
        data["item"] = get_data(source=self.sources[1], conform_to="AR6", **args).pipe(
            remove_categoricals
        )

        # Use a subclass method to further prepare data
        self.data = self.prepare_data(data)

        # Dump data for reference
        path_zf = OUTPUT_PATH / "data" / f"{self.base_fn}.zip"
        log.info(f"Dump data to {path_zf}")
        with ZipFile(path_zf, "w", compression=ZIP_DEFLATED) as zf:
            for label, df in sorted(
                self.data.items(), key=lambda i: len(i[1]), reverse=True
            ):
                if not len(df):
                    continue

                log.info(f"{len(df):7} obs for {repr(label)}")
                path_tmp = OUTPUT_PATH / "data" / f"{self.base_fn}_{label}.csv"
                df.to_csv(path_tmp)
                zf.write(path_tmp, arcname=f"{label}.csv")
                path_tmp.unlink()

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
