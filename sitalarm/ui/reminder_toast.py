from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget


class ReminderToast(QWidget):
    """Lightweight reminder toast to avoid high CPU usage from particle effects."""

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(360, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumWidth(320)
        self.message_label.setMaximumWidth(440)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet(
            """
            QLabel {
                background: rgba(255, 255, 255, 248);
                border: 1px solid rgba(15, 23, 42, 22);
                border-radius: 18px;
                padding: 18px 22px;
                color: rgba(15, 23, 42, 240);
                font-size: 16px;
                font-weight: 700;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
            }
            """
        )
        layout.addWidget(self.message_label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_animation.setDuration(180)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_animation.finished.connect(self._on_fade_finished)
        self._fading_out = False

    def show_message(self, message: str, duration_ms: int = 6000) -> None:
        message = str(message or "").strip()
        if not message:
            return

        self._hide_timer.stop()
        self._fading_out = False

        self.message_label.setText(message)
        self.adjustSize()
        self._move_to_top_right()
        self.show()
        self.raise_()

        self._fade_animation.stop()
        self._fade_animation.setStartValue(float(self._opacity_effect.opacity()))
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

        self._hide_timer.start(max(2500, int(duration_ms)))

    def _fade_out(self) -> None:
        self._fading_out = True
        self._fade_animation.stop()
        self._fade_animation.setStartValue(float(self._opacity_effect.opacity()))
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _on_fade_finished(self) -> None:
        if self._fading_out and self._opacity_effect.opacity() <= 0.01:
            self.hide()
            self._fading_out = False

    def _move_to_top_right(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        geom = screen.availableGeometry()
        x = geom.right() - self.width() - 24
        y = geom.top() + 24
        self.move(max(0, x), max(0, y))
