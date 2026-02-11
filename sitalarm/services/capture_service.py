from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterable


class CaptureError(RuntimeError):
    pass


class CameraCaptureService:
    def __init__(
        self,
        camera_index: int = 0,
        camera_backend: Any | None = None,
        warmup_frames: int = 5,
        max_retries: int = 2,
        min_brightness: float = 18.0,
        retry_sleep_seconds: float = 0.2,
    ) -> None:
        self.camera_index = camera_index
        self.warmup_frames = max(1, warmup_frames)
        self.max_retries = max(1, max_retries)
        self.min_brightness = min_brightness
        self.retry_sleep_seconds = max(0.0, retry_sleep_seconds)
        self._camera_backend = camera_backend

    def capture_frame(self) -> Any:
        backend = self._resolve_camera_backend()
        last_error: str | None = None

        for attempt in range(self.max_retries):
            camera = backend.VideoCapture(self.camera_index)
            if not camera.isOpened():
                camera.release()
                last_error = "无法打开摄像头，请检查权限或占用情况。"
                continue

            frame = self._read_warmed_frame(camera)
            camera.release()

            if frame is None:
                last_error = "摄像头抓拍失败，请重试。"
                continue

            if self._is_dark_frame(frame):
                last_error = "摄像头画面过暗或黑屏，请调整光线后重试。"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_sleep_seconds)
                continue

            return frame

        raise CaptureError(last_error or "摄像头抓拍失败，请重试。")

    def save_frame(self, frame: Any, output_path: Path) -> None:
        backend = self._resolve_camera_backend()
        if not hasattr(backend, "imwrite"):
            raise CaptureError("OpenCV 未安装，无法保存图片。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved = backend.imwrite(str(output_path), frame)
        if not saved:
            raise CaptureError("图片保存失败，请检查磁盘空间。")

    def _resolve_camera_backend(self) -> Any:
        if self._camera_backend is not None:
            return self._camera_backend
        try:
            import cv2  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on runtime env
            raise CaptureError("OpenCV 未安装，无法访问摄像头。") from exc
        self._camera_backend = cv2
        return self._camera_backend

    def _read_warmed_frame(self, camera: Any) -> Any | None:
        frame: Any | None = None
        for _ in range(self.warmup_frames):
            ok, candidate = camera.read()
            if ok and candidate is not None:
                frame = candidate
            time.sleep(0.03)
        return frame

    def _is_dark_frame(self, frame: Any) -> bool:
        return self.frame_brightness(frame) < self.min_brightness

    def frame_brightness(self, frame: Any) -> float:
        mean_fn = getattr(frame, "mean", None)
        if callable(mean_fn):
            value = float(mean_fn())
            if value >= 0:
                return value

        values = list(self._iter_numeric(frame))
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _iter_numeric(self, obj: Any) -> Iterable[float]:
        if isinstance(obj, (int, float)):
            yield float(obj)
            return

        if isinstance(obj, (list, tuple)):
            for item in obj:
                yield from self._iter_numeric(item)
