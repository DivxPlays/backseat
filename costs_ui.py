"""Costs window: what he has cost you this month, per day and per kind of call."""
import calendar
from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QWidget

import config

GROUPS = [("Talking to him", {"ask", "look", "heard", "clip"}), ("Automatic comments", {"change", "quiet", "lore", "nag", "start"}),
          ("Post-match breakdowns", {"breakdown"}), ("Battle reports", {"report"}),
          ("Music (Spotify comments and song lookups)", {"music"})]


def summary(total, days, today):
    """(today's cost, month-end estimate, [(what it went to, dollars)] biggest first)."""
    by = {}
    for kinds in days.values():
        for kind, dollars in kinds.items():
            name = next((n for n, ks in GROUPS if kind in ks), "Other")
            by[name] = by.get(name, 0.0) + dollars
    if total - sum(by.values()) > 0.005:
        by["Before daily tracking"] = total - sum(by.values())
    first = min(days, default=today.day)  # count from the first day he cost anything, not the 1st
    per_day = total / (today.day - first + 1)
    estimate = total + per_day * (calendar.monthrange(today.year, today.month)[1] - today.day)
    return sum(days.get(today.day, {}).values()), estimate, sorted(by.items(), key=lambda kv: -kv[1])


class DayBars(QWidget):
    def __init__(self, values, today):
        super().__init__()
        self.values, self.today = values, today  # dollars per day of the month, index 0 = the 1st
        self.setMinimumSize(360, 120)

    def paintEvent(self, _):
        g = QPainter(self)
        w, h, top = self.width() / len(self.values), self.height() - 16, max(self.values + [0.01])
        g.setFont(QFont("Segoe UI", 7))
        for i, v in enumerate(self.values):
            bar = h * v / top
            g.fillRect(QRectF(i * w + 1, h - bar, w - 2, bar), QColor("#e0a040" if i + 1 == self.today else "#9a6a3a"))
            if i == 0 or (i + 1) % 5 == 0 or i + 1 == self.today:
                g.setPen(QColor("#e0a040" if i + 1 == self.today else "#888888"))
                g.drawText(QRectF(i * w - 8, h + 2, w + 16, 14), Qt.AlignHCenter, str(i + 1))
        g.end()


class CostsWindow(QDialog):
    def __init__(self, mem):
        super().__init__()
        today = date.today()
        total, days = mem.month_costs()
        today_cost, estimate, groups = summary(total, days, today)
        budget = config.MONTHLY_BUDGET
        self.setWindowTitle(f"{config.NAME}'s cost, {today:%B %Y}")
        lay = QVBoxLayout(self)
        big = QLabel(f"${total:.2f}" + (f" of ${budget}" if budget else "") + " this month")
        big.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lay.addWidget(big)
        if budget:
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(min(1.0, total / budget) * 1000))
            bar.setFormat(f"{total / budget:.0%} of your budget")
            lay.addWidget(bar)
        lay.addWidget(QLabel(f"Today: ${today_cost:.2f}      Month-end estimate: ${estimate:.2f}"))
        lay.addSpacing(8)
        lay.addWidget(QLabel("<b>Per day</b>"))
        lay.addWidget(DayBars([sum(days.get(d, {}).values()) for d in range(1, calendar.monthrange(today.year, today.month)[1] + 1)],
                              today.day))
        lay.addSpacing(8)
        lay.addWidget(QLabel("<b>What it went to</b>"))
        for name, dollars in groups:
            lay.addWidget(QLabel(f"{name}: ${dollars:.2f} ({dollars / total if total else 0:.0%})"))
        if not groups:
            lay.addWidget(QLabel("Nothing yet this month."))
        note = QLabel("These are his estimates from token counts. The Anthropic Console has the real bill.")
        note.setStyleSheet("color: gray")
        lay.addSpacing(8)
        lay.addWidget(note)
