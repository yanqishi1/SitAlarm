from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from sitalarm.app_logging import configure_logging
from sitalarm.config import get_database_path
from sitalarm.controller import SitAlarmController
from sitalarm.services.settings_service import SettingsService
from sitalarm.services.stats_service import StatsService
from sitalarm.services.storage import Storage
from sitalarm.ui.main_window import MainWindow
from sitalarm.ui.theme import build_glass_theme


def _load_app_icon() -> QIcon:
    """Load application icon for dock and taskbar."""
    logo_path = Path(__file__).resolve().parent / "logo.png"
    if logo_path.exists():
        icon = QIcon(str(logo_path))
        if not icon.isNull():
            return icon
    return QIcon()


def main() -> int:
    configure_logging("SitAlarm")
    app = QApplication(sys.argv)

    # Set application metadata for macOS
    app.setApplicationName("SitAlarm")
    app.setOrganizationName("SitAlarm")
    app.setOrganizationDomain("sitalarm.local")

    # Set application icon for dock/taskbar
    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Prevent app from quitting when last window is closed (for tray mode)
    app.setQuitOnLastWindowClosed(False)
    # 允许在退出时关闭应用
    app.setQuitLockEnabled(False)

    app.setStyleSheet(build_glass_theme())

    db_path = get_database_path()
    storage = Storage(db_path)
    settings_service = SettingsService(storage)
    stats_service = StatsService(storage)
    controller = SitAlarmController(storage, settings_service, stats_service)

    window = MainWindow(controller)
    window.show()

    # 确保应用退出时正确清理资源
    def cleanup_resources():
        """清理所有资源并退出应用"""
        # 停止控制器
        controller.stop()
        # 停止实时预览
        controller.stop_live_debug()
        # 隐藏窗口
        window.hide()
        # 清理托盘图标
        if hasattr(window, 'tray_icon'):
            window.tray_icon.hide()
        # 清理提醒弹窗
        if hasattr(window, '_reminder_toast'):
            window._reminder_toast.hide()
        # 清理屏幕变暗覆盖
        if hasattr(window, '_screen_dimmer'):
            window._screen_dimmer.hide()

        # 延迟调用 QApplication.quit()，确保所有事件处理完成
        QTimer.singleShot(100, QApplication.quit)

    app.aboutToQuit.connect(cleanup_resources)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
