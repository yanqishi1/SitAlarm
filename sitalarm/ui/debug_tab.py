from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DebugTab(QWidget):
    debug_capture_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("PageScrollArea")
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("PageContent")
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 16)

        intro = QLabel("调试页支持实时画面与检测叠加，可直接观察头占比阈值是否合理。")
        intro.setWordWrap(True)
        root.addWidget(intro)

        button_row = QHBoxLayout()
        self.debug_capture_btn = QPushButton("抓拍调试（保存图片）")
        self.debug_capture_btn.clicked.connect(self.debug_capture_requested.emit)
        button_row.addWidget(self.debug_capture_btn)
        button_row.addStretch()
        root.addLayout(button_row)

        preview_group = QGroupBox("实时调试画面")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("等待实时画面...")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(560, 320)
        self.preview_label.setStyleSheet("border: 1px solid rgba(148, 163, 184, 80); background: rgba(15, 23, 42, 200); color: #94a3b8; border-radius: 8px;")
        preview_layout.addWidget(self.preview_label)
        root.addWidget(preview_group)

        self.summary_label = QLabel("等待调试数据...")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setPlaceholderText("指标详情会显示在这里")
        self.detail_box.setMinimumHeight(140)
        root.addWidget(self.detail_box)
        root.addStretch(1)

    def update_debug_info(self, payload: dict[str, object]) -> None:
        debug_info = payload.get("debug_info", {})
        if not isinstance(debug_info, dict):
            debug_info = {}

        status = str(payload.get("status", "unknown"))
        face_box = debug_info.get("face_box")

        frame = payload.get("frame")
        if frame is not None:
            self._set_preview_from_frame(frame, face_box, status)
        else:
            self._set_preview_from_path(str(payload.get("image_path", "")))

        reasons = payload.get("reasons", [])
        reason_text = ", ".join(reasons) if isinstance(reasons, list) and reasons else "无"
        source = str(payload.get("source", "unknown"))
        brightness = payload.get("brightness", "-")
        ratio = debug_info.get("head_ratio")
        ratio_text = f"{ratio:.4f}" if isinstance(ratio, (int, float)) else "-"

        self.summary_label.setText(
            f"时间：{payload.get('time', '-')}, 来源：{source}, 判定：{status}, "
            f"头占比：{ratio_text}, 原因：{reason_text}, 亮度：{brightness}"
        )

        lines: list[str] = []
        self._append_metric(
            lines,
            "头占比指标",
            debug_info.get("head_ratio"),
            debug_info.get("threshold_head_ratio"),
        )

        if face_box is not None:
            lines.append(f"头部框: {face_box}")

        self._append_metric(
            lines,
            "上半身可见度",
            debug_info.get("upper_visibility"),
            debug_info.get("threshold_visibility"),
        )
        self._append_metric(
            lines,
            "头前倾指标",
            debug_info.get("head_forward_ratio"),
            debug_info.get("threshold_head_forward"),
        )
        self._append_metric(
            lines,
            "耸肩指标",
            debug_info.get("shoulder_raise_ratio"),
            debug_info.get("threshold_shrugging"),
        )
        self._append_metric(
            lines,
            "躯干前倾角",
            debug_info.get("trunk_lean_degrees"),
            debug_info.get("threshold_hunchback"),
        )

        hip_visibility = debug_info.get("hip_visibility")
        if hip_visibility is not None:
            lines.append(f"髋部可见度: {hip_visibility}")

        trunk_available = debug_info.get("trunk_available")
        if trunk_available is not None:
            lines.append(f"躯干指标是否可用: {trunk_available}")

        calibrated = debug_info.get("calibrated")
        if calibrated is not None:
            lines.append(f"是否已校准: {calibrated}")

        if not lines:
            lines.append("暂无可用调试指标")

        self.detail_box.setPlainText("\n".join(lines))

    def _set_preview_from_path(self, image_path: str) -> None:
        if image_path and Path(image_path).exists():
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)
                return

        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("暂无调试画面")

    def _set_preview_from_frame(self, frame: Any, face_box: object, status: str) -> None:
        shape = getattr(frame, "shape", None)
        if not isinstance(shape, tuple) or len(shape) < 2:
            return

        frame_height, frame_width = shape[0], shape[1]
        if frame_height <= 0 or frame_width <= 0:
            return

        if len(shape) >= 3 and shape[2] >= 3:
            rgb = frame[:, :, :3][:, :, ::-1].copy()
            image = QImage(rgb.data, frame_width, frame_height, 3 * frame_width, QImage.Format_RGB888).copy()
        else:
            gray = frame.copy()
            image = QImage(gray.data, frame_width, frame_height, frame_width, QImage.Format_Grayscale8).copy()

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return

        if isinstance(face_box, tuple) and len(face_box) == 4:
            color = self._status_color(status)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(color, 3))
            x, y, w, h = [int(value) for value in face_box]
            painter.drawRect(x, y, w, h)
            painter.end()

        self._set_scaled_pixmap(pixmap)

    def _set_scaled_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    @staticmethod
    def _status_color(status: str) -> QColor:
        if status == "incorrect":
            return QColor("#ff5252")
        if status == "correct":
            return QColor("#00c853")
        return QColor("#9e9e9e")

    @staticmethod
    def _append_metric(lines: list[str], name: str, value: object, threshold: object) -> None:
        if not isinstance(value, (int, float)) or not isinstance(threshold, (int, float)):
            return

        hit = value >= threshold
        flag = "触发" if hit else "正常"
        lines.append(f"{name}: {value:.4f} >= {threshold:.4f} -> {flag}")
