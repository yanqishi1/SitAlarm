from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QRectF, QSize, Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import (
    QAction,
    QAbstractItemView,
    QHBoxLayout,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
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


class SideNavDelegate(QStyledItemDelegate):
    """Custom nav painting keeps icons crisp and centered, with subtle selected state."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform, True)

        visual_rect = option.rect.adjusted(6, 6, -6, -6)
        item_rect = QRectF(visual_rect)
        radius = 14.0

        if option.state & QStyle.State_Selected:
            glow_gradient = QLinearGradient(item_rect.topLeft(), item_rect.bottomRight())
            glow_gradient.setColorAt(0.0, QColor(255, 255, 255, 145))
            glow_gradient.setColorAt(1.0, QColor(251, 191, 36, 88))
            painter.setBrush(glow_gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(item_rect, radius, radius)

            border_gradient = QLinearGradient(item_rect.topLeft(), item_rect.bottomRight())
            border_gradient.setColorAt(0.0, QColor(255, 255, 255, 245))
            border_gradient.setColorAt(1.0, QColor(251, 146, 60, 228))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(border_gradient, 1.5))
            painter.drawRoundedRect(item_rect.adjusted(0.75, 0.75, -0.75, -0.75), radius - 1, radius - 1)
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(148, 163, 184, 28))
            painter.drawRoundedRect(item_rect, radius, radius)

        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            icon_size = option.decorationSize if option.decorationSize.isValid() else QSize(22, 22)
            ratio = option.widget.devicePixelRatioF() if option.widget else 1.0
            pixmap = icon.pixmap(int(icon_size.width() * ratio), int(icon_size.height() * ratio))
            pixmap.setDevicePixelRatio(ratio)

            x = int(option.rect.x() + (option.rect.width() - icon_size.width()) / 2)
            y = int(option.rect.y() + (option.rect.height() - icon_size.height()) / 2)
            painter.drawPixmap(x, y, pixmap)

        painter.restore()


class MainWindow(QMainWindow):
    def __init__(self, controller: SitAlarmController) -> None:
        super().__init__()
        self._log = logging.getLogger(__name__)
        self.controller = controller
        self.today_summary = DaySummary(datetime.now().date(), 0, 0, 0)
        self._allow_close = False
        self.last_history: list[DaySummary] = []
        self.today_detection_start: datetime | None = None
        self.today_records: list[dict[str, str]] = []
        self._calibration_prompted = False

        self.setWindowTitle("SitAlarm - 坐姿提醒")
        self.resize(1120, 720)
        self.setMinimumSize(960, 620)
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
        self.side_nav.setViewMode(QListView.IconMode)
        self.side_nav.setFlow(QListView.TopToBottom)
        self.side_nav.setMovement(QListView.Static)
        self.side_nav.setResizeMode(QListView.Adjust)
        self.side_nav.setGridSize(QSize(56, 56))
        self.side_nav.setSelectionMode(QAbstractItemView.SingleSelection)
        self.side_nav.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.side_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.side_nav.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.side_nav.setFixedWidth(74)
        self.side_nav.setItemDelegate(SideNavDelegate(self.side_nav))

        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")
        self.pages.addWidget(self.dashboard_tab)
        self.pages.addWidget(self.stats_tab)
        self.pages.addWidget(self.debug_tab)
        self.pages.addWidget(self.settings_tab)

        items = [
            ("首页", self._load_nav_icon("index.png", QStyle.SP_ComputerIcon)),
            ("统计", self._load_nav_icon("statistic.png", QStyle.SP_FileDialogDetailedView)),
            ("摄像头调试", self._load_nav_icon("video.png", QStyle.SP_MediaPlay)),
            ("设置", self._load_nav_icon("setting.png", QStyle.SP_FileDialogContentsView)),
        ]
        for label, icon in items:
            it = QListWidgetItem(icon, "")
            it.setToolTip(label)
            it.setSizeHint(QSize(56, 56))
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.side_nav.addItem(it)

        self.side_nav.setCurrentRow(0)

        row.addWidget(self.side_nav, 0)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(container)

        # Hover shadows for buttons (glass floating effect)
        install_hover_shadows(self)

        self._setup_tray()
        self._wire_events()
        self._apply_initial_window_size()

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
        self.controller.detection_start_updated.connect(self._update_detection_start)
        self.controller.posture_records_updated.connect(self._update_posture_records)
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

    def _load_nav_icon(self, file_name: str, fallback_style_icon: QStyle.StandardPixmap) -> QIcon:
        icon_path = Path(__file__).resolve().parents[1] / "assets" / file_name
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
        return self.style().standardIcon(fallback_style_icon)

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
        self.stats_tab.update_statistics(self.last_history, summary, self.today_detection_start)

    def _update_history(self, history: list[DaySummary]) -> None:
        self.last_history = history
        self.stats_tab.update_statistics(history, self.today_summary, self.today_detection_start)


    def _update_detection_start(self, start_time: datetime | None) -> None:
        self.today_detection_start = start_time
        self.stats_tab.update_statistics(self.last_history, self.today_summary, start_time)

    def _update_posture_records(self, records: list[object]) -> None:
        normalized: list[dict[str, str]] = []
        for record in records:
            captured_at = getattr(record, "captured_at", None)
            status = str(getattr(record, "status", "unknown"))
            if hasattr(captured_at, "strftime"):
                timestamp = captured_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp = "-"
            normalized.append({"captured_at": timestamp, "status": status})

        self.today_records = normalized
        self.stats_tab.update_posture_records(normalized)

    def _show_reminder(self, message: str) -> None:
        self._log.info("Show reminder. method=%s message=%s", getattr(self.controller.settings, "reminder_method", None), message)
        # Keep the latest message visible even if user switches back later.
        self.dashboard_tab.set_current_message(message)
        self.tray_icon.showMessage("SitAlarm 提醒", message, QSystemTrayIcon.Warning, 5000)
        # In practice users expect both cues when posture is incorrect.
        self._screen_dimmer.flash(strength=0.7, duration_ms=1800)
        self._reminder_toast.show_message(message, duration_ms=5000)

    def _apply_initial_window_size(self) -> None:
        available = self.screen().availableGeometry() if self.screen() else None
        if available is None:
            return

        target_width = min(1120, int(available.width() * 0.82))
        target_height = min(720, int(available.height() * 0.82))
        target_width = max(target_width, self.minimumWidth())
        target_height = max(target_height, self.minimumHeight())
        self.resize(target_width, target_height)

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
