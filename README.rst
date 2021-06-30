Plotting & other codes for Ch.10 “Transport” of IPCC AR6 WGIII
**************************************************************

Contents: Important links & notes
— `Running the code <#running-the-code>`__
— `History <#history>`__
— `References <#references>`__


- Recent figures are uploaded on `Box.com <https://app.box.com/folder/92464968722>`__, in the ``7 Scenarios/plots/`` folder.

  - Subfolders are named by date.
  - There are multiple variants of each figure, as indicated by the file name:

    - ``AR6-world``, ``AR6-R5``, ``AR6-R10``, ``AR6-country``—these indicate which snapshot of data from the AR6 database is used.

  - Each dated folder contains a ``data/`` subfolder with CSV dumps of the data used each plot.
    The file names match figure file names, with additions, e.g.:

    - ``_plot.csv``: the actual values, e.g. descriptive statistics (median etc.) displayed in the plot.
    - ``_iam.csv``: the individual scenario values used to compute these statistics.
    - ``_indicator.csv``: a subset of scenario values for the Chapter 3-designated indicator scenarios.
    - ``_item.csv``: data from the iTEM (sectoral) models.

- The file `NOTES.rst <./NOTES.rst>`__ contains some earlier plans and notes, not all up to date.
  Refer to the code for latest information, comments, pending ``TODO``s, etc.
  The files all follow a similar pattern.

  For instance, for information on ``fig2``, refer to the file `ar6_wg3_ch10/fig_2.py <./ar6_wg3_ch10/fig_2.py>`__.

Running the code
================

Generating all the plots
------------------------

1. Download the snapshots from the AR6 Scenario Explorer website.
2. Place the contents in the directory ``data/raw/``.
3. Run ``python -m ar6_wg3_ch10 all`` (about 20 minutes) or other commands (``python -m ar6_wg3_ch10 --help``).


Other actions
-------------

To retrieve raw data from the Scenario Explorer API, modify ``config-example.json`` to create a file named ``config.json`` with content like::

    {
      "credentials": {
        "username": "your-user-name",
        "password": "your-password"
      },
      "remote": {
        "upload": "ipcc:IPCC CH10/7 Scenarios/plots"
      }
    }

(NB. do **not** commit this file to the git repository; your password will become a permanent part of the history, and you will need to change it.)

Then:

.. code-block::

   $ pip install -r requirements.txt

   # Show help text
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
     all        Generate all plots.
     cache      Retrive data from remote databases to data/cache/SOURCE/.
     coverage   Report coverage per data/coverage-checks.yaml.
     debug      Demo or debug code.
     plot       Plot figures, writing to output/.
     refs       Retrieve reference files to ref/.
     upload     Sync output/ to a remote directory using rclone.
     variables  Write lists of variables for each data source.

   # Cache all raw data
   $ python -m ar6_wg3_ch10 cache refresh AR6  # about 60 minutes

   # Run a particular command
   $ python -m ar6_wg3_ch10 plot


History
=======

Use ``git log`` on the command line or the “commits” tab on the GitHub website.


References
==========

These are only for convenience; the chapter/section Mendeley collections should be used to store all key references.

- `AR5 WGIII chapters & figures <https://archive.ipcc.ch/report/ar5/wg3/>`_
