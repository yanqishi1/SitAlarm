from __future__ import annotations

import sys
from pathlib import Path

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

    app.setStyleSheet(build_glass_theme())

    db_path = get_database_path()
    storage = Storage(db_path)
    settings_service = SettingsService(storage)
    stats_service = StatsService(storage)
    controller = SitAlarmController(storage, settings_service, stats_service)

    window = MainWindow(controller)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
