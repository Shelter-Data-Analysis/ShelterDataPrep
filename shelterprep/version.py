"""The package version, in one place.

Its own module rather than a name in ``__init__``, so that `pipeline` can stamp
it into the run log without importing the package that imports `pipeline`.

A prepared file is only as citable as the thing that produced it, so this
number belongs in every run log.  Bump it whenever a change could move a
number: a new or altered step type, a change to how a derived column is built,
a change to what the ledger counts.
"""

__version__ = "0.2.0"
