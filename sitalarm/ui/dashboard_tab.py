from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sitalarm.services.stats_service import DaySummary


class DashboardTab(QWidget):
    run_now_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()

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
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(18)

        self.status_label = QLabel("状态: 检测中")
        self.status_label.setObjectName("StatusTitle")
        self.status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        root.addWidget(self.status_label)

        # ---- Today Stats Card ----
        stats_card = QFrame()
        stats_card.setObjectName("UiCard")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(26, 24, 26, 24)
        stats_layout.setSpacing(18)

        stats_title = QLabel("今日统计（分钟）")
        stats_title.setObjectName("SectionTitle")
        stats_layout.addWidget(stats_title)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.correct_label = self._build_stat_item("correct", "正确", row)
        self.incorrect_label = self._build_stat_item("incorrect", "错误", row)
        self.unknown_label = self._build_stat_item("unknown", "未检测到用户", row)
        stats_layout.addLayout(row)
        root.addWidget(stats_card)

        # ---- Latest Detection Card ----
        detection_card = QFrame()
        detection_card.setObjectName("UiCard")
        det_layout = QVBoxLayout(detection_card)
        det_layout.setContentsMargins(24, 20, 24, 20)
        det_layout.setSpacing(12)

        det_title = QLabel("最近检测")
        det_title.setObjectName("SectionTitle")
        det_layout.addWidget(det_title)

        # Two-column layout: image on left, metrics on right
        det_body = QHBoxLayout()
        det_body.setSpacing(16)

        # Image thumbnail
        self.capture_image_label = QLabel("暂无图片")
        self.capture_image_label.setObjectName("CapturePreview")
        self.capture_image_label.setAlignment(Qt.AlignCenter)
        self.capture_image_label.setFixedSize(160, 120)
        self.capture_image_label.setStyleSheet(
            "background: rgba(241, 245, 249, 0.8); border: 1px solid rgba(148, 163, 184, 0.3); "
            "border-radius: 8px; color: #94a3b8; font-size: 13px;"
        )
        det_body.addWidget(self.capture_image_label)

        # Metrics panel
        metrics_panel = QVBoxLayout()
        metrics_panel.setSpacing(6)

        self.last_event_label = QLabel("时间: --:--:--")
        self.last_event_label.setObjectName("FieldLabel")
        metrics_panel.addWidget(self.last_event_label)

        # Detection metrics grid
        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(12)
        metrics_grid.setVerticalSpacing(4)

        self._head_ratio_label = QLabel("--")
        self._head_ratio_threshold_label = QLabel("--")
        self._head_forward_label = QLabel("--")
        self._head_forward_threshold_label = QLabel("--")

        for lbl in (
            self._head_ratio_label,
            self._head_ratio_threshold_label,
            self._head_forward_label,
            self._head_forward_threshold_label,
        ):
            lbl.setObjectName("MetricDetail")

        metrics_grid.addWidget(self._make_hint("头占比:"), 0, 0)
        metrics_grid.addWidget(self._head_ratio_label, 0, 1)
        metrics_grid.addWidget(self._make_hint("阈值:"), 0, 2)
        metrics_grid.addWidget(self._head_ratio_threshold_label, 0, 3)

        metrics_grid.addWidget(self._make_hint("头前倾:"), 1, 0)
        metrics_grid.addWidget(self._head_forward_label, 1, 1)
        metrics_grid.addWidget(self._make_hint("阈值:"), 1, 2)
        metrics_grid.addWidget(self._head_forward_threshold_label, 1, 3)

        metrics_panel.addLayout(metrics_grid)

        # Status badge
        self._status_badge = QLabel("")
        self._status_badge.setObjectName("StatusBadge")
        self._status_badge.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        metrics_panel.addWidget(self._status_badge)
        metrics_panel.addStretch(1)

        det_body.addLayout(metrics_panel, 1)
        det_layout.addLayout(det_body)

        # Message area
        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setObjectName("DashboardMessageBox")
        self.message_box.setFrameShape(QFrame.NoFrame)
        self.message_box.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.message_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_box.setMinimumHeight(48)
        self.message_box.setMaximumHeight(80)
        det_layout.addWidget(self.message_box)

        root.addWidget(detection_card)

        # ---- Action Buttons ----
        button_row = QHBoxLayout()
        button_row.setSpacing(14)
        run_now_btn = QPushButton("立即检测")
        pause_btn = QPushButton("暂停")
        resume_btn = QPushButton("继续")
        run_now_btn.setObjectName("ActionButton")
        pause_btn.setObjectName("ActionButton")
        resume_btn.setObjectName("PrimaryButton")

        run_now_btn.clicked.connect(self.run_now_requested.emit)
        pause_btn.clicked.connect(self.pause_requested.emit)
        resume_btn.clicked.connect(self.resume_requested.emit)

        button_row.addWidget(run_now_btn)
        button_row.addWidget(pause_btn)
        button_row.addWidget(resume_btn)
        root.addLayout(button_row)
        root.addStretch(1)

    # ---- helpers ----

    @staticmethod
    def _make_hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionHint")
        return lbl

    def _build_stat_item(self, accent: str, name: str, parent_layout: QHBoxLayout) -> QLabel:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setProperty("accent", accent)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(8)

        icon = QLabel(self._metric_icon(accent))
        icon.setObjectName("MetricIcon")
        icon.setProperty("accent", accent)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(76, 76)
        card_layout.addWidget(icon, alignment=Qt.AlignHCenter)

        title = QLabel(name)
        title.setObjectName("MetricName")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        value = QLabel("0")
        value.setObjectName("MetricValue")
        value.setProperty("accent", accent)
        value.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(value)

        parent_layout.addWidget(card, 1)
        return value

    @staticmethod
    def _metric_icon(accent: str) -> str:
        if accent == "correct":
            return "OK"
        if accent == "incorrect":
            return "X"
        return "?"

    # ---- public API ----

    def set_state_text(self, text: str) -> None:
        self.status_label.setText(f"状态: {text}")

    def set_day_summary(self, summary: DaySummary) -> None:
        correct_minutes = int(summary.correct_seconds // 60)
        incorrect_minutes = int(summary.incorrect_seconds // 60)
        unknown_minutes = int(summary.unknown_seconds // 60)
        self.correct_label.setText(str(correct_minutes))
        self.incorrect_label.setText(str(incorrect_minutes))
        self.unknown_label.setText(str(unknown_minutes))

    def set_last_event(self, payload: dict[str, object]) -> None:
        status = str(payload.get("status", "unknown"))
        at = str(payload.get("time", "--:--:--"))
        self.last_event_label.setText(f"时间: {at}")

        # Status badge
        badge_map = {
            "correct": ("坐姿正确", "#16a34a", "rgba(22,163,74,0.12)"),
            "incorrect": ("坐姿错误", "#dc2626", "rgba(220,38,38,0.12)"),
            "unknown": ("未检测到", "#64748b", "rgba(100,116,139,0.12)"),
        }
        text, color, bg = badge_map.get(status, ("--", "#64748b", "rgba(100,116,139,0.12)"))
        self._status_badge.setText(text)
        self._status_badge.setStyleSheet(
            f"color: {color}; background: {bg}; font-weight: 700; font-size: 14px; "
            f"padding: 4px 12px; border-radius: 6px;"
        )

        # Detection metrics
        def _fmt(val: object) -> str:
            if isinstance(val, (int, float)):
                return f"{float(val):.4f}"
            return "--"

        self._head_ratio_label.setText(_fmt(payload.get("head_ratio")))
        self._head_ratio_threshold_label.setText(_fmt(payload.get("threshold_head_ratio")))
        self._head_forward_label.setText(_fmt(payload.get("head_forward_ratio")))
        self._head_forward_threshold_label.setText(_fmt(payload.get("threshold_head_forward")))

        # Capture image
        image_path = str(payload.get("image_path", ""))
        if image_path and Path(image_path).is_file():
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.capture_image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.capture_image_label.setPixmap(scaled)
        else:
            self.capture_image_label.setText("暂无图片")

        # Message box
        message = str(payload.get("message", "") or "")
        self.set_current_message(message)

    def set_current_message(self, message: str) -> None:
        self.message_box.setPlainText(message.strip())

    def append_message(self, message: str) -> None:
        self.message_box.append(message)
