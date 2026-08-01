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

Underneath the ledger sits a second table at a finer grain: one row per value
named in the settings, counted within the rows that step actually cut or
mapped.  A stage row says a cut removed 147,385 rows; a detail row says how
many of those were CAT and how many were BIRD, and shows the zero against a
value that occurs nowhere.  `report` stacks the two into one frame -- one file
rather than two -- distinguished by a leading ``section`` column.
"""

from __future__ import annotations

import pandas as pd


class Statistics:
    """Accumulates the ledger rows; `frame` renders them."""

    def __init__(self, unique_report):
        self.unique_report = tuple(unique_report)
        self._rows = []
        self._details = []

    def record(self, step, action, before, after, affected=None,
               column="", detail="", breakdown=()):
        """Record one stage.

        *before* and *after* are the frames on either side of it; *affected* is
        the boolean mask of rows it removed or rewrote, or None for a stage
        that only observes.  *breakdown* is what `steps.breakdown` returned for
        the same step, or nothing for a stage that names no values.
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

        for role, name, value, scope, mask in breakdown:
            item = {
                "step": step,
                "action": action,
                "column": name,
                "role": role,
                "value": value,
                "scope": scope,
                "rows_affected": int(mask.sum()),
            }
            for field in self.unique_report:
                item[field + "_affected"] = _distinct(before.loc[mask], field)
            self._details.append(item)

    # -- the two tables -----------------------------------------------------

    def frame(self):
        """The ledger as a tidy DataFrame: one row per stage."""
        return pd.DataFrame(self._rows, columns=self._stage_columns())

    def details(self):
        """The value-level table: one row per value the settings name."""
        return pd.DataFrame(self._details, columns=self._detail_columns())

    def report(self):
        """Both tables in one frame, the detail stacked underneath.

        Stacked rather than written side by side or to a second file: the two
        share most of their columns, and one CSV that `read_csv` still opens is
        worth more than a tidier layout that it does not.  Columns belonging to
        the other section are left empty, and ``section`` selects between them.
        """
        stages = self.frame()
        stages.insert(0, "section", "stage")
        details = self.details()
        details.insert(0, "section", "detail")

        counts = ["rows_in", "rows_affected", "rows_out"]
        for name in self.unique_report:
            counts += [name + "_in", name + "_affected", name + "_out"]
        order = ["section", "step", "action", "column",
                 "role", "value", "scope", "detail"] + counts

        combined = pd.concat([stages, details], ignore_index=True)
        combined = combined.reindex(columns=order)
        for name in ("role", "value", "scope", "detail"):
            combined[name] = combined[name].fillna("")
        # Nullable integers, so a count missing from one section writes as a
        # blank cell rather than turning the whole column into 12345.0.
        combined[counts] = combined[counts].astype("Int64")
        return combined

    # -- text ---------------------------------------------------------------

    def render(self):
        """Both tables as text, for the console and the run log."""
        stages = self.frame()
        if stages.empty:
            return "(no steps recorded)"
        columns = ["step", "action", "column", "rows_in", "rows_affected", "rows_out"]
        for name in self.unique_report:
            columns.append(name + "_in")
            columns.append(name + "_out")
        text = stages[columns].to_string(index=False)

        details = self.details()
        if details.empty:
            return text
        columns = ["step", "action", "column", "role", "value", "scope",
                   "rows_affected"]
        for name in self.unique_report:
            columns.append(name + "_affected")
        return "\n\n".join([
            text,
            "by value -- every value the settings name, counted within the "
            "rows of the scope:",
            details[columns].to_string(index=False),
        ])

    # -- column orders ------------------------------------------------------

    def _stage_columns(self):
        columns = ["step", "action", "column", "detail",
                   "rows_in", "rows_affected", "rows_out"]
        for name in self.unique_report:
            columns += [name + "_in", name + "_affected", name + "_out"]
        return columns

    def _detail_columns(self):
        columns = ["step", "action", "column", "role", "value", "scope",
                   "rows_affected"]
        for name in self.unique_report:
            columns.append(name + "_affected")
        return columns


def _distinct(frame, column):
    """Distinct non-missing values, or 0 when the column is not present.

    Absent rather than empty matters here: a unique_report field is allowed to
    be a column that some stages have not built yet.
    """
    if column not in frame.columns:
        return 0
    return int(frame[column].nunique(dropna=True))
