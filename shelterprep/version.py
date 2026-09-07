"""The package version, in one place.

Its own module rather than a name in ``__init__``, so that `pipeline` can stamp
it into the run log without importing the package that imports `pipeline`.

A prepared file is only as citable as the thing that produced it, so this
number belongs in every run log.  Bump it whenever a change could move a
number: a new or altered step type, a change to how a derived column is built,
a change to what the ledger counts.

A release that changes only documentation bumps the patch number too, so that
what gets cited has a version of its own.  Those are the releases where a run
of any config still produces byte-identical output, and CHANGELOG.md says which
is which.
"""

__version__ = "0.4.0"
