"""Applying one filter or mapping step.

The two functions here are deliberately separate.  `selection` works out which
rows a step will touch; `apply` touches them.  Nothing calls `apply` without
having recorded the statistics from `selection` first, which is the whole
reason the split exists: the numbers in the ledger describe the frame the step
actually saw, not a frame reconstructed afterwards.
"""

from __future__ import annotations

import pandas as pd

from .settings import Cut, Dedup, Map


def matches(frame, conditions):
    """AND of "this column's value is in this set", across ``conditions``.

    Empty conditions match every row, which is what makes an absent ``where:``
    behave as no restriction at all.
    """
    mask = pd.Series(True, index=frame.index)
    for column, values in conditions.items():
        mask &= frame[column].isin(values)
    return mask


def _restrict(frame, step):
    """The rows a map or dedup step is allowed to touch."""
    eligible = pd.Series(True, index=frame.index)
    if step.where:
        eligible &= matches(frame, step.where)
    if step.where_not:
        # Guarded: an empty where_not would negate to all-False and silence
        # the whole step, rather than leaving it unrestricted.
        eligible &= ~matches(frame, step.where_not)
    return eligible


def selection(frame, step):
    """The rows *step* will remove (cut, dedup) or rewrite (map)."""
    if isinstance(step, Cut):
        return matches(frame, step.conditions)

    if isinstance(step, Dedup):
        chosen = pd.Series(False, index=frame.index)
        eligible = frame.loc[_restrict(frame, step)]
        # The LAST row of each group survives and the earlier ones are cut.
        # When the compared columns are a subset, the rows can differ in the
        # columns not compared, and a later record is far more likely to be a
        # correction of an earlier one than the reverse. It also matches how
        # mLOS breaks the same tie: "of two equal stays, the one earlier in
        # the file is dropped".
        repeats = eligible.duplicated(subset=list(step.on), keep="last")
        chosen.loc[eligible.index] = repeats.to_numpy()
        return chosen

    return frame[step.column].isin(step.table) & _restrict(frame, step)


def apply(frame, step, chosen):
    """Return a new frame with *step* applied to the *chosen* rows."""
    if isinstance(step, (Cut, Dedup)):
        return frame.loc[~chosen].copy()

    if not isinstance(step, Map):
        raise TypeError("unknown step type {0!r}".format(type(step)))

    result = frame.copy()
    # Every chosen row is in the table by construction, so no unmapped value
    # can leak through as NaN here.
    result.loc[chosen, step.column] = result.loc[chosen, step.column].map(step.table)
    return result
