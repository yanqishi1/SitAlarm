from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PyQt5.QtCore import QPointF, QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


@dataclass
class Particle:
    pos: QPointF
    velocity: QPointF
    life: int
    max_life: int
    size: float
    color: QColor


class ReminderToast(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumWidth(300)
        self.message_label.setMaximumWidth(390)
        self.message_label.setStyleSheet(
            """
            QLabel {
                background: rgba(255, 245, 248, 238);
                border: 1px solid rgba(255, 133, 133, 236);
                border-radius: 16px;
                padding: 15px;
                color: #9a1515;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )
        layout.addWidget(self.message_label)

        self._particles: list[Particle] = []
        self._burst_ticks = 0

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self._particle_timer = QTimer(self)
        self._particle_timer.timeout.connect(self._tick_particles)
        self._particle_timer.start(16)

    def show_message(self, message: str, duration_ms: int = 5000) -> None:
        if not message:
            return

        self.message_label.setText(message)
        self.adjustSize()
        self._move_to_top_right()
        self._start_fireworks()
        self.show()
        self.raise_()
        self._hide_timer.start(max(1800, duration_ms))

    def _start_fireworks(self) -> None:
        self._particles.clear()
        self._burst_ticks = 45
        for _ in range(2):
            self._spawn_burst()

    def _spawn_burst(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        center = QPointF(
            random.uniform(26.0, max(28.0, self.width() - 26.0)),
            random.uniform(22.0, max(24.0, self.height() - 22.0)),
        )
        palette = [
            QColor(255, 77, 109),
            QColor(255, 168, 84),
            QColor(130, 214, 255),
            QColor(254, 238, 131),
            QColor(199, 156, 255),
        ]

        for _ in range(30):
            angle = random.uniform(0, 6.283)
            speed = random.uniform(1.2, 3.4)
            velocity = QPointF(speed * math.cos(angle), speed * math.sin(angle))
            self._particles.append(
                Particle(
                    pos=QPointF(center),
                    velocity=velocity,
                    life=random.randint(26, 44),
                    max_life=44,
                    size=random.uniform(1.8, 3.8),
                    color=random.choice(palette),
                )
            )

    def _tick_particles(self) -> None:
        if not self._particles and self._burst_ticks <= 0:
            return

        if self._burst_ticks > 0 and self._burst_ticks % 14 == 0:
            self._spawn_burst()

        self._burst_ticks = max(0, self._burst_ticks - 1)

        alive: list[Particle] = []
        for particle in self._particles:
            particle.life -= 1
            if particle.life <= 0:
                continue

            particle.velocity = QPointF(particle.velocity.x() * 0.98, particle.velocity.y() * 0.98 + 0.05)
            particle.pos = QPointF(particle.pos.x() + particle.velocity.x(), particle.pos.y() + particle.velocity.y())
            alive.append(particle)

        self._particles = alive
        self.update()

    def _move_to_top_right(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        geom = screen.availableGeometry()
        x = geom.right() - self.width() - 24
        y = geom.top() + 24
        self.move(max(0, x), max(0, y))

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.isVisible():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 110, 120, 34))
            painter.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 18, 18)

        for particle in self._particles:
            alpha = int(255 * (particle.life / max(1, particle.max_life)))
            color = QColor(particle.color)
            color.setAlpha(max(0, min(alpha, 255)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(particle.pos, particle.size, particle.size)

        if self._particles:
            pulse_alpha = 120 + (self._burst_ticks % 24) * 4
            painter.setPen(QPen(QColor(255, 120, 120, min(220, pulse_alpha)), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)

        super().paintEvent(event)

