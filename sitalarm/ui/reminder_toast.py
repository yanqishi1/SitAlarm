from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PyQt5.QtCore import QPointF, QPropertyAnimation, QTimer, Qt, QEasingCurve
from PyQt5.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QGraphicsOpacityEffect


@dataclass
class Particle:
    pos: QPointF
    velocity: QPointF
    life: int
    max_life: int
    size: float
    color: QColor
    particle_type: str = "spark"


class ReminderToast(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(380, 140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumWidth(340)
        self.message_label.setMaximumWidth(420)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet(
            """
            QLabel {
                background: rgba(255, 255, 255, 245);
                border: 1px solid rgba(17, 24, 39, 16);
                border-radius: 20px;
                padding: 22px 26px;
                color: rgba(17, 24, 39, 235);
                font-size: 16px;
                font-weight: 700;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
            }
            """
        )
        layout.addWidget(self.message_label)

        self._particles: list[Particle] = []
        self._burst_ticks = 0
        self._glow_phase = 0.0

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._particle_timer = QTimer(self)
        self._particle_timer.timeout.connect(self._tick_particles)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_animation.finished.connect(self._on_fade_finished)
        self._fading_out = False

    def show_message(self, message: str, duration_ms: int = 6000) -> None:
        if not message:
            return

        self._hide_timer.stop()
        self._fading_out = False
        self._opacity_effect.setOpacity(1.0)

        self.message_label.setText(message)
        self.adjustSize()
        self._move_to_top_right()
        self._start_fireworks()

        if not self._particle_timer.isActive():
            self._particle_timer.start(16)

        self.show()
        self.raise_()
        self.activateWindow()
        self._hide_timer.start(max(3000, duration_ms))

    def _fade_out(self) -> None:
        self._fading_out = True
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _on_fade_finished(self) -> None:
        if self._fading_out:
            self.hide()
            self._particle_timer.stop()
            self._particles.clear()
            self._fading_out = False

    def _start_fireworks(self) -> None:
        self._particles.clear()
        self._burst_ticks = 90
        self._glow_phase = 0.0
        for _ in range(4):
            self._spawn_burst()
        self._spawn_ring_particles()

    def _spawn_burst(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        center = QPointF(
            random.uniform(30.0, max(32.0, self.width() - 30.0)),
            random.uniform(26.0, max(28.0, self.height() - 26.0)),
        )
        palette = [
            QColor(255, 100, 180),
            QColor(255, 120, 200),
            QColor(220, 100, 255),
            QColor(180, 100, 255),
            QColor(140, 150, 255),
            QColor(100, 180, 255),
        ]

        for _ in range(40):
            angle = random.uniform(0, 6.283)
            speed = random.uniform(2.0, 5.0)
            velocity = QPointF(speed * math.cos(angle), speed * math.sin(angle))
            self._particles.append(
                Particle(
                    pos=QPointF(center),
                    velocity=velocity,
                    life=random.randint(35, 60),
                    max_life=60,
                    size=random.uniform(2.5, 5.0),
                    color=random.choice(palette),
                    particle_type="spark",
                )
            )

    def _spawn_ring_particles(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        center = QPointF(self.width() / 2, self.height() / 2)
        for i in range(24):
            angle = (i / 24) * 6.283
            radius = min(self.width(), self.height()) * 0.45
            pos = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle),
            )
            self._particles.append(
                Particle(
                    pos=pos,
                    velocity=QPointF(0, 0),
                    life=80,
                    max_life=80,
                    size=3.5,
                    color=QColor(255, 200, 100),
                    particle_type="glow",
                )
            )

    def _tick_particles(self) -> None:
        self._glow_phase += 0.15

        if self._burst_ticks > 0 and self._burst_ticks % 18 == 0:
            self._spawn_burst()

        self._burst_ticks = max(0, self._burst_ticks - 1)

        alive: list[Particle] = []
        for particle in self._particles:
            particle.life -= 1
            if particle.life <= 0:
                continue

            if particle.particle_type == "spark":
                particle.velocity = QPointF(
                    particle.velocity.x() * 0.96,
                    particle.velocity.y() * 0.96 + 0.08
                )
                particle.pos = QPointF(
                    particle.pos.x() + particle.velocity.x(),
                    particle.pos.y() + particle.velocity.y()
                )
            elif particle.particle_type == "glow":
                pulse = math.sin(self._glow_phase + particle.pos.x() * 0.05) * 0.3 + 0.7
                particle.size = 3.5 * pulse

            alive.append(particle)

        self._particles = alive

        if self._burst_ticks > 0 and random.random() < 0.3:
            self._spawn_trail_particle()

        self.update()

    def _spawn_trail_particle(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        edge = random.randint(0, 3)
        if edge == 0:
            pos = QPointF(random.uniform(0, self.width()), 0)
            velocity = QPointF(random.uniform(-1, 1), random.uniform(1, 3))
        elif edge == 1:
            pos = QPointF(self.width(), random.uniform(0, self.height()))
            velocity = QPointF(random.uniform(-3, -1), random.uniform(-1, 1))
        elif edge == 2:
            pos = QPointF(random.uniform(0, self.width()), self.height())
            velocity = QPointF(random.uniform(-1, 1), random.uniform(-3, -1))
        else:
            pos = QPointF(0, random.uniform(0, self.height()))
            velocity = QPointF(random.uniform(1, 3), random.uniform(-1, 1))

        self._particles.append(
            Particle(
                pos=pos,
                velocity=velocity,
                life=random.randint(20, 35),
                max_life=35,
                size=random.uniform(2, 4),
                color=QColor(255, random.randint(150, 220), random.randint(100, 150)),
                particle_type="trail",
            )
        )

    def _move_to_top_right(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        geom = screen.availableGeometry()
        x = geom.right() - self.width() - 30
        y = geom.top() + 40
        self.move(max(0, x), max(0, y))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.isVisible():
            glow_alpha = int(60 + 30 * math.sin(self._glow_phase * 0.5))
            gradient = QRadialGradient(self.width() / 2, self.height() / 2, max(self.width(), self.height()) / 2)
            gradient.setColorAt(0, QColor(255, 80, 180, glow_alpha))
            gradient.setColorAt(0.5, QColor(220, 100, 200, glow_alpha // 2))
            gradient.setColorAt(1, QColor(180, 120, 255, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 22, 22)

        for particle in self._particles:
            alpha = int(255 * (particle.life / max(1, particle.max_life)))
            color = QColor(particle.color)
            color.setAlpha(max(0, min(alpha, 255)))

            if particle.particle_type == "glow":
                glow_gradient = QRadialGradient(particle.pos, particle.size * 3)
                glow_gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), alpha))
                glow_gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
                painter.setPen(Qt.NoPen)
                painter.setBrush(glow_gradient)
                painter.drawEllipse(particle.pos, particle.size * 3, particle.size * 3)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(particle.pos, particle.size, particle.size)

                if particle.particle_type == "spark" and particle.life > particle.max_life * 0.5:
                    tail_len = min(particle.velocity.x() ** 2 + particle.velocity.y() ** 2, 16) ** 0.5 * 2
                    if tail_len > 1:
                        tail_color = QColor(color)
                        tail_color.setAlpha(alpha // 3)
                        painter.setPen(QPen(tail_color, particle.size * 0.6))
                        tail_end = QPointF(
                            particle.pos.x() - particle.velocity.x() * tail_len / 3,
                            particle.pos.y() - particle.velocity.y() * tail_len / 3
                        )
                        painter.drawLine(particle.pos, tail_end)

        if self._burst_ticks > 0:
            pulse_alpha = 150 + int(80 * math.sin(self._glow_phase * 2))
            painter.setPen(QPen(QColor(255, 120, 200, min(255, pulse_alpha)), 3.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 20, 20)

        super().paintEvent(event)
