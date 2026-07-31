"""The processing ledger: one row per stage, in execution order.

Shaped after the CONSORT flow diagram that reviewers already know how to read.
Every stage that removes or changes anything appears, including the ones that
are easy to forget -- reading the file, parsing the dates, building the derived
columns -- so the chain of row counts is continuous and a gap in it is visible
rather than inferred.

For each field named in ``unique_report`` (animal_id by default) the ledger
also carries ``_in``, ``_affected`` and ``_out`` counts of distinct values.
``_in`` minus ``_out`` is the number of animals that left the study entirely at
that stage, which is the figure a reviewer asks for and the one the old
pipeline never computed.
"""

from __future__ import annotations

import pandas as pd


class Statistics:
    """Accumulates the ledger rows; `frame` renders them."""

    def __init__(self, unique_report):
        self.unique_report = tuple(unique_report)
        self._rows = []

    def record(self, step, action, before, after, affected=None,
               column="", detail=""):
        """Record one stage.

        *before* and *after* are the frames on either side of it; *affected* is
        the boolean mask of rows it removed or rewrote, or None for a stage
        that only observes.
        """
        row = {
            "step": step,
            "action": action,
            "column": column,
            "detail": detail,
            "rows_in": len(before),
            "rows_affected": 0 if affected is None else int(affected.sum()),
            "rows_out": len(after),
        }
        for name in self.unique_report:
            row[name + "_in"] = _distinct(before, name)
            row[name + "_affected"] = (
                0 if affected is None else _distinct(before.loc[affected], name))
            row[name + "_out"] = _distinct(after, name)
        self._rows.append(row)

    def frame(self):
        """The ledger as a tidy DataFrame."""
        return pd.DataFrame(self._rows)

    def render(self):
        """The ledger as text, for the console and the run log."""
        table = self.frame()
        if table.empty:
            return "(no steps recorded)"
        columns = ["step", "action", "column", "rows_in", "rows_affected", "rows_out"]
        for name in self.unique_report:
            columns.append(name + "_in")
            columns.append(name + "_out")
        return table[columns].to_string(index=False)


def _distinct(frame, column):
    """Distinct non-missing values, or 0 when the column is not present.

    Absent rather than empty matters here: a unique_report field is allowed to
    be a column that some stages have not built yet.
    """
    if column not in frame.columns:
        return 0
    return int(frame[column].nunique(dropna=True))
