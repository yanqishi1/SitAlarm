from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
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

        event_card = QFrame()
        event_card.setObjectName("UiCard")
        event_layout = QVBoxLayout(event_card)
        event_layout.setContentsMargins(24, 20, 24, 20)
        event_layout.setSpacing(10)

        self.last_event_label = QLabel("最近检测: --:--:-- | - | -")
        self.last_event_label.setObjectName("LastEventLabel")
        event_layout.addWidget(self.last_event_label)

        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setObjectName("DashboardMessageBox")
        self.message_box.setFrameShape(QFrame.NoFrame)
        self.message_box.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.message_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_box.setMinimumHeight(64)
        self.message_box.setMaximumHeight(110)
        event_layout.addWidget(self.message_box)
        root.addWidget(event_card)

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
        reasons = str(payload.get("reasons", "-"))
        at = str(payload.get("time", "--:--:--"))
        self.last_event_label.setText(f"最近检测: {at} | {status} | {reasons}")

        message = str(payload.get("message", "") or "")
        self.set_current_message(message)

    def set_current_message(self, message: str) -> None:
        self.message_box.setPlainText(message.strip())

    def append_message(self, message: str) -> None:
        self.message_box.append(message)
