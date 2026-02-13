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
    QVBoxLayout,
    QWidget,
)


class DebugTab(QWidget):
    debug_capture_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._last_pixmap: QPixmap | None = None
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
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("调试")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        intro_card = QFrame()
        intro_card.setObjectName("UiCard")
        intro_layout = QHBoxLayout(intro_card)
        intro_layout.setContentsMargins(18, 14, 18, 14)
        intro_layout.setSpacing(10)
        info_icon = QLabel("i")
        info_icon.setObjectName("InfoDot")
        intro_layout.addWidget(info_icon, 0, Qt.AlignTop)
        intro = QLabel("调试页支持实时画面与检测阈值，可直接观察头点比阈值是否合理。")
        intro.setObjectName("SectionHint")
        intro.setWordWrap(True)
        intro_layout.addWidget(intro, 1)
        root.addWidget(intro_card)

        self.debug_capture_btn = QPushButton("抓拍调试（保存图片）")
        self.debug_capture_btn.setObjectName("ActionButton")
        self.debug_capture_btn.clicked.connect(self.debug_capture_requested.emit)
        root.addWidget(self.debug_capture_btn, alignment=Qt.AlignLeft)

        preview_group = QGroupBox("实时测试画面")
        preview_group.setObjectName("UiCard")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(12)

        self.preview_label = QLabel("等待实时画面...")
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        # 固定尺寸避免布局计算过程中的动态缩放
        self.preview_label.setFixedSize(640, 480)
        preview_layout.addWidget(self.preview_label, alignment=Qt.AlignCenter)
        root.addWidget(preview_group)

        info_group = QGroupBox("调试信息")
        info_group.setObjectName("UiCard")
        info_layout = QHBoxLayout(info_group)
        info_layout.setContentsMargins(24, 20, 24, 22)
        info_layout.setSpacing(34)

        self.left_info = QLabel("时间: -\n来源: -\n判定: -\n头点比: -\n原因: -")
        self.right_info = QLabel("亮度: -\n头点比较准比: -\n状态: -\n实际比: -")
        self.left_info.setObjectName("DebugInfoBlock")
        self.right_info.setObjectName("DebugInfoBlock")
        info_layout.addWidget(self.left_info, 1)
        info_layout.addWidget(self.right_info, 1)
        root.addWidget(info_group)

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

        source = str(payload.get("source", "unknown"))
        brightness = payload.get("brightness", "-")
        ratio = debug_info.get("head_ratio")
        ratio_text = f"{ratio:.4f}" if isinstance(ratio, (int, float)) else "-"

        threshold = debug_info.get("threshold_head_ratio")
        threshold_text = f"{threshold:.4f}" if isinstance(threshold, (int, float)) else "-"

        reason_text = self._reason_text(payload.get("reasons"))
        compare_text = f"{ratio_text} {'>=' if self._is_hit(ratio, threshold) else '<'} {threshold_text}"

        status_text = "正常"
        if status == "incorrect":
            status_text = "错误"
        elif status == "unknown":
            status_text = "未检测到用户"

        face_text = str(face_box) if isinstance(face_box, tuple) else "-"

        self.left_info.setText(
            f"时间: {payload.get('time', '-')}\n"
            f"来源: {source}\n"
            f"判定: {status}\n"
            f"头点比: {ratio_text}\n"
            f"原因: {reason_text}"
        )

        self.right_info.setText(
            f"亮度: {brightness}\n"
            f"头点比较准比: {compare_text}\n"
            f"状态: {status_text}\n"
            f"实际比: {face_text}"
        )

    @staticmethod
    def _reason_text(reasons: object) -> str:
        if isinstance(reasons, list) and reasons:
            return ", ".join(str(item) for item in reasons)
        if isinstance(reasons, str) and reasons:
            return reasons
        return "无"

    @staticmethod
    def _is_hit(value: object, threshold: object) -> bool:
        if not isinstance(value, (int, float)) or not isinstance(threshold, (int, float)):
            return False
        return float(value) >= float(threshold)

    def _set_preview_from_path(self, image_path: str) -> None:
        if image_path and Path(image_path).exists():
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)
                return

        self._last_pixmap = None
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
        self._last_pixmap = pixmap
        # 使用固定尺寸缩放，避免布局变化导致的动态缩放
        if self._last_pixmap is not None and not self._last_pixmap.isNull():
            scaled = self._last_pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,  # 使用快速变换减少闪烁
            )
            self.preview_label.setPixmap(scaled)

    def _refresh_preview(self) -> None:
        """刷新预览画面（保持固定尺寸避免动态缩放）"""
        if self._last_pixmap is None or self._last_pixmap.isNull():
            return
        scaled = self._last_pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,  # 使用快速变换减少闪烁
        )
        self.preview_label.setPixmap(scaled)

    @staticmethod
    def _status_color(status: str) -> QColor:
        if status == "incorrect":
            return QColor("#ff3d3d")
        if status == "correct":
            return QColor("#ff8a00")
        return QColor("#9ca3af")
