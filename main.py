from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from sitalarm.config import get_database_path
from sitalarm.controller import SitAlarmController
from sitalarm.services.settings_service import SettingsService
from sitalarm.services.stats_service import StatsService
from sitalarm.services.storage import Storage
from sitalarm.ui.main_window import MainWindow
from sitalarm.ui.theme import build_glass_theme


def main() -> int:
    app = QApplication(sys.argv)
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
