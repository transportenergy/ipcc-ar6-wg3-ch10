"""Command-line interface using 'click'."""
import logging
import logging.config
from datetime import datetime
from importlib import import_module
from pathlib import Path

import click
import pandas as pd
import yaml

from data import REMOTE_DATA

OUTPUT_PATH = Path("output")
NOW = datetime.now().isoformat(timespec="seconds")

# Log configuration
_LC = yaml.safe_load(open(Path(__file__).parents[1] / "data" / "logging.yaml"))


def _start_log():
    logging.config.dictConfig(_LC)


@click.group()
@click.option(
    "--verbose", is_flag=True, help="Also print DEBUG log messages to stdout."
)
def cli(verbose):
    """Command-line interface for IPCC AR6 WGIII Ch.10 figures.

    Reads a file config.json in the current directory. See config-example.json.

    Verbose log information for certain commands is written to a timestamped
    .log file in output/.
    """
    _LC["handlers"]["file"]["filename"] = OUTPUT_PATH / f"{NOW}.log"

    if verbose:
        _LC["handlers"]["console"]["level"] = "DEBUG"


@cli.command()
@click.argument("action", type=click.Choice(["refresh", "clear", "compile"]))
@click.argument("source", type=click.Choice(REMOTE_DATA.keys()))
def cache(action, source):
    """Retrive data from remote databases to data/cache/SOURCE/.

    An HDF5 file named all.h5 is also created to speed retrieval.

    \b
    The download takes:
    - AR6: ~60 minutes for 895 scenarios / 3.3 GiB.
      all.h5 is 9.1 GiB.
    - SR15: ~15 minutes for 416 scenarios / 832 MiB.
    """
    _start_log()

    from cache import cache_data

    if action == "refresh":
        cache_data(source)
    else:
        print("Please clear the cache manually.")
        raise NotImplementedError


@cli.command()
@click.option("--dump", is_flag=True, help="Also dump all data to output/coverage.csv.")
def coverage(dump):
    """Report coverage per data/coverage-checks.yaml."""
    _start_log()

    from coverage import checks_from_file

    dump_path = OUTPUT_PATH if dump else None

    checks_from_file(dump_path)


@cli.command()
def debug():
    """Demo or debug code."""
    _start_log()

    from data import get_client, get_data

    client = get_client()

    # List of all scenarios
    print(pd.DataFrame.from_dict(client.runs()))

    # Data for particular runs
    print(get_data(runs=[746, 791]))


@cli.command()
@click.option(
    "--normalize", is_flag=True, default=False, help="Normalize ordinate to 2020."
)
@click.option("--categories", type=click.Choice(["T", "T+os"]), default="T")
@click.option(
    "--ar6-data",
    type=click.Choice(["", "snapshot", "snapshot R5", "snapshot R10"]),
    help="Source or snapshot of AR6 data.",
)
@click.option(
    "--item-data",
    type=click.Choice(["MIP2", "MIP3"]),
    default="MIP2",
    help="Source or snapshot of iTEM data.",
)
@click.option(
    "--load-only",
    is_flag=True,
    help="Only load and preprocess data; no output.",
)
@click.argument("to_plot", metavar="FIGURES", type=int, nargs=-1)
def plot(to_plot, **options):
    """Plot figures, writing to output/.

    FIGURES is a sequence of ints, e.g. 1 4 5 to plot figures 1, 4, and 5.

    \b
    --categories controls the grouping of IAM scenarios:
    - 'T': five categories by temperature in 2100, using the WGIII-wide
           indicator 'Temperature-in-2100_bin'
    - 'T+os': six categories by two criteria: temperature in 2100, as above;
              and, for *only* the lowest bin ('Below 1.6C'), additional
              subdivision based on whether temperature overshoot occurs, i.e. a
              value in 'overshoot years|1.5°C'.

    Options --normalize and --categories do not affect the appearance of every
    figure.
    """
    _start_log()

    options["sources"] = (
        " ".join(filter(None, ["AR6", options.pop("ar6_data")])),
        f"iTEM {options.pop('item_data')}",
    )

    # Plot each figure
    for fig_id in to_plot:
        mod = import_module(f".fig_{fig_id}", package="ar6_wg3_ch10")
        mod.plot(options)

    # # Extra plots: Render and save
    # extra_fn = (output_path / f'extra_{now}').with_suffix('.pdf')
    # p9.save_as_pdf_pages(gen_plots(), extra_fn)


@cli.command()
def refs():
    """Retrieve reference files to ref/."""
    from cache import get_references

    get_references()


@cli.command()
@click.option("--go", is_flag=True)
def upload(go):
    """Sync output/ to a remote directory using rclone.

    \b
    Requires the following configuration:
    - Rclone installed from https://rclone.org.
    - At least one remote configured.
    - In config.json, a key 'rclone' and sub-key
      'output' with a destination ("remote:path").
    """
    from subprocess import check_call
    from data import CONFIG

    check_call(
        [
            "rclone",
            "--progress" if go else "--dry-run",
            "sync",
            "output",
            CONFIG["rclone"]["output"],
        ]
    )


@cli.command()
def variables():
    """Write lists of variables for each data source.

    The lists are written to data/variables-SOURCE-all.txt. These lists are
    *manually* trimmed to variables-SOURCE.txt, which in turn are used to
    filter data imports
    """
    _start_log()

    from data import DATA_PATH, LOCAL_DATA, get_data

    def write_vars(src, vars):
        (DATA_PATH / f"variables-{source}-all.txt").write_text("\n".join(vars))

    for source in LOCAL_DATA.keys():
        print(f"Processing {source!r}")
        df = get_data(source)
        write_vars(source, sorted(df["variable"].unique()))

    for source in REMOTE_DATA.keys():
        print(f"Processing {source!r}")
        try:
            df = get_data(source, use_cache=True)
        except ValueError as e:
            if e.args[0] == "No objects to concatenate":
                continue
            else:
                raise
        write_vars(source, sorted(df["variable"].unique()))


# Start the CLI
cli()
