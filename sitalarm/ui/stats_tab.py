from __future__ import annotations

import math
from datetime import datetime

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, icon: str, accent: str, value_style: str = "normal") -> None:
        super().__init__()
        self.setObjectName("StatsMetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setObjectName("StatsMetricIcon")
        icon_label.setProperty("accent", accent)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(54, 42)
        layout.addWidget(icon_label, alignment=Qt.AlignLeft)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatsMetricTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatsMetricValue")
        self.value_label.setProperty("accent", accent)
        self.value_label.setProperty("valueStyle", value_style)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class BarChartWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int, int]] = []
        self._bars: list[tuple[QRectF, str, int, int, int]] = []
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int, int]]) -> None:
        self._data = data
        self._bars.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        left_margin = 52
        top_margin = 20
        right_margin = 26
        bottom_margin = 46
        chart_rect = QRectF(
            left_margin,
            top_margin,
            max(0.0, width - left_margin - right_margin),
            max(0.0, height - top_margin - bottom_margin),
        )

        self._bars.clear()
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        grid_color = QColor(148, 163, 184, 70)
        painter.setPen(QPen(grid_color, 1, Qt.DashLine))
        for i in range(5):
            y = chart_rect.top() + chart_rect.height() * i / 4
            painter.drawLine(QPointF(chart_rect.left(), y), QPointF(chart_rect.right(), y))

        if not self._data:
            painter.setPen(QColor(71, 85, 105, 190))
            painter.drawText(chart_rect, Qt.AlignCenter, "暂无数据")
            return

        max_total = max(max(correct + incorrect for _, correct, incorrect in self._data), 1)
        count = len(self._data)
        bar_space = chart_rect.width() / max(count, 1)
        bar_width = min(46.0, bar_space * 0.66)

        for i in range(5):
            y_value = int(round(max_total * (4 - i) / 4))
            y = chart_rect.top() + chart_rect.height() * i / 4
            painter.setPen(QColor(100, 116, 139, 180))
            painter.drawText(QRectF(0, y - 10, left_margin - 8, 20), Qt.AlignRight | Qt.AlignVCenter, str(y_value))

        for idx, (label, correct, incorrect) in enumerate(self._data):
            x = chart_rect.left() + idx * bar_space + (bar_space - bar_width) / 2
            total = correct + incorrect
            total_height = chart_rect.height() * (total / max_total)
            bar_top = chart_rect.bottom() - total_height

            correct_height = total_height * (correct / total) if total > 0 else 0.0
            incorrect_height = total_height - correct_height

            incorrect_rect = QRectF(x, bar_top, bar_width, incorrect_height)
            correct_rect = QRectF(x, bar_top + incorrect_height, bar_width, correct_height)
            total_rect = QRectF(x, bar_top, bar_width, total_height)
            self._bars.append((total_rect, label, correct, incorrect, total))

            # 正确时间 - 橙色 (用户要求：橙色=正确)
            if correct_height > 0:
                correct_gradient = QLinearGradient(correct_rect.topLeft(), correct_rect.bottomLeft())
                correct_gradient.setColorAt(0.0, QColor(251, 146, 60, 240))  # 橙色
                correct_gradient.setColorAt(1.0, QColor(234, 88, 12, 220))   # 深橙色
                painter.setPen(Qt.NoPen)
                painter.setBrush(correct_gradient)
                painter.drawRoundedRect(correct_rect, 8, 8)

            # 错误时间 - 灰白色 (用户要求：灰白色=错误)
            if incorrect_height > 0:
                bad_gradient = QLinearGradient(incorrect_rect.topLeft(), incorrect_rect.bottomLeft())
                bad_gradient.setColorAt(0.0, QColor(209, 213, 219, 240))  # 浅灰
                bad_gradient.setColorAt(1.0, QColor(156, 163, 175, 220))  # 深灰
                painter.setPen(Qt.NoPen)
                painter.setBrush(bad_gradient)
                painter.drawRoundedRect(incorrect_rect, 8, 8)

            painter.setPen(QColor(71, 85, 105, 230))
            painter.drawText(QRectF(x - 8, chart_rect.bottom() + 6, bar_space + 16, 20), Qt.AlignCenter, label)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        hovered = None
        for rect, label, correct, incorrect, total in self._bars:
            if rect.contains(event.pos()):
                hovered = (label, correct, incorrect, total)
                break

        if hovered is None:
            QToolTip.hideText()
            return

        label, correct, incorrect, total = hovered
        QToolTip.showText(
            event.globalPos(),
            (
                f"{label}\n"
                f"正确时间: {correct} 分钟\n"
                f"错误时间: {incorrect} 分钟\n"
                f"总时间: {total} 分钟"
            ),
            self,
        )

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        QToolTip.hideText()
        super().leaveEvent(event)


