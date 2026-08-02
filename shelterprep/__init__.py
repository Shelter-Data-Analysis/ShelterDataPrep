"""ShelterDataPrep: config-driven preparation of animal shelter data files.

A run is a YAML settings file.  It says where the extract is, which columns to
keep, and an ordered sequence of filtering and mapping steps.  Out comes a tidy
CSV, a statistics table recording what every step removed or changed, a summary
of the finished set, and a run log for provenance.

    from shelterprep import load, Prep
    Prep(load("configs/orange_county2.yaml")).run()

or from the command line::

    python3 -m shelterprep configs/orange_county2.yaml
"""

from __future__ import annotations

from .pipeline import Prep, SourceError
from .settings import Settings, SettingsError, load
from .version import __version__

__all__ = ["Prep", "Settings", "SettingsError", "SourceError", "load",
           "__version__"]
