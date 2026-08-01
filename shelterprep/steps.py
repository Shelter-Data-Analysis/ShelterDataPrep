"""Applying one filter or mapping step.

`selection` works out which rows a step will touch; `apply` touches them.
Nothing calls `apply` without having recorded the statistics from `selection`
first, which is the whole reason the split exists: the numbers in the ledger
describe the frame the step actually saw, not a frame reconstructed afterwards.

`breakdown` is the third of the trio and reads the same masks a second time,
splitting a step's work across the individual values its settings name.
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


def breakdown(frame, step, chosen):
    """How a step's work splits across each value its settings name.

    One entry per (role, column, value) mentioned anywhere in *step*, as
    ``(role, column, value, scope, mask)``.  A value that matched nothing comes
    back with an empty mask rather than not at all, which is the point of the
    function: the safeguard entries -- labels kept in a settings file so that a
    future extract carrying them is mapped rather than passed through -- are
    exactly the ones a summary of what did occur cannot show.

    Within one column the masks partition their scope, because a row holds one
    value at a time.  So the counts for a column add up to the count of the
    scope, and a set that does not add up says a value is missing from it.

    A conjunction is reported one part at a time: `cut: {a: [...], b: [...]}`
    gives counts for a and counts for b over the same rows, not counts for the
    pairs.  Both add up to the same total.
    """
    entries = []

    def add(role, scope, conditions, within):
        for column, values in conditions.items():
            for value in sorted(values):
                entries.append(
                    (role, column, value, scope, within & frame[column].isin([value])))

    if isinstance(step, Cut):
        add("cut", "rows cut", step.conditions, chosen)
        return entries

    if isinstance(step, Map):
        # The table's keys are a value set like any other, and the one most
        # likely to be carrying safeguard entries.
        add("map from", "rows mapped", {step.column: frozenset(step.table)}, chosen)
        add("where", "rows mapped", step.where, chosen)
        if step.where_not:
            # Counted over the rows the guard held back, not over the rows
            # mapped: a where_not value cannot appear in a mapped row (that is
            # what the guard did), so counting it there would report zero for
            # every value and say nothing about which of them fired.
            add("where_not", "rows excluded by where_not", step.where_not,
                frame[step.column].isin(step.table)
                & matches(frame, step.where)
                & matches(frame, step.where_not))
        return entries

    # Dedup: `on` names columns rather than values, so only the guards have
    # anything to break down.
    add("where", "rows dropped", step.where, chosen)
    if step.where_not:
        add("where_not", "rows excluded by where_not", step.where_not,
            matches(frame, step.where) & matches(frame, step.where_not))
    return entries


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
