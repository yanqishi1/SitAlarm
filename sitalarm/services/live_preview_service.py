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

    def draw_pose_overlay(
        self,
        frame: Any,
        landmarks: object,
        connections: object,
        *,
        status: str,
    ) -> Any:
        backend = self._resolve_camera_backend()
        if not hasattr(frame, "copy"):
            return frame

        points = self._normalize_landmarks(landmarks)
        if not points:
            return frame

        skeleton = self._normalize_connections(connections)
        annotated = frame.copy()
        line_color = self._status_color(status)

        for start_idx, end_idx in skeleton:
            if start_idx >= len(points) or end_idx >= len(points):
                continue
            start = points[start_idx]
            end = points[end_idx]
            if start[2] < 0.35 or end[2] < 0.35:
                continue
            backend.line(
                annotated,
                (start[0], start[1]),
                (end[0], end[1]),
                line_color,
                2,
                backend.LINE_AA,
            )

        for idx, (x, y, visibility) in enumerate(points):
            if visibility < 0.35:
                continue
            radius = 4 if idx in {0, 7, 8, 11, 12, 23, 24} else 2
            backend.circle(annotated, (x, y), radius, (255, 255, 255), -1, backend.LINE_AA)
            backend.circle(annotated, (x, y), radius + 1, line_color, 1, backend.LINE_AA)

        return annotated

    def stop(self) -> None:
        if self._camera is None:
            return

        try:
            self._camera.release()
        except Exception:
            pass
        finally:
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

    @staticmethod
    def _normalize_landmarks(landmarks: object) -> list[tuple[int, int, float]]:
        if not isinstance(landmarks, (list, tuple)):
            return []

        points: list[tuple[int, int, float]] = []
        for item in landmarks:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                return []
            x_raw, y_raw, vis_raw = item[0], item[1], item[2]
            if not isinstance(x_raw, (int, float)) or not isinstance(y_raw, (int, float)):
                return []
            visibility = float(vis_raw) if isinstance(vis_raw, (int, float)) else 0.0
            points.append((int(x_raw), int(y_raw), visibility))
        return points

    @staticmethod
    def _normalize_connections(connections: object) -> list[tuple[int, int]]:
        if not isinstance(connections, (list, tuple)):
            return []

        pairs: list[tuple[int, int]] = []
        for item in connections:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            a_raw, b_raw = item[0], item[1]
            if not isinstance(a_raw, int) or not isinstance(b_raw, int):
                continue
            if a_raw < 0 or b_raw < 0:
                continue
            pairs.append((a_raw, b_raw))
        return pairs

    @staticmethod
    def _status_color(status: str) -> tuple[int, int, int]:
        if status == "incorrect":
            return (61, 61, 255)
        if status == "correct":
            return (0, 138, 255)
        return (156, 163, 175)

    def __del__(self):
        """析构函数，确保摄像头资源被释放"""
        try:
            if self._camera is not None:
                self._camera.release()
        except Exception:
            pass
        finally:
            self._camera = None
