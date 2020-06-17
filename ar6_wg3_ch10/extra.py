"""Extra figures for reference, comparing IPCC SR1.5 and iTEM2 data.

Repurposed from P.N. Kishimoto code for iTEM4, October 2018.
"""
import matplotlib as mpl
import pandas as pd
import plotnine as p9

from data import VARIABLES, compute_descriptives, get_data, get_data_item, item_var_info

# Matplotlib style
mpl.rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})


YEARS = [2030, 2050, 2100]


# Metadata for categories and 'super'categories
# - The colour for 2C is midway between the colours for 'Higher-' and 'Lower
#   2C', etc.
cat_meta = pd.DataFrame(
    [
        ("Above 2C", "red", r">2°", ""),
        ("2C", "#ca34de", r"2°", ""),  # Supercategory
        ("Higher 2C", "purple", r"hi", "2C"),
        ("Lower 2C", "magenta", r"lo", "2C"),
        ("1.5C", "#fca503", r"1.5°", ""),  # Supercategory
        ("1.5C high overshoot", "#f97306", r"hi", "1.5C"),
        ("1.5C low overshoot", "gold", r"lo", "1.5C"),
        ("Below 1.5C", "green", r"<1.5°", ""),
        ("reference", "black", "Ref", "item"),
        ("policy", "black", "Pol", "item"),
    ],
    columns=["category", "color", "label", "supercategory"],
)


def prepare_data(source):
    # Read data from local cache using a subset of variables;
    # drop scenarios that belong to no recognized category
    data = get_data(
        source, use_cache=True, vars_from_file=True, year=YEARS, region=["World"]
    ).dropna(subset=["category"])

    # Filter further by category;
    # add plotting metadata: color, label, supercategory
    data = data[~data.category.isin(["no-climate-assessment", "reference"])].merge(
        cat_meta, how="left", on="category"
    )

    # Compute descriptives by variable, then re-merge the category-level
    # metadata
    result = (
        data.pipe(compute_descriptives)
        .reset_index()
        .merge(cat_meta, how="left", on="category")
    )

    # Return both scenario-level data and descriptives by variable
    return data, result


# Common plot features
plot_common = [
    # Aesthetic mappings
    p9.aes(x="category", color="category"),
    # Horizontal panels by the years shown
    p9.facet_wrap("year"),
    # Vertical bars showing range of projections
    p9.geom_linerange(p9.aes(ymin="min", ymax="max"), size=6, color="#bbbbbb"),
    p9.geom_linerange(p9.aes(ymin="25%", ymax="75%"), size=6),
    # Median
    p9.geom_point(p9.aes(y="50%"), color="black", shape="_", size=6),
    # Vertical lines to separate scenario groups
    p9.geom_vline(xintercept=1.5, color="#bbbbbb"),
    p9.geom_vline(xintercept=4.5, color="#bbbbbb"),
    p9.geom_vline(xintercept=7.5, color="#bbbbbb"),
    p9.geom_vline(xintercept=8.5, color="#999999"),
    # Counts of number of scenarios included
    p9.geom_text(p9.aes(label="count", y="max"), format_string="{:.0f}", va="bottom",),
    # x-scale order and labels. Use 'expand' to leave room on right for iTEM2
    p9.scale_x_discrete(
        limits=cat_meta["category"], labels=cat_meta["label"], expand=(0, 0.5, 0, 1)
    ),
    # color scale values
    p9.scale_color_manual(cat_meta["color"], limits=cat_meta["category"]),
    # Axis labels
    p9.labs(x="", color="SR1.5 IAM scenarios", shape="Global transport models"),
    p9.guides(color=p9.guide_legend(ncol=2), shape=p9.guide_legend(ncol=2)),
    p9.theme(plot_background=p9.element_rect(alpha=0)),
]


# Create plot objects
def gen_plots(source="SR15"):
    # Raw data and descriptives by category and supercategory
    data, plot_data = prepare_data(source)

    for var_info in VARIABLES:
        # Variable name
        name = var_info[source]

        # Select data
        df = plot_data[plot_data.variable == name]

        # Y-axis label
        row = data[data.variable == name]
        if not len(row):
            # No SR1.5 data for this variable
            continue

        labels = p9.labs(y=row.iloc[0, :]["unit"])
        title = p9.ggtitle("{} ({}, {})".format(name, source, "iTEM MIP2"))

        # Create the plot
        plot = p9.ggplot(df) + plot_common + labels + title
        try:
            # Info for corresponding iTEM variable
            filters, scale = item_var_info("SR15", name)
            filters["year"] = YEARS
        except KeyError:
            # No iTEM2 data for this variable
            pass
        else:
            plot += p9.geom_point(
                mapping=p9.aes(y="value", shape="model"),
                data=get_data_item(filters, scale),
                color="black",
                size=2,
                fill=None,
            )

        print("Plotting {}".format(name))

        yield plot