class PieChartWidget(QWidget):
    COLORS = [QColor("#fb923c"), QColor("#f97316"), QColor("#fed7aa")]

    def __init__(self) -> None:
        super().__init__()
        self._data: list[tuple[str, int]] = []
        self._slice_regions: list[tuple[float, float, str, int, float, float]] = []
        self._pie_center = QPointF()
        self._outer_radius = 0.0
        self._inner_radius = 0.0
        self.setMinimumHeight(300)
        self.setMinimumWidth(320)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self._data = data
        self._slice_regions.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        total = sum(value for _, value in self._data)
        self._slice_regions.clear()

        if total <= 0:
            painter.setPen(QColor(71, 85, 105, 190))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无占比数据")
            return

        pie_size = min(width * 0.7, height * 0.56)
        pie_size = max(150.0, pie_size)
        pie_size = min(pie_size, min(width - 40.0, height - 90.0))
        pie_rect = QRectF((width - pie_size) / 2, 14, pie_size, pie_size)

        self._pie_center = pie_rect.center()
        self._outer_radius = pie_rect.width() / 2
        self._inner_radius = self._outer_radius * 0.52

        start_angle = 0.0
        for idx, (label, value) in enumerate(self._data):
            if value <= 0:
                continue

            span = 360.0 * value / total
            painter.setPen(QPen(QColor("#fffaf0"), 2))
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.drawPie(pie_rect, int(start_angle * 16), int(span * 16))
            self._slice_regions.append(
                (start_angle, start_angle + span, label, value, self._inner_radius, self._outer_radius)
            )

            percentage = int(round(value * 100 / total))
            if percentage >= 7:
                mid_angle = start_angle + span / 2
                rad = math.radians(mid_angle)
                text_radius = self._outer_radius * 0.76
                text_pos = QPointF(
                    self._pie_center.x() + math.cos(rad) * text_radius,
                    self._pie_center.y() - math.sin(rad) * text_radius,
                )
                painter.setPen(QColor("#fff7ed"))
                painter.drawText(
                    QRectF(text_pos.x() - 20, text_pos.y() - 10, 40, 20), Qt.AlignCenter, f"{percentage}%"
                )

            start_angle += span

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#fff8ef"))
        painter.drawEllipse(self._pie_center, self._inner_radius, self._inner_radius)

        legend_top = pie_rect.bottom() + 16
        item_height = 28
        for idx, (label, value) in enumerate(self._data):
            y = legend_top + idx * item_height
            painter.setBrush(self.COLORS[idx % len(self.COLORS)])
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(20, y, 12, 12))

            painter.setPen(QColor(51, 65, 85, 235))
            painter.drawText(QRectF(40, y - 2, width - 160, 16), Qt.AlignLeft | Qt.AlignVCenter, label)

            painter.setPen(QColor(234, 88, 12, 240))
            painter.drawText(QRectF(width - 130, y - 2, 110, 16), Qt.AlignRight | Qt.AlignVCenter, _format_hhmmss(value))

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._outer_radius <= 0:
            QToolTip.hideText()
            return

        dx = event.pos().x() - self._pie_center.x()
        dy = event.pos().y() - self._pie_center.y()
        distance = math.hypot(dx, dy)
        if distance > self._outer_radius or distance < self._inner_radius:
            QToolTip.hideText()
            return

        angle = math.degrees(math.atan2(-dy, dx))
        angle = (angle + 360.0) % 360.0
        for start, end, label, value, _, _ in self._slice_regions:
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
        self._build_ui()

    def _build_ui(self) -> None:
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
        content.setStyleSheet(
            """
            QWidget#PageContent { background: #fff8ef; }
            QFrame#StatsMetricCard, QFrame#StatsSectionCard {
                background: rgba(255, 255, 255, 238);
                border: 1px solid rgba(251, 146, 60, 72);
                border-radius: 18px;
            }
            QLabel#StatsPageTitle {
                font-size: 30px;
                font-weight: 900;
                color: #ea580c;
            }
            QLabel#StatsPageSubtitle {
                font-size: 16px;
                font-weight: 700;
                color: #334155;
                margin-bottom: 4px;
            }
            QLabel#StatsMetricIcon {
                font-size: 20px;
                font-weight: 900;
                border-radius: 12px;
                color: white;
            }
            QLabel#StatsMetricIcon[accent='warm'] { background: #ff7b00; }
            QLabel#StatsMetricIcon[accent='orange'] { background: #fb923c; }
            QLabel#StatsMetricIcon[accent='red'] { background: #ef4444; }
            QLabel#StatsMetricIcon[accent='peach'] { background: #f97316; }
            QLabel#StatsMetricTitle {
                font-size: 14px;
                font-weight: 700;
                color: #475569;
            }
            QLabel#StatsMetricValue {
                font-size: 28px;
                font-weight: 900;
                letter-spacing: 1px;
            }
            QLabel#StatsMetricValue[valueStyle='compact'] {
                font-size: 16px;
            }
            QLabel#StatsMetricValue[accent='warm'], QLabel#StatsMetricValue[accent='orange'] { color: #ea580c; }
            QLabel#StatsMetricValue[accent='red'] { color: #ef4444; }
            QLabel#StatsMetricValue[accent='peach'] { color: #f97316; }
            QLabel#StatsSectionTitle {
                font-size: 26px;
                font-weight: 900;
                color: #1e293b;
            }
            QLabel#StatsSectionHint {
                font-size: 14px;
                font-weight: 600;
                color: #64748b;
            }
            """
        )
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(14)

        title = QLabel("指标统计")
        title.setObjectName("StatsPageTitle")
        subtitle = QLabel("实时监控与数据分析")
        subtitle.setObjectName("StatsPageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(14)
        metric_grid.setVerticalSpacing(12)

        self.metric_screen_time = MetricCard("屏幕使用时间", "00:00:00", "◴", "warm")
        self.metric_detection_time = MetricCard("今日检测时间", "00:00:00", "▶", "peach")
        self.metric_correct_time = MetricCard("正确坐姿时间", "00:00:00", "∿", "orange")
        self.metric_incorrect_time = MetricCard("错误坐姿时间", "00:00:00", "!", "red")

        metric_grid.addWidget(self.metric_screen_time, 0, 0)
        metric_grid.addWidget(self.metric_detection_time, 0, 1)
        metric_grid.addWidget(self.metric_correct_time, 0, 2)
        metric_grid.addWidget(self.metric_incorrect_time, 0, 3)
        for col in range(4):
            metric_grid.setColumnStretch(col, 1)

        layout.addLayout(metric_grid)

        chart_row = QHBoxLayout()
        chart_row.setSpacing(14)

        bar_card = QFrame()
        bar_card.setObjectName("StatsSectionCard")
        bar_layout = QVBoxLayout(bar_card)
        bar_layout.setContentsMargins(16, 16, 16, 12)
        bar_layout.setSpacing(4)

        bar_title = QLabel("近7日正确/错误坐姿时长")
        bar_title.setObjectName("StatsSectionTitle")
        bar_hint = QLabel("同一柱状条中：橙色=正确，灰白=错误（单位：分钟）")
        bar_hint.setObjectName("StatsSectionHint")
        self.bar_chart = BarChartWidget()
        bar_layout.addWidget(bar_title)
        bar_layout.addWidget(bar_hint)
        bar_layout.addWidget(self.bar_chart)

        pie_card = QFrame()
        pie_card.setObjectName("StatsSectionCard")
        pie_layout = QVBoxLayout(pie_card)
        pie_layout.setContentsMargins(16, 16, 16, 12)
        pie_layout.setSpacing(4)

        pie_title = QLabel("今日状态占比")
        pie_title.setObjectName("StatsSectionTitle")
        self.pie_chart = PieChartWidget()
        pie_layout.addWidget(pie_title)
        pie_layout.addWidget(self.pie_chart)

        chart_row.addWidget(bar_card, 3)
        chart_row.addWidget(pie_card, 2)
        layout.addLayout(chart_row)

        table_title = QLabel("坐姿识别记录")
        table_title.setObjectName("StatsSectionTitle")
        layout.addWidget(table_title)

        self.posture_table = QTableWidget(0, 2)
        self.posture_table.setHorizontalHeaderLabels(["检测时间", "检测结果"])
        self.posture_table.verticalHeader().setVisible(False)
        self.posture_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.posture_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.posture_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.posture_table.setAlternatingRowColors(True)
        self.posture_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.posture_table.setMinimumHeight(190)
        layout.addWidget(self.posture_table)

        daily_title = QLabel("每日明细（近7天）")
        daily_title.setObjectName("StatsSectionTitle")
        layout.addWidget(daily_title)

        self.daily_table = QTableWidget(0, 6)
        self.daily_table.setHorizontalHeaderLabels(["日期", "在屏幕前", "正确", "错误", "正确占比", "错误占比"])
        self.daily_table.verticalHeader().setVisible(False)
        self.daily_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.daily_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.daily_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.daily_table.setAlternatingRowColors(True)
        self.daily_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.daily_table.setMinimumHeight(220)
        layout.addWidget(self.daily_table)

    def update_statistics(
        self,
        history: list[DaySummary],
        today_summary: DaySummary,
    ) -> None:
        # 屏幕使用时间：从系统读取
        self.metric_screen_time.set_value(_format_hhmmss(int(getattr(today_summary, "screen_seconds", 0))))
        
        # 今日检测时间 = 正确时间 + 错误时间
        detection_seconds = today_summary.correct_seconds + today_summary.incorrect_seconds
        self.metric_detection_time.set_value(_format_hhmmss(detection_seconds))
        
        self.metric_correct_time.set_value(_format_hhmmss(today_summary.correct_seconds))
        self.metric_incorrect_time.set_value(_format_hhmmss(today_summary.incorrect_seconds))

        bar_data: list[tuple[str, int, int]] = []
        for item in history:
            bar_data.append(
                (
                    item.day.strftime("%m-%d"),
                    int(item.correct_seconds // 60),
                    int(item.incorrect_seconds // 60),
                )
            )
        self.bar_chart.set_data(bar_data)

        pie_data = [
            ("正确", today_summary.correct_seconds),
            ("错误", today_summary.incorrect_seconds),
            ("未检测到用户", today_summary.unknown_seconds),
        ]
        self.pie_chart.set_data(pie_data)

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

            unknown = int(item.unknown_seconds)
            tooltip = (
                f"日期：{item.day.isoformat()}\n"
                f"在屏幕前：{_format_duration(front_total)}\n"
                f"正确：{_format_duration(correct)}\n"
                f"错误：{_format_duration(incorrect)}\n"
                f"未检测到用户：{_format_duration(unknown)}"
            )
            for col, cell in enumerate(cells):
                cell.setToolTip(tooltip)
                cell.setTextAlignment(Qt.AlignCenter)
                self.daily_table.setItem(row_idx, col, cell)

    def update_posture_records(self, records: list[dict[str, str]]) -> None:
        self.posture_table.setRowCount(len(records))
        for row_idx, row in enumerate(records):
            captured_at = QTableWidgetItem(str(row.get("captured_at", "-")))
            status = str(row.get("status", "unknown"))
            status_text = {"correct": "正确", "incorrect": "错误", "unknown": "未检测到用户"}.get(status, status)
            status_item = QTableWidgetItem(status_text)
            captured_at.setTextAlignment(Qt.AlignCenter)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.posture_table.setItem(row_idx, 0, captured_at)
            self.posture_table.setItem(row_idx, 1, status_item)

