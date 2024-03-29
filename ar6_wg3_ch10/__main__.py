"""Command-line interface for IPCC AR6 WGIII Ch.10 figures.

Reads a file config.json in the current directory. See config-example.json.

Verbose log information for certain commands is written to a timestamped .log file in
output/.
"""
import logging
import logging.config
from importlib import import_module
from itertools import product
from pathlib import Path
from traceback import print_exc

import click
import yaml

from .common import DATA_PATH, FINAL, NOW, OUTPUT_PATH, REMOTE_DATA

log = logging.getLogger(__name__)

# Log configuration
LC = yaml.safe_load(open(Path(__file__).parents[1] / "data" / "logging.yaml"))


def _start_log():
    logging.config.dictConfig(LC)


@click.group(help=__doc__)
@click.option("--skip-cache", is_flag=True, help="Don't use cached intermediate data.")
@click.option(
    "--verbose", is_flag=True, help="Also print DEBUG log messages to stdout."
)
def cli(skip_cache, verbose):
    LC["handlers"]["file"]["filename"] = OUTPUT_PATH / f"{NOW}.log"

    if verbose:
        LC["handlers"]["console"]["level"] = "DEBUG"

    if skip_cache:
        from . import util

        util.SKIP_CACHE = True


@cli.command()
@click.argument("action", type=click.Choice(["refresh", "compile"]))
@click.argument("source", type=click.Choice(REMOTE_DATA.keys()))
def remote(action, source):
    """Retrive data from remote databases to data/cache/SOURCE/.

    An HDF5 file named all.h5 is also created to speed retrieval.

    \b
    The download takes:
    - AR6: ~60 minutes for 895 scenarios / 3.3 GiB. all.h5 is 9.1 GiB.
    - SR15: ~15 minutes for 416 scenarios / 832 MiB.
    """
    _start_log()

    from cache import cache_data

    if action == "refresh":
        cache_data(source)
    else:
        print("Please clear the cache manually.")
        raise NotImplementedError


@cli.command(name="clear-cache")
@click.argument("pattern")
def clear_cache(pattern):
    """Clear cached/intermediate data matching PATTERN."""
    from .common import DATA_PATH

    for path in DATA_PATH.joinpath("cache").glob(f"{pattern}*.pkl"):
        print(path)
        path.unlink()


@cli.command()
@click.option("--all-vars", is_flag=True, default=False, help="Check all variables.")
@click.option(
    "--dump",
    is_flag=True,
    default=False,
    help="Also dump data to output/coverage/[...].csv.",
)
def coverage(all_vars, dump):
    """Report coverage of transport variables.

    If --all-vars is not given, checks are read from `data/coverage-checks.yaml`.
    """
    # Hide debug information about data loading etc.
    # _start_log()

    from coverage import run_checks

    if all_vars:
        # Don't dump when running checks on all data
        dump = False

    run_checks(from_file=not all_vars, dump_path=OUTPUT_PATH if dump else None)


@cli.command()
def count():
    """Count model and scenario names in final data.

    This command requires that the figures have been generated.
    """
    from . import coverage

    coverage.count_ids()


@cli.command()
def debug():
    """Demo or debug code."""

    _start_log()

    from .data import get_data

    print(
        get_data(
            "AR6 R5",
            variable=[
                "Energy Service|Transportation|Freight",
                "Energy Service|Transportation|Passenger",
            ],
            year=[2020, 2030, 2100],
        )
    )


@cli.command()
@click.option(
    "--ar6-data",
    type=click.Choice(["world", "R5", "R6", "R10", "country", "IP", "raw"]),
    default="world",
    help="Source snapshort for IPCC/IAM data.",
)
@click.option(
    "--recategorize",
    "--recat",
    type=click.Choice(["A", "B"]),
    default=None,
    help="Group scenarios categories into fewer.",
)
@click.option(
    "--tem-data",
    type=click.Choice(["MIP2", "MIP3", "IMO"]),
    default="MIP2",
    help="Source of G-/NTEM data.",
)
@click.option(
    "--load-only",
    is_flag=True,
    help="Only load and preprocess data; no output.",
)
@click.option(
    "--normalize/--absolute", default=True, help="Normalize ordinate to 2020 (default)."
)
@click.option(
    "--per-capita", is_flag=True, default=False, help="Compute per-capita ordinate."
)
@click.option(
    "--include-nca",
    is_flag=True,
    default=False,
    help="Include scenarios with no climate assessment",
)
@click.option(
    "--bandwidth",
    "--bw",
    type=click.Choice(["5", "8", "9", "10", "0"]),
    default="0",
    callback=lambda ctx, param, value: int(value),
    help="Width of bands, in deciles (default varies by figure)",
)
@click.argument("to_plot", metavar="FIGURES", type=int, nargs=-1)
def plot(to_plot, **options):
    """Plot figures, writing to output/.

    FIGURES is a sequence of ints, e.g. "1 4 5" to plot figures 1, 4, and 5.

    Not every option is recognized by every figure.
    """
    _start_log()

    tem_data = options.pop("tem_data")
    options["sources"] = (
        f"AR6 {options.pop('ar6_data')}",
        f"iTEM {tem_data}" if "MIP" in tem_data else tem_data,
    )

    # Plot each figure
    for fig_id in to_plot:
        mod = import_module(f".fig_{fig_id}", package="ar6_wg3_ch10")
        getattr(mod, f"Fig{fig_id}")(options).save()

    # # Extra plots: Render and save
    # extra_fn = (output_path / f'extra_{now}').with_suffix('.pdf')
    # p9.save_as_pdf_pages(gen_plots(), extra_fn)


