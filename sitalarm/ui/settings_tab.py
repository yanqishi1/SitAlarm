from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sitalarm.config import AppSettings


class SettingsTab(QWidget):
    settings_changed = pyqtSignal(dict)
    open_capture_dir_requested = pyqtSignal()
    calibration_capture_requested = pyqtSignal()
    calibration_reset_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.capture_interval = QSpinBox()
        self.capture_interval.setRange(1, 60)
        form.addRow("检测间隔（分钟）", self.capture_interval)

        self.cooldown = QSpinBox()
        self.cooldown.setRange(1, 30)
        form.addRow("提醒冷却（分钟）", self.cooldown)

        self.screen_time_enabled = QCheckBox("启用屏幕超时提醒")
        form.addRow(self.screen_time_enabled)

        self.screen_time_threshold = QSpinBox()
        self.screen_time_threshold.setRange(10, 240)
        form.addRow("屏幕超时阈值（分钟）", self.screen_time_threshold)

        self.retention = QSpinBox()
        self.retention.setRange(1, 30)
        form.addRow("图片保留天数", self.retention)

        root.addLayout(form)

        calibration_group = QGroupBox("头占比校准（首次必做）")
        calibration_layout = QVBoxLayout(calibration_group)

        hint = QLabel("请保持正确坐姿，连续拍 2 张照片。系统将按两张样本自动计算阈值。")
        hint.setWordWrap(True)
        calibration_layout.addWidget(hint)

        self.calibration_progress_label = QLabel("当前进度：0/2")
        calibration_layout.addWidget(self.calibration_progress_label)

        self.calibration_threshold_label = QLabel("当前阈值：未校准")
        calibration_layout.addWidget(self.calibration_threshold_label)

        self.calibration_status_label = QLabel("状态：等待开始")
        self.calibration_status_label.setWordWrap(True)
        calibration_layout.addWidget(self.calibration_status_label)

        calibration_buttons = QHBoxLayout()
        capture_button = QPushButton("拍摄正确姿势样本")
        reset_button = QPushButton("重置校准")

        capture_button.clicked.connect(self.calibration_capture_requested.emit)
        reset_button.clicked.connect(self.calibration_reset_requested.emit)

        calibration_buttons.addWidget(capture_button)
        calibration_buttons.addWidget(reset_button)
        calibration_layout.addLayout(calibration_buttons)

        root.addWidget(calibration_group)

        buttons = QHBoxLayout()
        save_button = QPushButton("保存设置")
        open_button = QPushButton("打开今日图片目录")

        save_button.clicked.connect(self._emit_save)
        open_button.clicked.connect(self.open_capture_dir_requested.emit)

        buttons.addWidget(save_button)
        buttons.addWidget(open_button)
        root.addLayout(buttons)

        root.addWidget(QLabel("提示：所有数据默认保存在本地，不会上传云端。"))

    def load_settings(self, settings: AppSettings) -> None:
        self.capture_interval.setValue(settings.capture_interval_minutes)
        self.cooldown.setValue(settings.reminder_cooldown_minutes)
        self.screen_time_enabled.setChecked(settings.screen_time_enabled)
        self.screen_time_threshold.setValue(settings.screen_time_threshold_minutes)
        self.retention.setValue(settings.retention_days)

        if settings.head_ratio_threshold > 0:
            self.calibration_threshold_label.setText(f"当前阈值：{settings.head_ratio_threshold:.4f}")
        else:
            self.calibration_threshold_label.setText("当前阈值：未校准")

    def update_calibration_status(self, payload: dict[str, object]) -> None:
        captured = int(payload.get("captured", 0))
        required = int(payload.get("required", 2))
        threshold = payload.get("threshold")
        message = str(payload.get("message", ""))

        self.calibration_progress_label.setText(f"当前进度：{captured}/{required}")

        if isinstance(threshold, (int, float)) and threshold > 0:
            self.calibration_threshold_label.setText(f"当前阈值：{float(threshold):.4f}")
        else:
            self.calibration_threshold_label.setText("当前阈值：未校准")

        if message:
            self.calibration_status_label.setText(f"状态：{message}")

    def _emit_save(self) -> None:
        payload = {
            "capture_interval_minutes": self.capture_interval.value(),
            "reminder_cooldown_minutes": self.cooldown.value(),
            "screen_time_enabled": self.screen_time_enabled.isChecked(),
            "screen_time_threshold_minutes": self.screen_time_threshold.value(),
            "retention_days": self.retention.value(),
        }
        self.settings_changed.emit(payload)
