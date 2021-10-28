"""Utility code for checking data coverage."""
import yaml
from zipfile import ZipFile

import pandas as pd

from .common import DATA_PATH, NOW, OUTPUT_PATH
from .data import get_data


def run_checks(from_file=True, dump_path=None):
    # Determine variables to check
    if from_file:
        checks = yaml.safe_load(open(DATA_PATH / "coverage-checks.yaml"))
    else:
        variables = (DATA_PATH / "variables-AR6.txt").read_text().split("\n")
        checks = list(map(lambda v: dict(variable=[v]), variables))

    N = len(checks)

    for i, info in enumerate(checks):
        lines = [f"--- {i:03d} of {N}", "", f"Coverage of {info!r}"]
        note = info.pop("_note", None)
        if dump_path is not None:
            dump_fn = f"{i:03}.csv"
            lines.append(f"Dumped to {dump_fn}")
        if note:
            lines.append(f"Note: {note}")

        for source in "AR6 world", "AR6 R5", "AR6 R10", "AR6 country", "iTEM MIP2":
            args = info.copy()
            if "iTEM" in source:
                args.update(dict(conform_to="AR6", default_item_filters=False))
            data = get_data(source, **args).assign(source=source)

            lines.extend([f"  {source}:", f"    {len(data)} observations"])

            if len(data) == 0:
                continue

            cats = data["category"].unique()
            lines.extend(
                [
                    " {:4d} models".format(len(data["model"].unique())),
                    " {:4d} (model, scenario) combinations".format(
                        len(data.groupby(["model", "scenario"]))
                    ),
                    " {:4d} scenario categories:".format(len(cats)),
                ]
            )
            lines.extend(cats + [""])

            if any(s in source for s in ("R5", "R10", "country")):
                # Give number of regions for non-global data
                regions = data["region"].unique()
                lines.append(" {:4d} regions".format(len(regions)))

                if "country" in source:
                    # Give specific list of countries for country-level data
                    lines[-1] += ":"
                    lines.extend(sorted(regions))

            if dump_path is not None:
                data.to_csv(dump_path / dump_fn)

        print("\n".join(lines), end="\n\n", flush=True)


def count_ids():
    """Count and output unique model- and scenario names in the final figures."""
    # Identifiers of final figures
    figures = [
        "fig1-AR6-R6-bw9",
        "fig1-AR6-world-bw9",
        "fig2-AR6-R6-bw9",
        "fig2-AR6-world-bw9",
        "fig4-AR6-world-bw9",
        "fig6-AR6-world-recatA-bw8",
        "fig7-AR6-world-recatA-bw9",
        "fig7-AR6-world-bw9",
    ]

    # Sets of unique names
    names = dict(model=set(), scenario=set())

    # Iterate over figures
    for id in figures:
        # Path to the data dump associated with the figure
        path = OUTPUT_PATH.joinpath("data", f"{id}.zip")
        print(f"Count model/scenario names in {path}")
        with ZipFile(path) as zf:
            # Count model/scenario names for both IAM and G-/NTEM data
            for kind in ("iam", "tem"):
                filename = f"{kind}.csv"
                try:
                    data = pd.read_csv(zf.open(filename))
                except KeyError:
                    print(f"  {filename}: does not exist")
                    continue

                # Update the sets
                for key in names:
                    names[key].update(data[key].tolist())

                # Display progress
                print(f"  {filename}: {dict((k, len(v)) for k, v in names.items())}")

    # Output
    for key, values in names.items():
        path = OUTPUT_PATH.joinpath("data", f"count-{key}-{NOW}.txt")
        path.write_text("\n".join(sorted(values)))
        print(f"Wrote {len(values)} {key} name(s) to {path}")
