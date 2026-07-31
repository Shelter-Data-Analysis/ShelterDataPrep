"""Command line entry point: ``python -m shelterprep <settings.yaml>``."""

from __future__ import annotations

import argparse
import sys

from .pipeline import Prep, SourceError
from .settings import SettingsError, load


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="shelterprep",
        description="Prepare an animal shelter data file from a YAML settings file.")
    parser.add_argument("settings", help="path to the YAML settings file")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="do not print the statistics table")
    args = parser.parse_args(argv)

    try:
        Prep(load(args.settings)).run(verbose=not args.quiet)
    except (SettingsError, SourceError) as error:
        print("error: {0}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
