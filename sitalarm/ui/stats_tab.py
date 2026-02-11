from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from sitalarm.services.stats_service import DaySummary


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours} 小时 {minutes} 分钟 {secs} 秒"
    if minutes > 0:
        return f"{minutes} 分钟 {secs} 秒"
    return f"{secs} 秒"


def _format_hhmmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class BarChartWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int]] = []
        self._bars: list[tuple[QRectF, str, int]] = []
        self.setMinimumHeight(160)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self._bars.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 24
        chart_rect = QRectF(margin, margin, width - margin * 2, height - margin * 2)

        self._bars.clear()
        painter.setPen(QPen(QColor(15, 23, 42, 26), 1.2))
        painter.setBrush(QColor(255, 255, 255, 140))
        painter.drawRoundedRect(chart_rect, 10, 10)

        if not self._data:
            painter.setPen(QColor(15, 23, 42, 140))
            painter.drawText(chart_rect, Qt.AlignCenter, "暂无数据")
            return

        max_value = max(max(value for _, value in self._data), 1)
        count = len(self._data)
        bar_space = chart_rect.width() / count
        bar_width = bar_space * 0.58

        for idx, (label, value) in enumerate(self._data):
            x = chart_rect.left() + idx * bar_space + (bar_space - bar_width) / 2
            ratio = value / max_value
            h = chart_rect.height() * ratio
            y = chart_rect.bottom() - h

            bar_rect = QRectF(x, y, bar_width, h)
            self._bars.append((bar_rect, label, value))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(6, 182, 212, 200))
            painter.drawRoundedRect(bar_rect, 6, 6)

            painter.setPen(QColor(15, 23, 42, 180))
            painter.drawText(QRectF(x - 6, chart_rect.bottom() + 2, bar_space + 12, 20), Qt.AlignCenter, label)
            painter.drawText(QRectF(x - 4, max(chart_rect.top() - 4, y - 20), bar_width + 8, 18), Qt.AlignCenter, str(value))

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        hovered = None
        for rect, label, value in self._bars:
            if rect.contains(event.pos()):
                hovered = (label, value)
                break

        if hovered is None:
            QToolTip.hideText()
            return

        label, value = hovered
        # value in minutes for bar chart
        QToolTip.showText(event.globalPos(), f"{label}: {value} 分钟\n({_format_duration(value * 60)})", self)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        QToolTip.hideText()
        super().leaveEvent(event)


class PieChartWidget(QWidget):
    COLORS = [QColor("#06b6d4"), QColor("#3b82f6"), QColor("#94a3b8")]

    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int]] = []
        self._slice_regions: list[tuple[float, float, str, int]] = []
        self._pie_center = QPointF()
        self._pie_radius = 0.0
        self.setMinimumHeight(160)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self._slice_regions.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pie_size = min(self.width() * 0.52, self.height() - 20)
        pie_size = max(120.0, pie_size)
        pie_size = min(pie_size, min(self.width() - 32, self.height() - 20))
        rect = QRectF(12, 10, pie_size, pie_size)

        self._pie_center = rect.center()
        self._pie_radius = rect.width() / 2
        self._slice_regions.clear()

        total = sum(value for _, value in self._data)
        if total <= 0:
            painter.setPen(QColor(15, 23, 42, 140))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无占比数据")
            return

        start_angle = 0.0
        for idx, (label, value) in enumerate(self._data):
            if value <= 0:
                continue

            span = 360.0 * value / total
            painter.setPen(QPen(QColor(15, 23, 42, 22), 1.2))
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.drawPie(rect, int(start_angle * 16), int(span * 16))
            self._slice_regions.append((start_angle, start_angle + span, label, value))
            start_angle += span

        legend_x = rect.right() + 16
        legend_y = 16
        for idx, (label, value) in enumerate(self._data):
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.drawRoundedRect(QRectF(legend_x, legend_y + idx * 26, 12, 12), 2, 2)
            painter.setPen(QColor(15, 23, 42, 180))
            painter.drawText(QPointF(legend_x + 18, legend_y + 10 + idx * 26), f"{label}: {_format_hhmmss(value)}")

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._pie_radius <= 0:
            QToolTip.hideText()
            return

        dx = event.pos().x() - self._pie_center.x()
        dy = event.pos().y() - self._pie_center.y()
        distance = math.hypot(dx, dy)

        if distance > self._pie_radius:
            QToolTip.hideText()
            return

        angle = math.degrees(math.atan2(-dy, dx))
        angle = (angle + 360.0) % 360.0

        # Qt drawPie 以 3 点钟方向为 0 度，逆时针增加，转换后保持一致。
        for start, end, label, value in self._slice_regions:
            if start <= angle < end:
                QToolTip.showText(
                    event.globalPos(),
                    f"{label}: {_format_hhmmss(value)}\n({_format_duration(value)})",
                    self,
                )
                return

        QToolTip.hideText()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        QToolTip.hideText()
        super().leaveEvent(event)


class StatsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("PageScrollArea")
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("PageContent")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 16)

        layout.addWidget(QLabel("近 7 天在屏幕前时长（分钟，= 正确 + 错误）"))
        self.bar_chart = BarChartWidget()
        layout.addWidget(self.bar_chart)

        layout.addWidget(QLabel("今日状态占比（时长）"))
        self.pie_chart = PieChartWidget()
        layout.addWidget(self.pie_chart)

        layout.addWidget(QLabel("每日明细（近 7 天）"))
        self.daily_table = QTableWidget(0, 6)
        self.daily_table.setHorizontalHeaderLabels(["日期", "在屏幕前", "正确", "错误", "正确占比", "错误占比"])
        self.daily_table.verticalHeader().setVisible(False)
        self.daily_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.daily_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.daily_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.daily_table.setAlternatingRowColors(True)
        self.daily_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.daily_table.setMinimumHeight(180)
        layout.addWidget(self.daily_table)
        layout.addStretch(1)

    def update_statistics(self, history: list[DaySummary], today_summary: DaySummary) -> None:
        # Bar chart uses minutes for readability.
        bar_data = []
        for item in history:
            front_seconds = item.correct_seconds + item.incorrect_seconds
            bar_data.append((item.day.strftime("%m-%d"), int(front_seconds // 60)))
        self.bar_chart.set_data(bar_data)

        pie_data = [
            ("正确", today_summary.correct_seconds),
            ("错误", today_summary.incorrect_seconds),
            ("未知", today_summary.unknown_seconds),
        ]
        self.pie_chart.set_data(pie_data)

        # Daily breakdown table
        self.daily_table.setRowCount(len(history))
        for row_idx, item in enumerate(history):
            correct = int(item.correct_seconds)
            incorrect = int(item.incorrect_seconds)
            front_total = correct + incorrect

            correct_pct = (correct / front_total * 100.0) if front_total > 0 else 0.0
            incorrect_pct = (incorrect / front_total * 100.0) if front_total > 0 else 0.0

            cells = [
                QTableWidgetItem(item.day.strftime("%Y-%m-%d")),
                QTableWidgetItem(_format_hhmmss(front_total)),
                QTableWidgetItem(_format_hhmmss(correct)),
                QTableWidgetItem(_format_hhmmss(incorrect)),
                QTableWidgetItem(f"{correct_pct:.1f}%"),
                QTableWidgetItem(f"{incorrect_pct:.1f}%"),
            ]

            # Extra info via tooltip (include unknown)
            unknown = int(item.unknown_seconds)
            tooltip = (
                f"日期：{item.day.isoformat()}\n"
                f"在屏幕前：{_format_duration(front_total)}\n"
                f"正确：{_format_duration(correct)}\n"
                f"错误：{_format_duration(incorrect)}\n"
                f"未知：{_format_duration(unknown)}"
            )
            for col, cell in enumerate(cells):
                cell.setToolTip(tooltip)
                cell.setTextAlignment(Qt.AlignCenter)
                self.daily_table.setItem(row_idx, col, cell)
