from __future__ import annotations

from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QWidget


class _HoverShadowFilter(QObject):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def _apply_shadow(
        button: QPushButton,
        *,
        blur_radius: float,
        color: QColor,
        y_offset: float,
    ) -> None:
        effect = button.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            effect = QGraphicsDropShadowEffect(button)
            button.setGraphicsEffect(effect)
        effect.setBlurRadius(blur_radius)
        effect.setColor(color)
        effect.setOffset(0.0, y_offset)

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if isinstance(obj, QPushButton):
            if event.type() == QEvent.Enter:
                # Hover: stronger shadow + slight lift for a "floating glass" feel
                self._apply_shadow(
                    obj,
                    blur_radius=22.0,
                    color=QColor(2, 132, 199, 70),  # subtle cyan tint
                    y_offset=6.0,
                )
            elif event.type() == QEvent.Leave:
                self._apply_shadow(
                    obj,
                    blur_radius=10.0,
                    color=QColor(15, 23, 42, 35),
                    y_offset=3.0,
                )
            elif event.type() == QEvent.MouseButtonPress:
                self._apply_shadow(
                    obj,
                    blur_radius=8.0,
                    color=QColor(15, 23, 42, 28),
                    y_offset=1.0,
                )
            elif event.type() == QEvent.MouseButtonRelease:
                # Return to hover or normal depending on cursor state
                if obj.underMouse():
                    self._apply_shadow(
                        obj,
                        blur_radius=22.0,
                        color=QColor(2, 132, 199, 70),
                        y_offset=6.0,
                    )
                else:
                    self._apply_shadow(
                        obj,
                        blur_radius=10.0,
                        color=QColor(15, 23, 42, 35),
                        y_offset=3.0,
                    )
        return super().eventFilter(obj, event)


def install_hover_shadows(root: QWidget) -> None:
    """Install consistent hover shadows on all QPushButton under root."""
    filt = _HoverShadowFilter()
    # Keep filter alive by parenting it to root.
    filt.setParent(root)

    for button in root.findChildren(QPushButton):
        # Baseline shadow
        _HoverShadowFilter._apply_shadow(
            button,
            blur_radius=10.0,
            color=QColor(15, 23, 42, 35),
            y_offset=3.0,
        )
        button.installEventFilter(filt)

