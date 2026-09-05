"""The one date rule in this package.

Every date-valued thing here is a naive ``datetime64``.  Never
``datetime.date``, never tz-aware, never a mix.  The resolution is pandas's
to choose: pandas 2 gives ``[ns]``, pandas 3 infers ``[us]`` from strings, and
nothing here depends on which.

This is not a stylistic preference.  The stale pipeline round-tripped date
columns through ``.dt.date`` and then compared the result against
``datetime64`` columns and against a ``datetime.date`` sampling axis.  pandas
2 rejects that outright::

    TypeError: Invalid comparison between dtype=datetime64[ns] and date

Normalizing to midnight keeps the dtype uniform while discarding the time,
which is what "a date with no time attached" ought to mean in pandas.  Values
only leave this representation at the very end, in `to_iso`, on their way to
the output file.
"""

from __future__ import annotations

import pandas as pd

#: Accepts both ``2018-03-02`` and ``2018-03-02 14:30:00``.  See `to_datetime`.
ISO8601 = "ISO8601"

#: Additionally accepts US-style ``m/d/Y``, at the cost of guessing on days
#: that could be either the month or the day.
MIXED = "mixed"

DATE_FORMATS = (ISO8601, MIXED)


def to_datetime(values, date_format=ISO8601, keep_time=False):
    """Parse *values* to a naive ``datetime64``; unparseable entries become ``NaT``.

    The explicit ``date_format`` is load-bearing, not decorative.  Left to
    infer, pandas locks onto one format from the first non-null value and
    silently coerces everything that disagrees with it::

        >>> s = pd.Series(["2018-01-01 14:30:00", "2018-03-02"])
        >>> list(pd.to_datetime(s, errors="coerce"))
        [Timestamp('2018-01-01 14:30:00'), NaT]

    A whole row would disappear from the study with no warning.  ``"ISO8601"``
    accepts both of those spellings; the caller counts whatever still fails and
    records it in the statistics table.

    With ``keep_time`` false (the default) the time component is dropped but
    the dtype is unchanged, so the result still compares cleanly against every
    other date in the package.
    """
    parsed = pd.to_datetime(values, format=date_format, errors="coerce")
    parsed = _drop_timezone(parsed, values, date_format)
    return parsed if keep_time else parsed.dt.normalize()


def _drop_timezone(parsed, values, date_format):
    """Force a tz-aware or mixed-offset parse back to a naive ``datetime64``.

    Some exports stamp an offset on every value -- the LA County open-data
    extract writes ``2021/09/14 07:00:00+00``, which is local midnight
    expressed in UTC.  pandas returns ``datetime64[ns, UTC]`` for that, or
    ``object`` when the offsets are not uniform.  Either would quietly break
    the rule this module exists to enforce, and the breakage would surface far
    away, as a comparison that no longer works.

    The UTC wall clock is kept as the naive value, so the calendar date is the
    one the export encoded.  For an extract that means local midnight -- the
    common case, and true of LA County -- that is the intended date.
    """
    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_localize(None)
    if parsed.dtype == object:
        # Mixed offsets: normalize to UTC first, then drop the zone.
        coerced = pd.to_datetime(values, format=date_format,
                                 errors="coerce", utc=True)
        return coerced.dt.tz_localize(None)
    return parsed


def to_timestamp(value):
    """Coerce a single settings value to a midnight ``Timestamp``.

    PyYAML turns an unquoted ``2018-07-01`` into a ``datetime.date``, which is
    precisely the type this package refuses to let anywhere near a DataFrame.
    Every date arriving from settings goes through here.
    """
    return pd.Timestamp(value).normalize()


def nights_between(start, end):
    """Whole nights from *start* to *end*, as nullable ``Int64``.

    Both sides are normalized first, so enabling ``keep_time`` can never shift
    a night count.  ``Int64`` rather than ``int`` because an animal still in
    care has no outcome date, and that absence must stay distinguishable from
    a stay of zero nights.

    Note this counts *nights*, not length of stay: an animal that arrives and
    leaves the same day scores 0 here.  mLOS defines ``LOS = nights + 1`` and
    derives it from the two dates itself.
    """
    delta = end.dt.normalize() - start.dt.normalize()
    return delta.dt.days.astype("Int64")


def to_iso(values):
    """Render a ``datetime64`` column as ``YYYY-MM-DD``; ``NaT`` becomes empty.

    ``.dt.strftime`` renders ``NaT`` as the float ``nan``, which ``to_csv``
    would then write as the string ``nan``.  Masking it back to the empty
    string keeps a missing outcome date genuinely blank in the output.
    """
    rendered = values.dt.strftime("%Y-%m-%d")
    return rendered.where(values.notna(), "")
