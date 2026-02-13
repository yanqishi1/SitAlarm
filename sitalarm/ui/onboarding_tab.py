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
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class OnboardingTab(QWidget):
    """引导页面：帮助用户完成首次配置（集成实时预览和设置）"""

    calibration_requested = pyqtSignal()  # 请求拍摄校准照片
    finish_onboarding_requested = pyqtSignal()  # 完成引导
    start_detection_requested = pyqtSignal()  # 开始检测
    # 设置相关信号
    settings_changed = pyqtSignal(dict)  # 设置变更

    def __init__(self) -> None:
        super().__init__()
        self._calibration_count = 0
        self._build_ui()
        self._current_settings: dict = {}

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 主堆叠窗口
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        # 创建各个引导页面
        self.welcome_page = self._create_welcome_page()
        self.calibration_page = self._create_calibration_page()
        self.preview_page = self._create_preview_page()
        self.settings_page = self._create_settings_page()
        self.finish_page = self._create_finish_page()

        self.stack.addWidget(self.welcome_page)
        self.stack.addWidget(self.calibration_page)
        self.stack.addWidget(self.preview_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.finish_page)

        # 应用样式
        self._apply_styles()

    def _create_welcome_page(self) -> QWidget:
        """欢迎页面"""
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

        steps = QLabel(
            "📸 拍摄校准照片  →  👁️ 预览检测效果  →  ⚙️ 配置检测参数"
        )
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
        """校准页面 - 拍摄两张正确姿势照片"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        step_indicator = QLabel("步骤 1 / 4")
        step_indicator.setObjectName("StepIndicator")
        layout.addWidget(step_indicator)

        title = QLabel("拍摄校准照片")
        title.setObjectName("OnboardingTitle")
        layout.addWidget(title)

        desc = QLabel(
            "请调整摄像头，确保您在画面中央，然后拍摄 2 张正确坐姿的照片。\n"
            "系统将根据这些照片计算您的头占比阈值，用于后续检测。\n\n"
            "💡 正确坐姿要点："
        )
        desc.setObjectName("OnboardingDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        tips = QLabel(
            "• 头部正直，耳朵与肩膀保持垂直\n"
            "• 眼睛与屏幕保持适当距离（约50-70cm）\n"
            "• 肩膀放松，背部挺直"
        )
        tips.setObjectName("TipsList")
        tips.setWordWrap(True)
        layout.addWidget(tips)

        layout.addSpacing(16)

        self.calibration_status = QLabel("未开始校准")
        self.calibration_status.setObjectName("CalibrationStatus")
        self.calibration_status.setAlignment(Qt.AlignCenter)
        self.calibration_status.setMinimumHeight(50)
        layout.addWidget(self.calibration_status)

        self.calibration_progress = QLabel("○ ○")
        self.calibration_progress.setObjectName("CalibrationProgress")
        self.calibration_progress.setAlignment(Qt.AlignCenter)
        self.calibration_progress.setStyleSheet("font-size: 24px; letter-spacing: 10px;")
        layout.addWidget(self.calibration_progress)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        self.back_btn_1 = QPushButton("返回")
        self.back_btn_1.setObjectName("SecondaryButton")
        self.back_btn_1.setFixedSize(100, 40)
        self.back_btn_1.clicked.connect(lambda: self.go_to_page(0))
        btn_layout.addWidget(self.back_btn_1)

        self.capture_btn = QPushButton("拍摄照片")
        self.capture_btn.setObjectName("PrimaryButton")
        self.capture_btn.setFixedSize(120, 40)
        self.capture_btn.clicked.connect(self._on_capture_clicked)
        btn_layout.addWidget(self.capture_btn)

        self.next_btn_1 = QPushButton("下一步")
        self.next_btn_1.setObjectName("PrimaryButton")
        self.next_btn_1.setFixedSize(100, 40)
        self.next_btn_1.setEnabled(False)
        self.next_btn_1.clicked.connect(lambda: self.go_to_page(2))
        btn_layout.addWidget(self.next_btn_1)

        layout.addLayout(btn_layout)

        return page

    def _create_preview_page(self) -> QWidget:
        """实时预览页面 - 集成实时画面显示"""
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

        # 实时画面显示区域
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

        # 状态显示
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
        """设置页面 - 集成设置控件"""
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

        # 设置卡片
        settings_card = QFrame()
        settings_card.setObjectName("SettingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(20)

        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(16)
        form.setColumnStretch(1, 1)

        # 检测模式
        self.detection_mode = QComboBox()
        self.detection_mode.addItem("严格", "strict")
        self.detection_mode.addItem("正常", "normal")
        self.detection_mode.addItem("宽松", "loose")
        self.detection_mode.setObjectName("WideInput")
        self.detection_mode.currentTextChanged.connect(self._emit_settings_change)
        form.addWidget(self._field_label("检测模式"), 0, 0)
        form.addWidget(self.detection_mode, 0, 1)

        # 提醒方式
        self.reminder_method = QComboBox()
        self.reminder_method.addItem("降低屏幕亮度 (默认)", "dim_screen")
        self.reminder_method.addItem("弹出框提醒", "popup")
        self.reminder_method.setObjectName("WideInput")
        self.reminder_method.currentTextChanged.connect(self._emit_settings_change)
        form.addWidget(self._field_label("提醒方式"), 1, 0)
        form.addWidget(self.reminder_method, 1, 1)

        # 检测间隔
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

        # 图片保留天数
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

        # 屏幕超时提醒
        self.screen_time_enabled = QCheckBox("启用屏幕超时提醒")
        self.screen_time_enabled.stateChanged.connect(self._emit_settings_change)
        form.addWidget(self.screen_time_enabled, 4, 0, 1, 2)

        # 屏幕超时时间
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
        """完成页面"""
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

    def _apply_styles(self) -> None:
        """应用样式"""
        self.setStyleSheet(
            """
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
            }
            
            QLabel#OnboardingTitle {
                font-size: 28px;
                font-weight: 700;
                color: #1e293b;
                margin-bottom: 4px;
            }
            
            QLabel#OnboardingDesc {
                font-size: 15px;
                color: #475569;
                line-height: 1.6;
            }
            
            QLabel#StepIndicator {
                font-size: 13px;
                font-weight: 600;
                color: #fb923c;
                padding: 4px 12px;
                background: rgba(251, 146, 60, 0.15);
                border-radius: 16px;
            }
            
            QLabel#OnboardingSteps {
                font-size: 14px;
                color: #64748b;
                padding: 12px;
                background: rgba(241, 245, 249, 0.8);
                border-radius: 10px;
            }
            
            QLabel#TipsList {
                font-size: 14px;
                color: #475569;
                background: rgba(241, 245, 249, 0.8);
                padding: 14px 18px;
                border-radius: 10px;
                border-left: 4px solid #fb923c;
            }
            
            QLabel#CalibrationStatus {
                font-size: 15px;
                font-weight: 600;
                color: #475569;
                padding: 14px;
                background: rgba(241, 245, 249, 0.8);
                border-radius: 10px;
            }
            
            QLabel#PreviewStatus {
                font-size: 14px;
                font-weight: 600;
                color: #475569;
                padding: 8px;
            }
            
            QFrame#PreviewCard, QFrame#SettingsCard {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(251, 146, 60, 0.3);
                border-radius: 14px;
            }
            
            QLabel#HintText {
                font-size: 13px;
                color: #64748b;
                font-style: italic;
            }
            
            QPushButton#PrimaryButton {
                background: #fb923c;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 20px;
            }
            
            QPushButton#PrimaryButton:hover {
                background: #f97316;
            }
            
            QPushButton#PrimaryButton:disabled {
                background: #cbd5e1;
                color: #94a3b8;
            }
            
            QPushButton#SecondaryButton {
                background: rgba(241, 245, 249, 0.8);
                color: #475569;
                border: 1px solid rgba(148, 163, 184, 0.3);
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 20px;
            }
            
            QPushButton#SecondaryButton:hover {
                background: rgba(226, 232, 240, 0.8);
            }
            
            QComboBox, QSpinBox {
                padding: 6px 10px;
                border: 1px solid rgba(148, 163, 184, 0.4);
                border-radius: 6px;
                background: white;
                font-size: 14px;
            }
            
            QComboBox:focus, QSpinBox:focus {
                border-color: #fb923c;
            }
            
            QCheckBox {
                font-size: 14px;
                color: #475569;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            """
        )

    def _field_label(self, text: str) -> QLabel:
        """创建设置字段标签"""
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155;")
        return label

    def go_to_page(self, index: int) -> None:
        """跳转到指定页面"""
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def reset(self) -> None:
        """重置引导状态"""
        self._calibration_count = 0
        self.calibration_status.setText("未开始校准")
        self.calibration_status.setProperty("status", "")
        self.calibration_status.setStyleSheet("")
        self.calibration_progress.setText("○ ○")
        self.next_btn_1.setEnabled(False)
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("拍摄照片")
        self.preview_label.setText("等待实时画面...")
        self.preview_label.setStyleSheet("background: #1e293b; color: #94a3b8; font-size: 16px;")
        self.preview_status.setText("状态: 等待开始")
        self.go_to_page(0)

    def update_calibration_status(self, captured: int, required: int, message: str) -> None:
        """更新校准状态"""
        self._calibration_count = captured
        self.calibration_status.setText(message)
        
        progress = ""
        for i in range(required):
            if i < captured:
                progress += "● "
            else:
                progress += "○ "
        self.calibration_progress.setText(progress.strip())
        
        if captured >= required:
            self.calibration_status.setStyleSheet(
                "font-size: 15px; font-weight: 600; color: #16a34a; "
                "padding: 14px; background: rgba(22, 163, 74, 0.1); border-radius: 10px;"
            )
            self.next_btn_1.setEnabled(True)
            self.capture_btn.setEnabled(False)
            self.capture_btn.setText("校准完成")

    def update_preview_frame(self, frame: Any, status: str = "") -> None:
        """更新实时预览画面"""
        if frame is None:
            return
        
        try:
            shape = getattr(frame, "shape", None)
            if not isinstance(shape, tuple) or len(shape) < 2:
                return
            
            frame_height, frame_width = shape[0], shape[1]
            if frame_height <= 0 or frame_width <= 0:
                return
            
            # 转换为 QImage
            if len(shape) >= 3 and shape[2] >= 3:
                rgb = frame[:, :, :3][:, :, ::-1].copy()
                image = QImage(rgb.data, frame_width, frame_height, 3 * frame_width, QImage.Format_RGB888)
            else:
                gray = frame.copy()
                image = QImage(gray.data, frame_width, frame_height, frame_width, QImage.Format_Grayscale8)
            
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return
            
            # 缩放到固定尺寸
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            
            if status:
                status_text = {
                    "correct": "✅ 检测正确",
                    "incorrect": "⚠️ 检测错误",
                    "unknown": "❓ 未检测到用户"
                }.get(status, f"状态: {status}")
                self.preview_status.setText(status_text)
                
        except Exception:
            pass

    def load_settings(self, settings: Any) -> None:
        """加载设置值到控件"""
        self._current_settings = {
            "capture_interval_seconds": getattr(settings, "capture_interval_seconds", 30),
            "detection_mode": getattr(settings, "detection_mode", "strict"),
            "reminder_method": getattr(settings, "reminder_method", "dim_screen"),
            "screen_time_enabled": getattr(settings, "screen_time_enabled", False),
            "screen_time_threshold_minutes": getattr(settings, "screen_time_threshold_minutes", 60),
            "retention_days": getattr(settings, "retention_days", 7),
        }
        
        # 设置控件值
        self.capture_interval.setValue(self._current_settings["capture_interval_seconds"])
        self.retention.setValue(self._current_settings["retention_days"])
        self.screen_time_enabled.setChecked(self._current_settings["screen_time_enabled"])
        self.screen_time_threshold.setValue(self._current_settings["screen_time_threshold_minutes"])
        
        # 设置下拉框
        mode_index = self.detection_mode.findData(self._current_settings["detection_mode"])
        if mode_index >= 0:
            self.detection_mode.setCurrentIndex(mode_index)
        
        method_index = self.reminder_method.findData(self._current_settings["reminder_method"])
        if method_index >= 0:
            self.reminder_method.setCurrentIndex(method_index)

    def _emit_settings_change(self) -> None:
        """发送设置变更信号"""
        payload = {
            "capture_interval_seconds": self.capture_interval.value(),
            "detection_mode": self.detection_mode.currentData(),
            "reminder_method": self.reminder_method.currentData(),
            "screen_time_enabled": self.screen_time_enabled.isChecked(),
            "screen_time_threshold_minutes": self.screen_time_threshold.value(),
            "retention_days": self.retention.value(),
        }
        self.settings_changed.emit(payload)

    def _on_capture_clicked(self) -> None:
        """拍摄照片按钮点击"""
        self.calibration_requested.emit()

    def _on_start_detection_clicked(self) -> None:
        """开始检测按钮点击"""
        self.start_detection_requested.emit()

    def _on_finish_clicked(self) -> None:
        """完成按钮点击"""
        self.finish_onboarding_requested.emit()
