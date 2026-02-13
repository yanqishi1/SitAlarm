from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class _ThumbnailCard(QFrame):
    """Small image card with an 'x' delete button."""

    delete_requested = pyqtSignal(int)  # emits the sample index

    def __init__(self, index: int, image_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.setFixedSize(110, 90)
        self.setObjectName("ThumbnailCard")
        self.setStyleSheet(
            "QFrame#ThumbnailCard { background: #f1f5f9; border: 1px solid rgba(148,163,184,0.3); border-radius: 8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Delete button (top-right)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch(1)
        del_btn = QPushButton("×")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet(
            "QPushButton { background: rgba(220,38,38,0.8); color: white; border: none; border-radius: 10px; "
            "font-size: 14px; font-weight: 700; } QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.index))
        top_row.addWidget(del_btn)
        layout.addLayout(top_row)

        # Image
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setFixedSize(100, 60)
        if Path(image_path).is_file():
            pix = QPixmap(image_path).scaled(100, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            img_label.setPixmap(pix)
        else:
            img_label.setText(f"#{index + 1}")
        layout.addWidget(img_label, alignment=Qt.AlignCenter)


class OnboardingTab(QWidget):
    """引导页面：帮助用户完成首次配置（集成实时预览和设置）"""

    calibration_requested = pyqtSignal()  # 请求拍摄校准照片（自动判断阶段）
    calibration_correct_requested = pyqtSignal()
    calibration_incorrect_requested = pyqtSignal()
    remove_correct_sample_requested = pyqtSignal(int)
    remove_incorrect_sample_requested = pyqtSignal(int)
    calibration_reset_requested = pyqtSignal()
    finish_onboarding_requested = pyqtSignal()
    start_detection_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._calibration_count = 0
        self._phase = "correct"  # "correct" or "incorrect"
        self._build_ui()
        self._current_settings: dict = {}

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        self.welcome_page = self._create_welcome_page()
        self.calibration_page = self._create_calibration_page()
        self.preview_page = self._create_preview_page()
        self.settings_page = self._create_settings_page()
        self.finish_page = self._create_finish_page()

        self.stack.addWidget(self.welcome_page)      # 0
        self.stack.addWidget(self.calibration_page)   # 1
        self.stack.addWidget(self.preview_page)       # 2
        self.stack.addWidget(self.settings_page)      # 3
        self.stack.addWidget(self.finish_page)        # 4

        self._apply_styles()

    # ------------------------------------------------------------------ pages

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel("🎯")
        icon_label.setStyleSheet("font-size: 72px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("欢迎使用 SitAlarm")
        title.setObjectName("OnboardingTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "SitAlarm 是一款智能坐姿提醒应用，通过摄像头监测您的坐姿，"
            "及时提醒您保持正确姿势，保护颈椎健康。\n\n"
            "接下来，我们将引导您完成几个简单的设置步骤。"
        )
        desc.setObjectName("OnboardingDesc")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(20)

        steps = QLabel("📸 拍摄校准照片  →  👁️ 预览检测效果  →  ⚙️ 配置检测参数")
        steps.setObjectName("OnboardingSteps")
        steps.setAlignment(Qt.AlignCenter)
        layout.addWidget(steps)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        self.start_btn = QPushButton("开始引导")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setFixedSize(180, 48)
        self.start_btn.clicked.connect(lambda: self.go_to_page(1))
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)
        return page

    def _create_calibration_page(self) -> QWidget:
        page = QWidget()

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        step_indicator = QLabel("步骤 1 / 4")
        step_indicator.setObjectName("StepIndicator")
        layout.addWidget(step_indicator)

        title = QLabel("坐姿校准")
        title.setObjectName("OnboardingTitle")
        layout.addWidget(title)

        # ---- Phase 1: correct posture ----
        correct_group = QFrame()
        correct_group.setObjectName("SettingsCard")
        cg_layout = QVBoxLayout(correct_group)
        cg_layout.setContentsMargins(18, 14, 18, 14)
        cg_layout.setSpacing(10)

        cg_title = QLabel("① 拍摄正确坐姿（3 张）")
        cg_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #1e293b;")
        cg_layout.addWidget(cg_title)

        cg_tips = QLabel(
            "请保持标准坐姿：头部正直、眼睛与屏幕保持 50-70cm 距离、背部挺直。"
        )
        cg_tips.setObjectName("OnboardingDesc")
        cg_tips.setWordWrap(True)
        cg_layout.addWidget(cg_tips)

        # Thumbnail gallery for correct samples
        self._correct_gallery = QHBoxLayout()
        self._correct_gallery.setSpacing(8)
        self._correct_gallery_stretch = None
        cg_layout.addLayout(self._correct_gallery)

        self._capture_correct_btn = QPushButton("拍摄正确坐姿")
        self._capture_correct_btn.setObjectName("PrimaryButton")
        self._capture_correct_btn.setFixedHeight(38)
        self._capture_correct_btn.clicked.connect(self.calibration_correct_requested.emit)
        cg_layout.addWidget(self._capture_correct_btn)

        self._correct_status = QLabel("")
        self._correct_status.setObjectName("CalibrationStatus")
        self._correct_status.setWordWrap(True)
        cg_layout.addWidget(self._correct_status)

        layout.addWidget(correct_group)

        # ---- Phase 2: incorrect posture ----
        incorrect_group = QFrame()
        incorrect_group.setObjectName("SettingsCard")
        ig_layout = QVBoxLayout(incorrect_group)
        ig_layout.setContentsMargins(18, 14, 18, 14)
        ig_layout.setSpacing(10)

        ig_title = QLabel("② 拍摄错误坐姿（2 张）")
        ig_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #1e293b;")
        ig_layout.addWidget(ig_title)

        ig_tips = QLabel(
            "请做出不正确坐姿，如低头看手机、向前探头等，用于确定检测阈值。"
        )
        ig_tips.setObjectName("OnboardingDesc")
        ig_tips.setWordWrap(True)
        ig_layout.addWidget(ig_tips)

        self._incorrect_gallery = QHBoxLayout()
        self._incorrect_gallery.setSpacing(8)
        ig_layout.addLayout(self._incorrect_gallery)

        self._capture_incorrect_btn = QPushButton("拍摄错误坐姿")
        self._capture_incorrect_btn.setObjectName("PrimaryButton")
        self._capture_incorrect_btn.setFixedHeight(38)
        self._capture_incorrect_btn.setEnabled(False)
        self._capture_incorrect_btn.clicked.connect(self.calibration_incorrect_requested.emit)
        ig_layout.addWidget(self._capture_incorrect_btn)

        self._incorrect_status = QLabel("")
        self._incorrect_status.setObjectName("CalibrationStatus")
        self._incorrect_status.setWordWrap(True)
        ig_layout.addWidget(self._incorrect_status)

        layout.addWidget(incorrect_group)

        # Overall status
        self.calibration_status = QLabel("请先拍摄 3 张正确坐姿照片")
        self.calibration_status.setObjectName("CalibrationStatus")
        self.calibration_status.setAlignment(Qt.AlignCenter)
        self.calibration_status.setMinimumHeight(40)
        layout.addWidget(self.calibration_status)

        self.calibration_progress = QLabel("")
        self.calibration_progress.setObjectName("CalibrationProgress")
        self.calibration_progress.setAlignment(Qt.AlignCenter)
        self.calibration_progress.setStyleSheet("font-size: 20px; letter-spacing: 6px;")
        layout.addWidget(self.calibration_progress)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.back_btn_1 = QPushButton("返回")
        self.back_btn_1.setObjectName("SecondaryButton")
        self.back_btn_1.setFixedSize(100, 40)
        self.back_btn_1.clicked.connect(lambda: self.go_to_page(0))
        btn_layout.addWidget(self.back_btn_1)

        self.next_btn_1 = QPushButton("下一步")
        self.next_btn_1.setObjectName("PrimaryButton")
        self.next_btn_1.setFixedSize(100, 40)
        self.next_btn_1.setEnabled(False)
        self.next_btn_1.clicked.connect(lambda: self.go_to_page(2))
        btn_layout.addWidget(self.next_btn_1)

        layout.addLayout(btn_layout)
        return page

    def _create_preview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        step_indicator = QLabel("步骤 2 / 4")
        step_indicator.setObjectName("StepIndicator")
        layout.addWidget(step_indicator)

        title = QLabel("预览检测效果")
        title.setObjectName("OnboardingTitle")
        layout.addWidget(title)

        desc = QLabel(
            "下方显示实时检测画面。您可以看到面部检测框和骨骼线。"
            "调整姿势，确保检测效果良好后再继续。"
        )
        desc.setObjectName("OnboardingDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        preview_card = QFrame()
        preview_card.setObjectName("PreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)

        self.preview_label = QLabel("等待实时画面...")
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(640, 480)
        self.preview_label.setStyleSheet("background: #1e293b; color: #94a3b8; font-size: 16px;")
        preview_layout.addWidget(self.preview_label, alignment=Qt.AlignCenter)

        self.preview_status = QLabel("状态: 等待开始")
        self.preview_status.setObjectName("PreviewStatus")
        self.preview_status.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.preview_status)

        layout.addWidget(preview_card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.back_btn_2 = QPushButton("返回")
        self.back_btn_2.setObjectName("SecondaryButton")
        self.back_btn_2.setFixedSize(100, 40)
        self.back_btn_2.clicked.connect(lambda: self.go_to_page(1))
        btn_layout.addWidget(self.back_btn_2)

        self.next_btn_2 = QPushButton("下一步")
        self.next_btn_2.setObjectName("PrimaryButton")
        self.next_btn_2.setFixedSize(100, 40)
        self.next_btn_2.clicked.connect(lambda: self.go_to_page(3))
        btn_layout.addWidget(self.next_btn_2)

        layout.addLayout(btn_layout)
        return page

    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        step_indicator = QLabel("步骤 3 / 4")
        step_indicator.setObjectName("StepIndicator")
        layout.addWidget(step_indicator)

        title = QLabel("配置检测参数")
        title.setObjectName("OnboardingTitle")
        layout.addWidget(title)

        desc = QLabel("根据您的使用习惯，配置以下检测参数：")
        desc.setObjectName("OnboardingDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        settings_card = QFrame()
        settings_card.setObjectName("SettingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(20)

        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(16)
        form.setColumnStretch(1, 1)

        self.detection_mode = QComboBox()
        self.detection_mode.addItem("严格", "strict")
        self.detection_mode.addItem("正常", "normal")
        self.detection_mode.addItem("宽松", "loose")
        self.detection_mode.setObjectName("WideInput")
        self.detection_mode.currentTextChanged.connect(self._emit_settings_change)
        form.addWidget(self._field_label("检测模式"), 0, 0)
        form.addWidget(self.detection_mode, 0, 1)

        self.reminder_method = QComboBox()
        self.reminder_method.addItem("降低屏幕亮度 (默认)", "dim_screen")
        self.reminder_method.addItem("弹出框提醒", "popup")
        self.reminder_method.setObjectName("WideInput")
        self.reminder_method.currentTextChanged.connect(self._emit_settings_change)
        form.addWidget(self._field_label("提醒方式"), 1, 0)
        form.addWidget(self.reminder_method, 1, 1)

        interval_wrap = QHBoxLayout()
        interval_wrap.setSpacing(10)
        self.capture_interval = QSpinBox()
        self.capture_interval.setRange(5, 300)
        self.capture_interval.setValue(30)
        self.capture_interval.setSuffix(" 秒")
        self.capture_interval.setObjectName("ShortInput")
        self.capture_interval.valueChanged.connect(self._emit_settings_change)
        interval_wrap.addWidget(self.capture_interval)
        interval_wrap.addStretch(1)
        form.addWidget(self._field_label("检测间隔"), 2, 0)
        form.addLayout(interval_wrap, 2, 1)

        retention_wrap = QHBoxLayout()
        retention_wrap.setSpacing(10)
        self.retention = QSpinBox()
        self.retention.setRange(1, 30)
        self.retention.setValue(7)
        self.retention.setSuffix(" 天")
        self.retention.setObjectName("ShortInput")
        self.retention.valueChanged.connect(self._emit_settings_change)
        retention_wrap.addWidget(self.retention)
        retention_wrap.addStretch(1)
        form.addWidget(self._field_label("图片保留天数"), 3, 0)
        form.addLayout(retention_wrap, 3, 1)

        self.screen_time_enabled = QCheckBox("启用屏幕超时提醒")
        self.screen_time_enabled.stateChanged.connect(self._emit_settings_change)
        form.addWidget(self.screen_time_enabled, 4, 0, 1, 2)

        threshold_wrap = QHBoxLayout()
        threshold_wrap.setSpacing(10)
        self.screen_time_threshold = QSpinBox()
        self.screen_time_threshold.setRange(10, 240)
        self.screen_time_threshold.setValue(60)
        self.screen_time_threshold.setSuffix(" 分钟")
        self.screen_time_threshold.setObjectName("ShortInput")
        self.screen_time_threshold.valueChanged.connect(self._emit_settings_change)
        threshold_wrap.addWidget(self.screen_time_threshold)
        threshold_wrap.addStretch(1)
        form.addWidget(self._field_label("屏幕超时时间"), 5, 0)
        form.addLayout(threshold_wrap, 5, 1)

        settings_layout.addLayout(form)
        layout.addWidget(settings_card)

        hint = QLabel("💡 这些设置后续可以在设置页面随时修改")
        hint.setObjectName("HintText")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.back_btn_3 = QPushButton("返回")
        self.back_btn_3.setObjectName("SecondaryButton")
        self.back_btn_3.setFixedSize(100, 40)
        self.back_btn_3.clicked.connect(lambda: self.go_to_page(2))
        btn_layout.addWidget(self.back_btn_3)

        self.next_btn_3 = QPushButton("下一步")
        self.next_btn_3.setObjectName("PrimaryButton")
        self.next_btn_3.setFixedSize(100, 40)
        self.next_btn_3.clicked.connect(lambda: self.go_to_page(4))
        btn_layout.addWidget(self.next_btn_3)

        layout.addLayout(btn_layout)
        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel("🎉")
        icon_label.setStyleSheet("font-size: 72px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        step_indicator = QLabel("步骤 4 / 4")
        step_indicator.setObjectName("StepIndicator")
        step_indicator.setAlignment(Qt.AlignCenter)
        layout.addWidget(step_indicator)

        title = QLabel("配置完成！")
        title.setObjectName("OnboardingTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "恭喜您完成了所有设置！\n\n"
            "SitAlarm 现在开始为您监测坐姿。"
            "当检测到不正确坐姿时，会及时提醒您。\n\n"
            "您可以通过左侧边栏随时返回引导页面重新配置。"
        )
        desc.setObjectName("OnboardingDesc")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(30)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.start_detection_btn = QPushButton("🚀 开始检测")
        self.start_detection_btn.setObjectName("PrimaryButton")
        self.start_detection_btn.setFixedSize(180, 48)
        self.start_detection_btn.clicked.connect(self._on_start_detection_clicked)
        btn_layout.addWidget(self.start_detection_btn)

        self.finish_btn = QPushButton("完成")
        self.finish_btn.setObjectName("SecondaryButton")
        self.finish_btn.setFixedSize(120, 44)
        self.finish_btn.clicked.connect(self._on_finish_clicked)
        btn_layout.addWidget(self.finish_btn)

        layout.addLayout(btn_layout)
        return page

    # ------------------------------------------------------------------ styles

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
            }
            QLabel#OnboardingTitle {
                font-size: 28px; font-weight: 700; color: #1e293b; margin-bottom: 4px;
            }
            QLabel#OnboardingDesc {
                font-size: 15px; color: #475569; line-height: 1.6;
            }
            QLabel#StepIndicator {
                font-size: 13px; font-weight: 600; color: #fb923c;
                padding: 4px 12px; background: rgba(251,146,60,0.15); border-radius: 16px;
            }
            QLabel#OnboardingSteps {
                font-size: 14px; color: #64748b; padding: 12px;
                background: rgba(241,245,249,0.8); border-radius: 10px;
            }
            QLabel#TipsList {
                font-size: 14px; color: #475569; background: rgba(241,245,249,0.8);
                padding: 14px 18px; border-radius: 10px; border-left: 4px solid #fb923c;
            }
            QLabel#CalibrationStatus {
                font-size: 14px; font-weight: 600; color: #475569;
                padding: 10px; background: rgba(241,245,249,0.8); border-radius: 8px;
            }
            QLabel#PreviewStatus {
                font-size: 14px; font-weight: 600; color: #475569; padding: 8px;
            }
            QFrame#PreviewCard, QFrame#SettingsCard {
                background: rgba(255,255,255,0.9);
                border: 1px solid rgba(251,146,60,0.3); border-radius: 14px;
            }
            QLabel#HintText {
                font-size: 13px; color: #64748b; font-style: italic;
            }
            QPushButton#PrimaryButton {
                background: #fb923c; color: white; border: none; border-radius: 8px;
                font-size: 14px; font-weight: 600; padding: 8px 20px;
            }
            QPushButton#PrimaryButton:hover { background: #f97316; }
            QPushButton#PrimaryButton:disabled { background: #cbd5e1; color: #94a3b8; }
            QPushButton#SecondaryButton {
                background: rgba(241,245,249,0.8); color: #475569;
                border: 1px solid rgba(148,163,184,0.3); border-radius: 8px;
                font-size: 14px; font-weight: 600; padding: 8px 20px;
            }
            QPushButton#SecondaryButton:hover { background: rgba(226,232,240,0.8); }
            QComboBox, QSpinBox {
                padding: 6px 10px; border: 1px solid rgba(148,163,184,0.4);
                border-radius: 6px; background: white; font-size: 14px;
            }
            QComboBox:focus, QSpinBox:focus { border-color: #fb923c; }
            QCheckBox { font-size: 14px; color: #475569; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            """
        )

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155;")
        return label

    # ------------------------------------------------------------------ gallery helpers

    def _rebuild_gallery(self, gallery_layout: QHBoxLayout, image_paths: list[str], is_correct: bool) -> None:
        """Clear and rebuild a thumbnail gallery from image paths."""
        # Remove existing widgets
        while gallery_layout.count():
            item = gallery_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for i, path in enumerate(image_paths):
            card = _ThumbnailCard(i, path)
            if is_correct:
                card.delete_requested.connect(self.remove_correct_sample_requested.emit)
            else:
                card.delete_requested.connect(self.remove_incorrect_sample_requested.emit)
            gallery_layout.addWidget(card)

        gallery_layout.addStretch(1)

    # ------------------------------------------------------------------ public API

    def go_to_page(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def reset(self) -> None:
        self._calibration_count = 0
        self._phase = "correct"
        self.calibration_status.setText("请先拍摄 3 张正确坐姿照片")
        self.calibration_status.setStyleSheet("")
        self.calibration_progress.setText("")
        self.next_btn_1.setEnabled(False)
        self._capture_correct_btn.setEnabled(True)
        self._capture_incorrect_btn.setEnabled(False)
        self._correct_status.setText("")
        self._incorrect_status.setText("")
        self._rebuild_gallery(self._correct_gallery, [], True)
        self._rebuild_gallery(self._incorrect_gallery, [], False)
        self.preview_label.setText("等待实时画面...")
        self.preview_label.setStyleSheet("background: #1e293b; color: #94a3b8; font-size: 16px;")
        self.preview_status.setText("状态: 等待开始")
        self.go_to_page(0)

    def update_calibration_status(self, payload: dict) -> None:
        """Update calibration UI from controller status payload."""
        phase = str(payload.get("phase", ""))
        captured_correct = int(payload.get("captured_correct", 0))
        required_correct = int(payload.get("required_correct", 3))
        captured_incorrect = int(payload.get("captured_incorrect", 0))
        required_incorrect = int(payload.get("required_incorrect", 2))
        message = str(payload.get("message", ""))
        correct_paths = list(payload.get("correct_image_paths", []))
        incorrect_paths = list(payload.get("incorrect_image_paths", []))

        # Rebuild galleries
        self._rebuild_gallery(self._correct_gallery, correct_paths, True)
        self._rebuild_gallery(self._incorrect_gallery, incorrect_paths, False)

        # Progress dots
        total_required = required_correct + required_incorrect
        total_captured = captured_correct + captured_incorrect
        progress = ""
        for i in range(total_required):
            progress += "● " if i < total_captured else "○ "
        self.calibration_progress.setText(progress.strip())

        # Phase-specific text
        self._correct_status.setText(f"已拍摄 {captured_correct}/{required_correct}")
        self._incorrect_status.setText(f"已拍摄 {captured_incorrect}/{required_incorrect}")

        # Overall status
        self.calibration_status.setText(message)

        # Button states
        if phase in ("correct_done", "collecting_incorrect"):
            self._capture_correct_btn.setEnabled(False)
            self._capture_incorrect_btn.setEnabled(True)
            self.next_btn_1.setEnabled(False)
        elif phase == "completed":
            self.calibration_status.setStyleSheet(
                "font-size: 15px; font-weight: 600; color: #16a34a; "
                "padding: 14px; background: rgba(22,163,74,0.1); border-radius: 10px;"
            )
            self._capture_correct_btn.setEnabled(False)
            self._capture_incorrect_btn.setEnabled(False)
            self.next_btn_1.setEnabled(True)
        elif phase == "error" and captured_correct >= required_correct:
            # Error during incorrect phase
            self._capture_correct_btn.setEnabled(False)
            self._capture_incorrect_btn.setEnabled(True)
        else:
            # Still collecting correct, or error during correct phase
            self._capture_correct_btn.setEnabled(True)
            self._capture_incorrect_btn.setEnabled(False)
            self.next_btn_1.setEnabled(False)

    def update_preview_frame(self, frame: Any, status: str = "") -> None:
        if frame is None:
            return
        try:
            shape = getattr(frame, "shape", None)
            if not isinstance(shape, tuple) or len(shape) < 2:
                return
            frame_height, frame_width = shape[0], shape[1]
            if frame_height <= 0 or frame_width <= 0:
                return

            # 创建 QImage，需要确保数据在 QImage 使用期间有效
            # 关键：先复制 frame 数据，再传给 QImage
            if len(shape) >= 3 and shape[2] >= 3:
                # BGR 转 RGB (OpenCV 使用 BGR 格式，Qt 需要 RGB)
                # 先深拷贝 frame 的数据，避免 view 问题
                rgb_data = frame[:, :, :3][:, :, ::-1].copy()
                # 现在可以从 rgb_data 创建 QImage，因为 rgb_data 拥有独立的数据
                image = QImage(rgb_data.data, frame_width, frame_height, 3 * frame_width, QImage.Format_RGB888)
                # 清理临时数据
                del rgb_data
            else:
                # 灰度图
                gray_data = frame.copy()
                image = QImage(gray_data.data, frame_width, frame_height, frame_width, QImage.Format_Grayscale8)
                del gray_data

            if image.isNull():
                return

            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return

            # 设置缩放后的 pixmap 到预览标签
            target_size = self.preview_label.size()
            if not target_size.isEmpty():
                scaled = pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.FastTransformation)
                self.preview_label.setPixmap(scaled)

            if status:
                status_text = {
                    "correct": "✅ 检测正确",
                    "incorrect": "⚠️ 检测错误",
                    "unknown": "❓ 未检测到用户",
                }.get(status, f"状态: {status}")
                self.preview_status.setText(status_text)

        except Exception:
            pass

    def load_settings(self, settings: Any) -> None:
        self._current_settings = {
            "capture_interval_seconds": getattr(settings, "capture_interval_seconds", 30),
            "detection_mode": getattr(settings, "detection_mode", "strict"),
            "reminder_method": getattr(settings, "reminder_method", "dim_screen"),
            "screen_time_enabled": getattr(settings, "screen_time_enabled", False),
            "screen_time_threshold_minutes": getattr(settings, "screen_time_threshold_minutes", 60),
            "retention_days": getattr(settings, "retention_days", 7),
        }
        self.capture_interval.setValue(self._current_settings["capture_interval_seconds"])
        self.retention.setValue(self._current_settings["retention_days"])
        self.screen_time_enabled.setChecked(self._current_settings["screen_time_enabled"])
        self.screen_time_threshold.setValue(self._current_settings["screen_time_threshold_minutes"])
        mode_index = self.detection_mode.findData(self._current_settings["detection_mode"])
        if mode_index >= 0:
            self.detection_mode.setCurrentIndex(mode_index)
        method_index = self.reminder_method.findData(self._current_settings["reminder_method"])
        if method_index >= 0:
            self.reminder_method.setCurrentIndex(method_index)

    # ------------------------------------------------------------------ private slots

    def _emit_settings_change(self) -> None:
        payload = {
            "capture_interval_seconds": self.capture_interval.value(),
            "detection_mode": self.detection_mode.currentData(),
            "reminder_method": self.reminder_method.currentData(),
            "screen_time_enabled": self.screen_time_enabled.isChecked(),
            "screen_time_threshold_minutes": self.screen_time_threshold.value(),
            "retention_days": self.retention.value(),
        }
        self.settings_changed.emit(payload)

    def _on_start_detection_clicked(self) -> None:
        self.start_detection_requested.emit()

    def _on_finish_clicked(self) -> None:
        self.finish_onboarding_requested.emit()

    def cleanup(self):
        """清理资源，释放 pixmap 占用的内存"""
        try:
            self.preview_label.clear()
            self.preview_label.setPixmap(QPixmap())
        except Exception:
            pass

    def __del__(self):
        """析构函数，确保资源被释放"""
        try:
            self.cleanup()
        except Exception:
            pass
