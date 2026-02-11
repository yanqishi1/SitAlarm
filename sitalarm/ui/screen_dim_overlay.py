from __future__ import annotations

import logging
from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget


class _DimOverlay(QWidget):
    def __init__(self) -> None:
        # Use SplashScreen instead of Tool to improve "always on top" behavior on macOS,
        # especially when the main window is hidden/minimized to tray.
        super().__init__(None, Qt.FramelessWindowHint | Qt.SplashScreen | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._alpha = 0.0
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_dim_strength(self, strength: float) -> None:
        self._alpha = max(0.0, min(1.0, float(strength)))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, int(255 * self._alpha)))

    def fade_in(self, duration_ms: int = 120) -> None:
        self._anim.stop()
        self._anim.setDuration(max(60, int(duration_ms)))
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def fade_out(self, duration_ms: int = 220) -> None:
        self._anim.stop()
        self._anim.setDuration(max(80, int(duration_ms)))
        self._anim.setStartValue(float(self._opacity_effect.opacity()))
        self._anim.setEndValue(0.0)
        self._anim.start()


class ScreenDimmer:
    """Simulate 'lower screen brightness then restore' using an overlay."""

    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._overlays: list[_DimOverlay] = []
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def flash(self, *, strength: float = 0.35, duration_ms: int = 900) -> None:
        self._log.info("Screen dim flash. strength=%.2f duration_ms=%s", strength, duration_ms)
        self.show(strength=strength)
        self._hide_timer.start(max(120, int(duration_ms)))

    def show(self, *, strength: float = 0.35) -> None:
        app = QApplication.instance()
        if app is None:
            self._log.warning("Screen dim skipped: QApplication instance is None")
            return
        screens = app.screens()
        if not screens:
            self._log.warning("Screen dim skipped: no screens")
            return

        # Ensure overlays count matches screens.
        while len(self._overlays) < len(screens):
            self._overlays.append(_DimOverlay())
        while len(self._overlays) > len(screens):
            overlay = self._overlays.pop()
            overlay.hide()
            overlay.deleteLater()

        for overlay, screen in zip(self._overlays, screens):
            overlay.set_dim_strength(strength)
            overlay.setGeometry(screen.geometry())
            overlay.show()
            overlay.raise_()
            overlay.fade_in()

    def hide(self) -> None:
        self._log.info("Screen dim hide.")
        for overlay in self._overlays:
            overlay.fade_out()
            # Ensure it's actually hidden after animation finishes.
            QTimer.singleShot(260, overlay.hide)

