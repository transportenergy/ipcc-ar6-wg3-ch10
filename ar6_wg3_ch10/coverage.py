"""Utility code for checking data coverage."""
import yaml

from data import DATA_PATH, get_data


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
