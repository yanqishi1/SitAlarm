from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        self.status_label = QLabel("状态：未启动")
        self.status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.status_label, alignment=Qt.AlignTop)

        stats_box = QGroupBox("今日统计（分钟）")
        stats_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stats_box.setMaximumHeight(120)
        stats_layout = QGridLayout(stats_box)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setHorizontalSpacing(28)
        self.correct_label = QLabel("正确：0")
        self.incorrect_label = QLabel("错误：0")
        self.unknown_label = QLabel("未知：0")
        stats_layout.addWidget(self.correct_label, 0, 0)
        stats_layout.addWidget(self.incorrect_label, 0, 1)
        stats_layout.addWidget(self.unknown_label, 0, 2)
        stats_layout.setColumnStretch(0, 1)
        stats_layout.setColumnStretch(1, 1)
        stats_layout.setColumnStretch(2, 1)
        layout.addWidget(stats_box)

        self.last_event_label = QLabel("最近检测：无")
        self.last_event_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.last_event_label)

        self.message_box = QTextEdit()
        self.message_box.setReadOnly(True)
        self.message_box.setPlaceholderText("提醒内容会显示在这里")
        self.message_box.setFixedHeight(96)
        layout.addWidget(self.message_box)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        run_now_btn = QPushButton("立即检测")
        pause_btn = QPushButton("暂停")
        resume_btn = QPushButton("继续")

        run_now_btn.clicked.connect(self.run_now_requested.emit)
        pause_btn.clicked.connect(self.pause_requested.emit)
        resume_btn.clicked.connect(self.resume_requested.emit)

        button_row.addWidget(run_now_btn)
        button_row.addWidget(pause_btn)
        button_row.addWidget(resume_btn)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def set_state_text(self, text: str) -> None:
        self.status_label.setText(f"状态：{text}")

    def set_day_summary(self, summary: DaySummary) -> None:
        self.correct_label.setText(f"正确：{summary.correct_minutes}")
        self.incorrect_label.setText(f"错误：{summary.incorrect_minutes}")
        self.unknown_label.setText(f"未知：{summary.unknown_minutes}")

    def set_last_event(self, payload: dict[str, object]) -> None:
        status = str(payload.get("status", "unknown"))
        reasons = str(payload.get("reasons", "-"))
        at = str(payload.get("time", "--:--:--"))
        self.last_event_label.setText(f"最近检测：{at} | {status} | {reasons}")

    def append_message(self, message: str) -> None:
        self.message_box.append(message)
