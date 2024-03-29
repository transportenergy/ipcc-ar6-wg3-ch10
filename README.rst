Plotting & other codes for Ch.10 “Transport” of IPCC AR6 WGIII
**************************************************************

Contents: Important links & notes
— `Running the code <#running-the-code>`__
— `CLI --help text <#cli-help-text>`__
— `History <#history>`__
— `References <#references>`__

This code generates plots used in figures in Chapter 10, mainly Section 10.7,
titled “Scenarios from integrated, sectoral, and regional models”. The code does
not generate other Chapter 10 plots or figures not mentioned.

The code, including its entire edit history, is available on GitHub at:
https://github.com/transportenergy/ipcc-ar6-wg3-ch10

- Each plot responds to multiple configuration options; thus, there are at least
  30 variants of each plot, many with multiple pages (one per spatial region).

  The figures in the final text of Chapter 10 each contain **1 or more** pages
  from **1 or 2** variants of each plot, selected to best support the assessment
  text. The commands which will generate the specific plots used in the figures
  are:

  - **Figure 10.14**: ``fig_9``, created using:
    ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw10 9``
  - **Figure 10.17**: ``fig_10``, created using:

    - ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw10 9`` (IAM scenarios; i.e. same as Figure 10.14, but a different page)
    - ``python -m ar6_wg3_ch10 plot --tem-data=IMO --bw=8 10`` (IMO scenarios)
  - **Figure 10.18**: ``fig_1``, created using:

    - ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw=9 1`` (world panel)
    - ``python -m ar6_wg3_ch10 plot --ar6-data=R6 --bw=9 1`` (regional panels)

  - **Figure 10.19**: ``fig_2``, created using:

    - ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw=9 2`` (world panel)
    - ``python -m ar6_wg3_ch10 plot --ar6-data=R6 --bw=9 2`` (regional panels)

  - **Figure 10.20**: ``fig_6``, created using:
    ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw=8 --recat=A 6``.
  - **Figure 10.21**: ``fig_4``, created using:
    ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw=9 4``.
  - **Figure 10.22**: ``fig_7``, created using:
    ``python -m ar6_wg3_ch10 plot --ar6-data=world --bw=9 --recat=A 7``.
  - **Figure 10.23** (in Box 10.5): ``fig_8``, created using:
    ``python -m ar6_wg3_ch10 plot --ar6-data=IP 8``.

- Earlier versions of figures used by the chapter authors in earlier drafts of
  the report are uploaded on
  `Box.com <https://app.box.com/folder/92464968722>`__ (access for report
  contributors only), in the ``7 Scenarios/plots/`` folder.

  - Subfolders are named by date.
  - There are multiple variants of each figure, as indicated by the file name:

    - ``AR6-world``, ``AR6-R5``, ``AR6-R10``, ``AR6-country``—these indicate
      which snapshot of data from the AR6 database is used.

  - Each dated folder contains a ``data/`` subfolder with ZIP files containing
    CSV dumps of the data used each plot.
    The file names match figure file names, with additions, e.g.:

    - ``_plot.csv``: the actual values, e.g. descriptive statistics (median
      etc.) displayed in the plot.
    - ``_iam.csv``: the individual scenario values used to compute these
      statistics.
    - ``_indicator.csv``: a subset of scenario values for the Chapter
      3-designated indicator scenarios.
    - ``_tem.csv``: data from the G-/NTEM (sectoral and national) models.

- The file `NOTES.rst <./NOTES.rst>`__ contains some earlier plans and notes,
  not all up to date.
  Refer to the code for latest information, comments, pending ``TODO``s, etc.
  The files all follow a similar pattern.

  For instance, for information on ``fig2``, refer to the file
  `ar6_wg3_ch10/fig_2.py <./ar6_wg3_ch10/fig_2.py>`__.

Running the code
================

Generating all plots
--------------------

1. Download the snapshots from the `AR6 Scenario Explorer <https://data.ene.iiasa.ac.at/ar6-scenario-submission/>`__ website.

   This data is submitted by a variety of parties, and processed in various ways
   by the Chapter 3 team. The code here uses the metadata produced by Chapter 3
   to select data to be plotted.

2. Place the contents in the directory ``data/raw/``.

   Data must be converted to ``.csv.gz`` format, using a process like:

   - Unpack the ``.zip`` snapshot and enter the directory created.
   - Compress the data using the Gzip command-line program, available on most
     \*nix systems: ``gzip *.csv``.
   - Move the file created to ``data/raw/``.

   Refer to the file ``common.py`` for the expected file names.

3. Install requirements: ``pip install -r requirements.txt``

4. Run ``python -m ar6_wg3_ch10 plot-all`` (about 30 minutes) or other commands
  (see below).

Other actions
-------------

To retrieve raw data from the Scenario Explorer API, modify
``config-example.json`` to create a file named ``config.json`` with content
like::

    {
      "credentials": {
        "username": "your-user-name",
        "password": "your-password"
      },
      "remote": {
        "upload": "ipcc:IPCC CH10/7 Scenarios/plots"
      }
    }

(NB. do **not** commit this file to the git repository; your password will
become a permanent part of the history, and you will need to change it.)

.. code-block::

   # Cache all raw data
   $ python -m ar6_wg3_ch10 cache refresh AR6  # about 60 minutes

Note that the final process to generate figures used in the report does not use
this raw data directly, but rather the post-processed "snapshots" provided by
the Chapter 3 team, as mentioned above.

CLI help text
-------------

The top-level CLI and each command provide help text; use ``--help``.
For example, ``python -m ar6_wg3_ch10 --help`` gives:

.. code-block::
   $ python -m ar6_wg3_ch10 --help
   Usage: python -m ar6_wg3_ch10 [OPTIONS] COMMAND [ARGS]...

     Command-line interface for IPCC AR6 WGIII Ch.10 figures.

     Reads a file config.json in the current directory. See config-
     example.json.

     Verbose log information for certain commands is written to a timestamped
     .log file in output/.

   Options:
     --skip-cache  Don't use cached intermediate data.
     --verbose     Also print DEBUG log messages to stdout.
     --help        Show this message and exit.

   Commands:
     clear-cache  Clear cached/intermediate data matching PATTERN.
     count        Count model and scenario names in final data.
     coverage     Report coverage of transport variables.
     debug        Demo or debug code.
     plot         Plot figures, writing to output/.
     plot-all     Generate all plots.
     prepare      Prepare files for submission.
     refs         Retrieve reference files to ref/.
     remote       Retrive data from remote databases to data/cache/SOURCE/.
     upload       Sync output/ to a remote directory using rclone.
     variables    Write lists of variables for each data source.

History
=======

Use ``git log`` on the command line or the “commits” tab on the GitHub website.

References
==========

These are only for convenience; the chapter/section Mendeley collections should
be used to store all key references.

- `AR5 WGIII chapters & figures <https://archive.ipcc.ch/report/ar5/wg3/>`_
