import pandas as pd
import yaml

from data import DATA_PATH, get_data


def checks_from_file(dump_path=None):
    dfs = []

    for info in yaml.safe_load(open(DATA_PATH / "coverage-checks.yaml")):
        note = info.pop("_note", "(none)")
        lines = [
            "---"
            f"\nCoverage of {info!r}",
            f"Note: {note}",
        ]

        for source in "AR6", "iTEM MIP2":
            args = info.copy()
            if "iTEM" in source:
                args.update(dict(conform_to="AR6", default_item_filters=False))
            data = get_data(source, **args).assign(source=source)

            lines.extend([f"  {source}:", f"    {len(data)} observations"])

            if len(data) == 0:
                continue

            lines.extend(
                [
                    "    {} (model, scenario) combinations".format(
                        len(data.groupby(["model", "scenario"]))
                    ),
                    "    {} scenario categories".format(len(data["category"].unique())),
                    "    {} models".format(len(data["model"].unique())),
                    "    {} regions:".format(len(data["region"].unique())),
                ]
            )

            lines.extend(sorted(data["region"].unique()))

            if dump_path:
                dfs.append(data)

        print("\n".join(lines), end="\n\n")

        if dump_path:
            pd.concat(dfs).to_csv(dump_path / "coverage.csv")
