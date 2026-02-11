from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QSize, Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
    QStackedWidget,
    QWidget,
)

from sitalarm.controller import SitAlarmController
from sitalarm.services.stats_service import DaySummary
from sitalarm.ui.dashboard_tab import DashboardTab
from sitalarm.ui.debug_tab import DebugTab
from sitalarm.ui.effects import install_hover_shadows
from sitalarm.ui.reminder_toast import ReminderToast
from sitalarm.ui.screen_dim_overlay import ScreenDimmer
from sitalarm.ui.settings_tab import SettingsTab
from sitalarm.ui.stats_tab import StatsTab


class MainWindow(QMainWindow):
    def __init__(self, controller: SitAlarmController) -> None:
        super().__init__()
        self._log = logging.getLogger(__name__)
        self.controller = controller
        self.today_summary = DaySummary(datetime.now().date(), 0, 0, 0)
        self._allow_close = False
        self.last_history: list[DaySummary] = []
        self._calibration_prompted = False

        self.setWindowTitle("SitAlarm - 坐姿提醒")
        self.resize(720, 520)
        self.setMinimumSize(620, 460)
        self.setObjectName("RootSurface")
        # Enable semi-transparent window background for frosted glass effect
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # Opaque window (no opacity setting)
        self.setWindowOpacity(1.0)

        self._app_icon = self._load_app_icon()
        self._reminder_toast = ReminderToast()
        self._screen_dimmer = ScreenDimmer()

        self.dashboard_tab = DashboardTab()
        self.stats_tab = StatsTab()
        self.debug_tab = DebugTab()
        self.settings_tab = SettingsTab()

        # Left sidebar navigation (icons centered, top-to-bottom)
        container = QWidget()
        container.setObjectName("MainContainer")
        row = QHBoxLayout(container)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(12)

        self.side_nav = QListWidget()
        self.side_nav.setObjectName("SideNav")
        self.side_nav.setIconSize(QSize(22, 22))
        self.side_nav.setMovement(QListWidget.Static)
        self.side_nav.setSelectionMode(QAbstractItemView.SingleSelection)
        self.side_nav.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.side_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.side_nav.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.side_nav.setFixedWidth(74)

        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")
        self.pages.addWidget(self.dashboard_tab)
        self.pages.addWidget(self.stats_tab)
        self.pages.addWidget(self.debug_tab)
        self.pages.addWidget(self.settings_tab)

        style = self.style()
        items = [
            ("首页", style.standardIcon(QStyle.SP_ComputerIcon)),
            ("统计", style.standardIcon(QStyle.SP_FileDialogDetailedView)),
            ("摄像头调试", style.standardIcon(QStyle.SP_MediaPlay)),
            ("设置", style.standardIcon(QStyle.SP_FileDialogContentsView)),
        ]
        for label, icon in items:
            it = QListWidgetItem(icon, "")
            it.setToolTip(label)
            it.setTextAlignment(Qt.AlignCenter)
            self.side_nav.addItem(it)

        self.side_nav.setCurrentRow(0)

        row.addWidget(self.side_nav, 0)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(container)

        # Hover shadows for buttons (glass floating effect)
        install_hover_shadows(self)

        self._setup_tray()
        self._wire_events()

        self.settings_tab.load_settings(self.controller.settings)
        self.controller.start()
        self._on_nav_changed(self.side_nav.currentRow())

    def _wire_events(self) -> None:
        self.dashboard_tab.run_now_requested.connect(self.controller.run_detection_now)
        self.dashboard_tab.pause_requested.connect(self.controller.pause_detection)
        self.dashboard_tab.resume_requested.connect(self.controller.resume_detection)
        self.debug_tab.debug_capture_requested.connect(self.controller.run_debug_capture)

        self.settings_tab.settings_changed.connect(self._save_settings)
        self.settings_tab.open_capture_dir_requested.connect(self._open_capture_dir)
        self.settings_tab.calibration_capture_requested.connect(self.controller.capture_head_ratio_calibration_sample)
        self.settings_tab.calibration_reset_requested.connect(self.controller.reset_head_ratio_calibration)
        self.settings_tab.preview_camera_requested.connect(self._open_debug_page)

        self.controller.state_changed.connect(self.dashboard_tab.set_state_text)
        self.controller.summary_updated.connect(self._update_day_summary)
        self.controller.history_updated.connect(self._update_history)
        self.controller.event_logged.connect(self.dashboard_tab.set_last_event)
        self.controller.reminder_triggered.connect(self._show_reminder)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.debug_info_updated.connect(self.debug_tab.update_debug_info)
        self.controller.live_debug_frame_updated.connect(self.debug_tab.update_debug_info)
        self.controller.calibration_required.connect(self._show_calibration_required)
        self.controller.calibration_status_updated.connect(self.settings_tab.update_calibration_status)

        self.side_nav.currentRowChanged.connect(self._on_nav_changed)

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._app_icon)
        self.setWindowIcon(self._app_icon)

        menu = QMenu(self)
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.showNormal)

        pause_action = QAction("暂停检测", self)
        pause_action.triggered.connect(self.controller.pause_detection)

        resume_action = QAction("继续检测", self)
        resume_action.triggered.connect(self.controller.resume_detection)

        run_action = QAction("立即检测", self)
        run_action.triggered.connect(self.controller.run_detection_now)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)

        menu.addAction(show_action)
        menu.addAction(pause_action)
        menu.addAction(resume_action)
        menu.addAction(run_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _load_app_icon(self) -> QIcon:
        # 优先使用用户自定义 logo.png，其次退回项目默认图标。
        for logo_path in (
            Path(__file__).resolve().parents[2] / "logo.png",
            Path(__file__).resolve().parents[1] / "assets" / "logo.svg",
        ):
            if not logo_path.exists():
                continue

            icon = QIcon(str(logo_path))
            if not icon.isNull():
                return icon

        return self.style().standardIcon(QStyle.SP_ComputerIcon)

    def _save_settings(self, payload: dict) -> None:
        settings = self.controller.update_settings(**payload)
        self.settings_tab.load_settings(settings)
        self.setWindowOpacity(1.0)
        self.statusBar().showMessage("设置已保存并生效", 3000)

    def _open_capture_dir(self) -> None:
        folder = self.controller.open_today_capture_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _update_day_summary(self, summary: DaySummary) -> None:
        self.today_summary = summary
        self.dashboard_tab.set_day_summary(summary)
        self.stats_tab.update_statistics(self.last_history, summary)

    def _update_history(self, history: list[DaySummary]) -> None:
        self.last_history = history
        self.stats_tab.update_statistics(history, self.today_summary)

    def _show_reminder(self, message: str) -> None:
        self._log.info("Show reminder. method=%s message=%s", getattr(self.controller.settings, "reminder_method", None), message)
        # Keep the latest message visible even if user switches back later.
        self.dashboard_tab.set_current_message(message)
        self.tray_icon.showMessage("SitAlarm 提醒", message, QSystemTrayIcon.Warning, 5000)
        method = str(getattr(self.controller.settings, "reminder_method", "dim_screen") or "dim_screen")
        if method == "popup":
            self._reminder_toast.show_message(message)
        else:
            # Default: dim screen then restore (simulated by overlay) + popup,
            # so users understand what happened.
            self._screen_dimmer.flash(strength=0.55, duration_ms=1100)
            self._reminder_toast.show_message(message, duration_ms=5000)

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)
        self.tray_icon.showMessage("SitAlarm 错误", message, QSystemTrayIcon.Critical, 5000)

    def _show_calibration_required(self, message: str) -> None:
        self._set_current_page(self.settings_tab)
        self.statusBar().showMessage(message, 6000)

        if self._calibration_prompted:
            return

        self._calibration_prompted = True
        QMessageBox.information(self, "SitAlarm 首次校准", message)

    def _on_nav_changed(self, index: int) -> None:
        if index < 0 or index >= self.pages.count():
            return
        self.pages.setCurrentIndex(index)
        current = self.pages.currentWidget()
        if current is self.debug_tab:
            self.controller.start_live_debug()
        else:
            self.controller.stop_live_debug()

    def _open_debug_page(self) -> None:
        self._set_current_page(self.debug_tab)

    def _set_current_page(self, widget: QWidget) -> None:
        idx = self.pages.indexOf(widget)
        if idx >= 0:
            self.side_nav.setCurrentRow(idx)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        self.controller.stop_live_debug()
        self.hide()
        self.tray_icon.showMessage("SitAlarm", "已最小化到托盘，仍在后台检测。", QSystemTrayIcon.Information, 3000)

    def _quit(self) -> None:
        self.controller.stop()
        self._reminder_toast.hide()
        self._screen_dimmer.hide()
        self.tray_icon.hide()
        self._allow_close = True
        self.close()
