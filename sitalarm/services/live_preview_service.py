from __future__ import annotations

from typing import Any

from sitalarm.services.capture_service import CaptureError


class LivePreviewService:
    def __init__(self, camera_index: int = 0, camera_backend: Any | None = None) -> None:
        self.camera_index = camera_index
        self._camera_backend = camera_backend
        self._camera: Any | None = None

    @property
    def started(self) -> bool:
        return self._camera is not None

    def start(self) -> None:
        if self._camera is not None:
            return

        backend = self._resolve_camera_backend()
        camera = backend.VideoCapture(self.camera_index)
        if not camera.isOpened():
            camera.release()
            raise CaptureError("无法打开摄像头，请检查权限或占用情况。")

        self._camera = camera

    def read_frame(self) -> Any:
        if self._camera is None:
            raise CaptureError("实时预览未启动，请先启动后再读取画面。")

        ok, frame = self._camera.read()
        if not ok or frame is None:
            raise CaptureError("实时预览读取失败，请检查摄像头状态。")
        return frame

    def stop(self) -> None:
        if self._camera is None:
            return

        self._camera.release()
        self._camera = None

    def _resolve_camera_backend(self) -> Any:
        if self._camera_backend is not None:
            return self._camera_backend

        try:
            import cv2  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise CaptureError("OpenCV 未安装，无法访问摄像头。") from exc

        self._camera_backend = cv2
        return self._camera_backend