@cli.command(name="plot-all")
@click.option(
    "--per-capita", is_flag=True, default=False, help="Compute per-capita ordinate."
)
@click.pass_context
def plot_all(ctx, **options):
    """Generate all plots.

    Use --skip-cache when the initial data-loading code changes.
    Use --per-capita for e.g. fig_2.
    """
    # Comment out entries to reduce the set of plots generated
    figures = [
        1,
        2,
        4,
        6,
        7,
        8,
        9,
        10,
    ]
    source = [
        "world",
        "R5",
        "R6",
        "R10",
        "country",
    ]
    normalize = [
        True,
        False,
    ]
    recategorize = [
        None,
        "A",
        "B",
    ]
    bandwidths = [
        8,
        9,
        10,
    ]

    for f, s, n, r, bw in product(figures, source, normalize, recategorize, bandwidths):
        options.update(
            to_plot=[f], ar6_data=s, normalize=n, recategorize=r, bandwidth=bw
        )

        try:
            ctx.invoke(plot, **options)
        except Exception:
            # Print the exception, but continue
            print()
            print_exc()
            print()


@cli.command()
def prepare():
    """Prepare files for submission.

    Results are stored in OUTPUT_PATH/submission/.
    """
    import shutil
    from zipfile import ZipFile

    import requests

    base_path = OUTPUT_PATH / "submission"
    print(base_path)
    base_path.mkdir(exist_ok=True)

    for final_id, info in FINAL.items():
        basename = f"Figure-{final_id}"

        zf_name = base_path.joinpath(f"{basename}-data.zip")
        with ZipFile(zf_name, mode="w") as zf:
            for i, id in enumerate(info["ids"]):
                # Raw/vector graphics
                from_ = OUTPUT_PATH.joinpath(f"{id}.pdf")
                to_ = base_path.joinpath(f"{basename}-vector-{i}.pdf")

                print(f"Copy {from_} to {to_}")
                shutil.copyfile(from_, to_)

                # Data
                from_ = OUTPUT_PATH.joinpath("data", f"{id}.zip")
                print(f"Add {from_} to {zf_name}")
                zf.write(from_, arcname=f"{basename}-data-0.zip")

                # Data README
                print(f"Add README to {zf_name}")
                zf.writestr(
                    "README.txt",
                    DATA_PATH.joinpath("README-1.template")
                    .read_text()
                    .format(final_id=final_id, basename=basename),
                )

    # Mirror code
    URL = (
        "https://github.com/transportenergy/ipcc-ar6-wg3-ch10/archive/refs/heads/"
        "master.zip"
    )
    to_ = base_path.joinpath("Section-10.7-code.zip")

    print(f"Download {URL} to {to_}")

    with open(to_, "wb") as fd:
        for chunk in requests.get(URL).iter_content(chunk_size=4096):
            fd.write(chunk)


@cli.command()
def refs():
    """Retrieve reference files to ref/."""
    from .cache import get_references

    get_references()


@cli.command()
@click.option("--go", is_flag=True)
def upload(go):
    """Sync output/ to a remote directory using rclone.

    \b
    Requires the following configuration:
    - Rclone installed from https://rclone.org.
    - At least one remote configured.
    - In config.json, a key 'rclone' and sub-key 'output' with a destination
      ("remote:path").
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

    The lists are written to data/variables-SOURCE-all.txt. These lists are *manually*
    trimmed to variables-SOURCE.txt, which in turn are used to filter data imports.
    """
    _start_log()

    from .data import DATA_PATH, LOCAL_DATA, get_data

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
