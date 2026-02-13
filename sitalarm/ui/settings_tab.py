from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sitalarm.config import AppSettings
from sitalarm.services.capture_service import CameraCaptureService
from sitalarm.services.compute_device_service import gpu_available


class SettingsTab(QWidget):
    settings_changed = pyqtSignal(dict)
    open_capture_dir_requested = pyqtSignal()
    calibration_capture_requested = pyqtSignal()
    calibration_incorrect_capture_requested = pyqtSignal()
    calibration_reset_requested = pyqtSignal()
    preview_camera_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._loading = False
        self._autosave_timer = None
        self._gpu_available = gpu_available()
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
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        title = QLabel("坐姿提醒 - 设置")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        camera_group = QGroupBox("Camera")
        camera_group.setObjectName("UiCard")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setContentsMargins(24, 24, 24, 24)
        camera_layout.setSpacing(14)

        camera_desc = QLabel("Choose which camera to use for posture monitoring")
        camera_desc.setObjectName("SectionHint")
        camera_layout.addWidget(camera_desc)

        self.camera_combo = QComboBox()
        self.camera_combo.setObjectName("WideInput")

        preview_btn = QPushButton("预览")
        preview_btn.setObjectName("PrimaryButton")
        preview_btn.clicked.connect(self.preview_camera_requested.emit)

        self.refresh_camera_btn = QPushButton("刷新")
        self.refresh_camera_btn.setObjectName("ActionButton")
        self.refresh_camera_btn.clicked.connect(self._refresh_cameras)

        camera_row = QHBoxLayout()
        camera_row.setSpacing(12)
        camera_row.addWidget(self.camera_combo, 1)
        camera_row.addWidget(preview_btn)
        camera_row.addWidget(self.refresh_camera_btn)
        camera_layout.addLayout(camera_row)
        root.addWidget(camera_group)

        reminder_group = QGroupBox("Reminder")
        reminder_group.setObjectName("UiCard")
        reminder_layout = QVBoxLayout(reminder_group)
        reminder_layout.setContentsMargins(24, 24, 24, 24)
        reminder_layout.setSpacing(18)

        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        form.setColumnStretch(1, 1)

        self.detection_mode = QComboBox()
        self.detection_mode.addItem("strict(严格)", "strict")
        self.detection_mode.addItem("normal(正常)", "normal")
        self.detection_mode.addItem("loose(宽松)", "loose")
        self.detection_mode.setObjectName("WideInput")
        form.addWidget(self._field_label("检测模式"), 0, 0)
        form.addWidget(self.detection_mode, 0, 1)

        self.compute_device = QComboBox()
        self.compute_device.setObjectName("WideInput")
        self.compute_device.addItem("CPU", "cpu")
        if self._gpu_available:
            self.compute_device.addItem("GPU (加速)", "gpu")
        form.addWidget(self._field_label("识别加速"), 1, 0)
        form.addWidget(self.compute_device, 1, 1)

        self.reminder_method = QComboBox()
        self.reminder_method.addItem("降低屏幕亮度 (默认)", "dim_screen")
        self.reminder_method.addItem("弹出框提醒", "popup")
        self.reminder_method.setObjectName("WideInput")
        form.addWidget(self._field_label("提醒方式"), 2, 0)
        form.addWidget(self.reminder_method, 2, 1)

        interval_wrap = QHBoxLayout()
        interval_wrap.setSpacing(10)
        self.capture_interval = QSpinBox()
        self.capture_interval.setRange(1, 3600)
        self.capture_interval.setObjectName("ShortInput")
        interval_wrap.addWidget(self.capture_interval)
        interval_wrap.addWidget(QLabel("秒"))
        interval_wrap.addStretch(1)
        form.addWidget(self._field_label("检测间隔"), 3, 0)
        form.addLayout(interval_wrap, 3, 1)

        self.screen_time_enabled = QCheckBox("启用屏幕超时提醒")
        form.addWidget(self.screen_time_enabled, 4, 0, 1, 2)

        self.screen_time_threshold = QSpinBox()
        self.screen_time_threshold.setRange(10, 240)
        self.screen_time_threshold.setObjectName("ShortInput")
        threshold_wrap = QHBoxLayout()
        threshold_wrap.setSpacing(0)
        threshold_wrap.addStretch(1)
        threshold_wrap.addWidget(self.screen_time_threshold)
        form.addWidget(self._field_label("屏幕超时时间值（分钟）"), 5, 0)
        form.addLayout(threshold_wrap, 5, 1)

        self.retention = QSpinBox()
        self.retention.setRange(1, 30)
        self.retention.setObjectName("ShortInput")
        retention_wrap = QHBoxLayout()
        retention_wrap.setSpacing(0)
        retention_wrap.addStretch(1)
        retention_wrap.addWidget(self.retention)
        form.addWidget(self._field_label("图片保留天数"), 6, 0)
        form.addLayout(retention_wrap, 6, 1)

        reminder_layout.addLayout(form)
        root.addWidget(reminder_group)

        calibration_group = QGroupBox("坐姿校准")
        calibration_group.setObjectName("UiCard")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setContentsMargins(24, 18, 24, 18)
        calibration_layout.setSpacing(14)

        calibration_desc = QLabel(
            "校准流程：先拍 3 张正确坐姿，再拍 2 张错误坐姿（如低头/前倾），"
            "系统会用两者的中间值作为检测阈值。"
        )
        calibration_desc.setObjectName("SectionHint")
        calibration_desc.setWordWrap(True)
        calibration_layout.addWidget(calibration_desc)

        self.calibration_progress_label = QLabel("正确坐姿: 0/3　错误坐姿: 0/2")
        self.calibration_progress_label.setObjectName("FieldLabel")
        calibration_layout.addWidget(self.calibration_progress_label)

        self.calibration_threshold_label = QLabel("当前阈值: 未校准")
        self.calibration_threshold_label.setObjectName("FieldLabel")
        self.calibration_threshold_label.setWordWrap(True)
        calibration_layout.addWidget(self.calibration_threshold_label)

        self.calibration_status_label = QLabel("状态: 等待开始")
        self.calibration_status_label.setObjectName("SectionHint")
        self.calibration_status_label.setWordWrap(True)
        calibration_layout.addWidget(self.calibration_status_label)

        calibration_buttons = QHBoxLayout()
        calibration_buttons.setSpacing(10)
        self._capture_correct_btn = QPushButton("拍摄正确姿势样本")
        self._capture_correct_btn.setObjectName("ActionButton")
        self._capture_incorrect_btn = QPushButton("拍摄错误姿势样本")
        self._capture_incorrect_btn.setObjectName("ActionButton")
        self._capture_incorrect_btn.setEnabled(False)
        reset_button = QPushButton("重置校准")
        reset_button.setObjectName("ActionButton")
        self._capture_correct_btn.clicked.connect(self.calibration_capture_requested.emit)
        self._capture_incorrect_btn.clicked.connect(self.calibration_incorrect_capture_requested.emit)
        reset_button.clicked.connect(self.calibration_reset_requested.emit)
        calibration_buttons.addWidget(self._capture_correct_btn)
        calibration_buttons.addWidget(self._capture_incorrect_btn)
        calibration_buttons.addWidget(reset_button)
        calibration_buttons.addStretch(1)
        calibration_layout.addLayout(calibration_buttons)
        root.addWidget(calibration_group)

        footer_buttons = QHBoxLayout()
        open_button = QPushButton("打开今日图片目录")
        open_button.setObjectName("ActionButton")
        open_button.clicked.connect(self.open_capture_dir_requested.emit)
        footer_buttons.addWidget(open_button)
        footer_buttons.addStretch(1)
        root.addLayout(footer_buttons)

        tip = QLabel("提示: 所有数据默认保存在本地，不会上传云端。")
        tip.setObjectName("SectionHint")
        root.addWidget(tip)
        root.addStretch(1)

        self._refresh_cameras()

        from PyQt5.QtCore import QTimer

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(250)
        self._autosave_timer.timeout.connect(self._emit_save)

        self._wire_autosave()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def load_settings(self, settings: AppSettings) -> None:
        self._loading = True
        self.capture_interval.setValue(settings.capture_interval_seconds)
        self.screen_time_enabled.setChecked(settings.screen_time_enabled)
        self.screen_time_threshold.setValue(settings.screen_time_threshold_minutes)
        self.retention.setValue(settings.retention_days)
        self._set_camera_index(settings.camera_index)
        self._set_reminder_method(settings.reminder_method)
        self._set_detection_mode(settings.detection_mode)
        self._set_compute_device(getattr(settings, "compute_device", "cpu"))
        self._loading = False

        head_fwd = getattr(settings, "head_forward_threshold_calibrated", 0.0)
        if settings.head_ratio_threshold > 0:
            text = f"头占比阈值: {settings.head_ratio_threshold:.4f}"
            if head_fwd > 0:
                text += f"　｜　头前倾阈值: {head_fwd:.4f}"
            self.calibration_threshold_label.setText(text)
        else:
            self.calibration_threshold_label.setText("当前阈值: 未校准")

    def update_calibration_status(self, payload: dict[str, object]) -> None:
        phase = str(payload.get("phase", ""))
        captured_correct = int(payload.get("captured_correct", payload.get("captured", 0)))
        required_correct = int(payload.get("required_correct", payload.get("required", 3)))
        captured_incorrect = int(payload.get("captured_incorrect", 0))
        required_incorrect = int(payload.get("required_incorrect", 2))
        threshold = payload.get("threshold")
        message = str(payload.get("message", ""))

        self.calibration_progress_label.setText(
            f"正确坐姿: {captured_correct}/{required_correct}　"
            f"错误坐姿: {captured_incorrect}/{required_incorrect}"
        )

        head_fwd_threshold = payload.get("head_forward_threshold")
        if isinstance(threshold, (int, float)) and threshold > 0:
            text = f"头占比阈值: {float(threshold):.4f}"
            if isinstance(head_fwd_threshold, (int, float)) and head_fwd_threshold > 0:
                text += f"　｜　头前倾阈值: {float(head_fwd_threshold):.4f}"
            self.calibration_threshold_label.setText(text)
        else:
            self.calibration_threshold_label.setText("当前阈值: 未校准")

        if message:
            self.calibration_status_label.setText(f"状态: {message}")

        # Button state management based on calibration phase.
        if phase == "correct_done" or phase == "collecting_incorrect":
            # Phase 1 done, enable incorrect capture, disable correct capture.
            self._capture_correct_btn.setEnabled(False)
            self._capture_incorrect_btn.setEnabled(True)
        elif phase == "completed":
            # All done.
            self._capture_correct_btn.setEnabled(True)
            self._capture_incorrect_btn.setEnabled(False)
        elif phase in ("required", "error") and captured_correct >= required_correct:
            # Error during incorrect capture, keep incorrect button active.
            self._capture_correct_btn.setEnabled(False)
            self._capture_incorrect_btn.setEnabled(True)
        else:
            # Default / collecting correct / error during correct / reset.
            self._capture_correct_btn.setEnabled(True)
            self._capture_incorrect_btn.setEnabled(False)

    def _emit_save(self) -> None:
        if self._loading:
            return
        selected_camera = self._current_camera_index()
        payload = {
            "capture_interval_seconds": self.capture_interval.value(),
            "camera_index": selected_camera if selected_camera is not None else 0,
            "detection_mode": str(self.detection_mode.currentData() or "strict"),
            "compute_device": str(self.compute_device.currentData() or "cpu"),
            "reminder_method": str(self.reminder_method.currentData() or "dim_screen"),
            "screen_time_enabled": self.screen_time_enabled.isChecked(),
            "screen_time_threshold_minutes": self.screen_time_threshold.value(),
            "retention_days": self.retention.value(),
        }
        self.settings_changed.emit(payload)

    def _schedule_autosave(self) -> None:
        if self._loading or self._autosave_timer is None:
            return
        self._autosave_timer.start()

    def _wire_autosave(self) -> None:
        self.capture_interval.valueChanged.connect(lambda *_: self._schedule_autosave())
        self.camera_combo.currentIndexChanged.connect(lambda *_: self._schedule_autosave())
        self.detection_mode.currentIndexChanged.connect(lambda *_: self._schedule_autosave())
        self.compute_device.currentIndexChanged.connect(lambda *_: self._schedule_autosave())
        self.reminder_method.currentIndexChanged.connect(lambda *_: self._schedule_autosave())
        self.screen_time_enabled.toggled.connect(lambda *_: self._schedule_autosave())
        self.screen_time_threshold.valueChanged.connect(lambda *_: self._schedule_autosave())
        self.retention.valueChanged.connect(lambda *_: self._schedule_autosave())

    def _refresh_cameras(self) -> None:
        self._loading = True
        current = self._current_camera_index()
        self.camera_combo.clear()
        indices = CameraCaptureService.list_available_camera_indices(max_index=4)
        if not indices:
            self.camera_combo.addItem("未检测到可用摄像头（请检查权限）", -1)
            self.camera_combo.setEnabled(False)
            self._loading = False
            return

        self.camera_combo.setEnabled(True)
        for idx in indices:
            self.camera_combo.addItem(f"摄像头 {idx}", idx)

        if current is not None and current in indices:
            self._set_camera_index(current)
        self._loading = False

    def _current_camera_index(self) -> int | None:
        data = self.camera_combo.currentData()
        if isinstance(data, int) and data >= 0:
            return data
        return None

    def _set_camera_index(self, index: int) -> None:
        for i in range(self.camera_combo.count()):
            if self.camera_combo.itemData(i) == index:
                self.camera_combo.setCurrentIndex(i)
                return

    def _set_reminder_method(self, method: str) -> None:
        method = str(method or "dim_screen")
        for i in range(self.reminder_method.count()):
            if str(self.reminder_method.itemData(i)) == method:
                self.reminder_method.setCurrentIndex(i)
                return

    def _set_detection_mode(self, mode: str) -> None:
        mode = str(mode or "strict")
        for i in range(self.detection_mode.count()):
            if str(self.detection_mode.itemData(i)) == mode:
                self.detection_mode.setCurrentIndex(i)
                return

    def _set_compute_device(self, device: str) -> None:
        requested = str(device or "cpu")
        if requested == "gpu" and not self._gpu_available:
            requested = "cpu"
        for i in range(self.compute_device.count()):
            if str(self.compute_device.itemData(i)) == requested:
                self.compute_device.setCurrentIndex(i)
                return
