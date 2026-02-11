from __future__ import annotations

import contextlib
import os
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

    def normalize_frame_brightness(
        self,
        frame: Any,
        *,
        low: float = 55.0,
        high: float = 195.0,
        target: float = 120.0,
        min_alpha: float = 0.65,
        max_alpha: float = 4.0,
        min_gamma: float = 0.45,
        max_gamma: float = 2.2,
    ) -> tuple[Any, dict[str, object]]:
        """
        Best-effort brightness normalization before head/pose detection.

        - If image is too dark, increase luminance.
        - If image is too bright, decrease luminance.

        Returns (possibly adjusted frame, info dict).
        """
        info: dict[str, object] = {
            "brightness_before": None,
            "brightness_after": None,
            "brightness_alpha": 1.0,
            "brightness_gamma": 1.0,
            "brightness_adjusted": False,
        }

        backend = None
        try:
            backend = self._resolve_camera_backend()
        except Exception:
            backend = None

        # Use Y channel if possible for better luminance estimate.
        try:
            if backend is not None and hasattr(backend, "cvtColor"):
                ycrcb = backend.cvtColor(frame, backend.COLOR_BGR2YCrCb)
                y = ycrcb[:, :, 0]
                mean = float(y.mean())
            else:
                mean = float(getattr(frame, "mean")())
        except Exception:
            mean = self.frame_brightness(frame)

        info["brightness_before"] = round(mean, 2)

        if mean <= 1.0:
            return frame, info
        if low <= mean <= high:
            info["brightness_after"] = info["brightness_before"]
            return frame, info

        # Choose gamma + alpha for more natural brightening/dimming.
        if mean < low:
            gamma = max(min_gamma, min(0.95, mean / max(1.0, low)))
        else:
            gamma = min(max_gamma, max(1.05, mean / max(1.0, high)))
        info["brightness_gamma"] = round(float(gamma), 4)

        alpha = float(target / mean)
        alpha = max(min_alpha, min(max_alpha, alpha))
        info["brightness_alpha"] = round(float(alpha), 4)
        info["brightness_adjusted"] = True

        # Apply on luminance channel if OpenCV is available.
        try:
            if backend is not None and hasattr(backend, "cvtColor"):
                ycrcb = backend.cvtColor(frame, backend.COLOR_BGR2YCrCb)
                y = ycrcb[:, :, 0]
                try:
                    import numpy as np  # type: ignore
                except Exception:
                    np = None  # type: ignore

                if np is not None:
                    # Gamma correction via LUT.
                    x = np.arange(256, dtype=np.float32) / 255.0
                    lut = np.clip((x ** float(gamma)) * 255.0, 0, 255).astype(np.uint8)
                    y_gamma = backend.LUT(y, lut)
                    y2 = (y_gamma.astype("float32") * float(alpha)).clip(0, 255).astype("uint8")
                else:
                    y2 = (y.astype("float32") * float(alpha)).clip(0, 255).astype("uint8")

                ycrcb[:, :, 0] = y2
                out = backend.cvtColor(ycrcb, backend.COLOR_YCrCb2BGR)
                info["brightness_after"] = round(float(y2.mean()), 2)
                return out, info
        except Exception:
            pass

        # Fallback: scale the whole frame.
        try:
            out = (frame.astype("float32") * float(alpha)).clip(0, 255).astype("uint8")
            info["brightness_after"] = round(self.frame_brightness(out), 2)
            return out, info
        except Exception:
            # Give up; return original.
            info["brightness_adjusted"] = False
            info["brightness_alpha"] = 1.0
            info["brightness_gamma"] = 1.0
            info["brightness_after"] = info["brightness_before"]
            return frame, info

    @staticmethod
    def list_available_camera_indices(max_index: int = 8) -> list[int]:
        """Best-effort probe for available cameras (OpenCV indices)."""
        try:
            import cv2  # type: ignore
        except Exception:
            return []

        @contextlib.contextmanager
        def _silence_native_output():
            """Best-effort suppress C-level stdout/stderr noise during probing."""
            devnull = None
            old_out = None
            old_err = None
            try:
                devnull = os.open(os.devnull, os.O_WRONLY)
                old_out = os.dup(1)
                old_err = os.dup(2)
                os.dup2(devnull, 1)
                os.dup2(devnull, 2)
                yield
            finally:
                try:
                    if old_out is not None:
                        os.dup2(old_out, 1)
                    if old_err is not None:
                        os.dup2(old_err, 2)
                finally:
                    for fd in (devnull, old_out, old_err):
                        try:
                            if fd is not None:
                                os.close(fd)
                        except Exception:
                            pass

        # Suppress noisy OpenCV stderr/log output during probing on macOS.
        old_level = None
        try:
            logging = getattr(getattr(cv2, "utils", None), "logging", None)
            if logging is not None and hasattr(logging, "getLogLevel") and hasattr(logging, "setLogLevel"):
                old_level = logging.getLogLevel()
                silent = getattr(logging, "LOG_LEVEL_SILENT", None)
                if silent is not None:
                    logging.setLogLevel(silent)
        except Exception:
            old_level = None

        available: list[int] = []
        try:
            with _silence_native_output():
                for idx in range(max(0, int(max_index)) + 1):
                    cap = cv2.VideoCapture(idx)
                    try:
                        if cap is not None and cap.isOpened():
                            available.append(idx)
                    finally:
                        try:
                            cap.release()
                        except Exception:
                            pass
        finally:
            try:
                logging = getattr(getattr(cv2, "utils", None), "logging", None)
                if old_level is not None and logging is not None and hasattr(logging, "setLogLevel"):
                    logging.setLogLevel(old_level)
            except Exception:
                pass
        return available

    def _iter_numeric(self, obj: Any) -> Iterable[float]:
        if isinstance(obj, (int, float)):
            yield float(obj)
            return

        if isinstance(obj, (list, tuple)):
            for item in obj:
                yield from self._iter_numeric(item)
