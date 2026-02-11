from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QLabel, QToolTip, QVBoxLayout, QWidget

from sitalarm.services.stats_service import DaySummary


def _format_minutes(value: int) -> str:
    hours, minutes = divmod(max(0, value), 60)
    if hours > 0:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"


class BarChartWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int]] = []
        self._bars: list[tuple[QRectF, str, int]] = []
        self.setMinimumHeight(220)
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
        margin = 28
        chart_rect = QRectF(margin, margin, width - margin * 2, height - margin * 2)

        self._bars.clear()
        painter.setPen(QPen(QColor(132, 162, 199, 190), 1.2))
        painter.setBrush(QColor(255, 255, 255, 70))
        painter.drawRoundedRect(chart_rect, 10, 10)

        if not self._data:
            painter.setPen(QColor(48, 75, 108, 220))
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
            painter.setBrush(QColor(104, 188, 255, 210))
            painter.drawRoundedRect(bar_rect, 6, 6)

            painter.setPen(QColor(42, 67, 98, 232))
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
        QToolTip.showText(event.globalPos(), f"{label}: {value} 分钟\n({_format_minutes(value)})", self)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        QToolTip.hideText()
        super().leaveEvent(event)


class PieChartWidget(QWidget):
    COLORS = [QColor("#67C9FF"), QColor("#FFB26A"), QColor("#C6CBD6")]

    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int]] = []
        self._slice_regions: list[tuple[float, float, str, int]] = []
        self._pie_center = QPointF()
        self._pie_radius = 0.0
        self.setMinimumHeight(220)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self._slice_regions.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pie_size = min(self.width() * 0.52, self.height() - 20)
        pie_size = max(150.0, pie_size)
        pie_size = min(pie_size, min(self.width() - 32, self.height() - 20))
        rect = QRectF(12, 10, pie_size, pie_size)

        self._pie_center = rect.center()
        self._pie_radius = rect.width() / 2
        self._slice_regions.clear()

        total = sum(value for _, value in self._data)
        if total <= 0:
            painter.setPen(QColor(48, 75, 108, 220))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无占比数据")
            return

        start_angle = 0.0
        for idx, (label, value) in enumerate(self._data):
            if value <= 0:
                continue

            span = 360.0 * value / total
            painter.setPen(QPen(QColor(148, 172, 207, 190), 1.2))
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.drawPie(rect, int(start_angle * 16), int(span * 16))
            self._slice_regions.append((start_angle, start_angle + span, label, value))
            start_angle += span

        legend_x = rect.right() + 18
        legend_y = 18
        for idx, (label, value) in enumerate(self._data):
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.drawRoundedRect(QRectF(legend_x, legend_y + idx * 28, 14, 14), 2, 2)
            painter.setPen(QColor(42, 67, 98, 232))
            painter.drawText(QPointF(legend_x + 22, legend_y + 12 + idx * 28), f"{label}: {value} 分钟")

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
                    f"{label}: {value} 分钟\n({_format_minutes(value)})",
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
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("近 7 天正确坐姿时长（分钟）"))
        self.bar_chart = BarChartWidget()
        layout.addWidget(self.bar_chart)

        layout.addWidget(QLabel("今日状态占比（分钟）"))
        self.pie_chart = PieChartWidget()
        layout.addWidget(self.pie_chart)

    def update_statistics(self, history: list[DaySummary], today_summary: DaySummary) -> None:
        bar_data = [(item.day.strftime("%m-%d"), item.correct_minutes) for item in history]
        self.bar_chart.set_data(bar_data)

        pie_data = [
            ("正确", today_summary.correct_minutes),
            ("错误", today_summary.incorrect_minutes),
            ("未知", today_summary.unknown_minutes),
        ]
        self.pie_chart.set_data(pie_data)
