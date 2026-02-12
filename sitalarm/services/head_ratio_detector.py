from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


FaceBox = tuple[int, int, int, int]
DEFAULT_HEAD_RATIO_THRESHOLD = 0.15
CALIBRATION_SAFETY_MARGIN = 0.15


@dataclass(frozen=True)
class HeadRatioResult:
    status: str
    head_ratio: float | None
    face_box: FaceBox | None
    threshold: float


class FaceDetector(Protocol):
    def detect(self, frame: Any) -> list[FaceBox]:
        ...


class BlazeFaceFaceDetector:
    """Face detector powered by MediaPipe's BlazeFace model."""

    def __init__(
        self,
        model_selection: int = 0,
        min_detection_confidence: float = 0.5,
    ) -> None:
        try:
            import mediapipe as mp  # type: ignore
        except ImportError:
            self._mp = None
            self._detector = None
            return

        self._mp = mp
        try:
            self._detector = mp.solutions.face_detection.FaceDetection(
                model_selection=model_selection,
                min_detection_confidence=min_detection_confidence,
            )
        except Exception:
            self._detector = None

    def detect(self, frame: Any) -> list[FaceBox]:
        if self._detector is None:
            return []

        frame_height, frame_width = frame.shape[:2]
        if frame_width <= 0 or frame_height <= 0:
            return []

        try:
            import cv2  # type: ignore
        except ImportError:
            return []

        infer_frame = frame
        infer_width = frame_width
        infer_height = frame_height
        scale_x = 1.0
        scale_y = 1.0

        # Limit detector input size to reduce CPU usage on hi-res cameras.
        max_infer_width = 640
        if frame_width > max_infer_width:
            infer_width = max_infer_width
            infer_height = max(1, int(frame_height * (infer_width / frame_width)))
            infer_frame = cv2.resize(frame, (infer_width, infer_height))
            scale_x = frame_width / infer_width
            scale_y = frame_height / infer_height

        rgb = cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.detections:
            return []

        boxes: list[FaceBox] = []
        for detection in result.detections:
            relative_box = detection.location_data.relative_bounding_box
            x = int(relative_box.xmin * infer_width)
            y = int(relative_box.ymin * infer_height)
            w = int(relative_box.width * infer_width)
            h = int(relative_box.height * infer_height)

            x = int(x * scale_x)
            y = int(y * scale_y)
            w = int(w * scale_x)
            h = int(h * scale_y)

            x = max(0, min(x, frame_width - 1))
            y = max(0, min(y, frame_height - 1))
            w = max(0, min(w, frame_width - x))
            h = max(0, min(h, frame_height - y))
            if w > 0 and h > 0:
                boxes.append((x, y, w, h))

        return boxes


class HeadRatioPostureDetector:
    def __init__(
        self,
        face_detector: FaceDetector | None = None,
        ratio_threshold: float = DEFAULT_HEAD_RATIO_THRESHOLD,
    ) -> None:
        self.face_detector = face_detector or BlazeFaceFaceDetector()
        self.ratio_threshold = ratio_threshold

    def evaluate_frame(self, frame: Any) -> HeadRatioResult:
        faces = self.face_detector.detect(frame)
        if not faces:
            return HeadRatioResult(
                status="unknown",
                head_ratio=None,
                face_box=None,
                threshold=self.ratio_threshold,
            )

        face_box = max(faces, key=self._face_area)
        head_ratio = self.calculate_head_ratio(face_box, frame.shape)
        status = "incorrect" if head_ratio >= self.ratio_threshold else "correct"
        return HeadRatioResult(
            status=status,
            head_ratio=head_ratio,
            face_box=face_box,
            threshold=self.ratio_threshold,
        )

    @staticmethod
    def recommend_threshold(
        correct_ratios: list[float] | tuple[float, ...],
        safety_margin: float = CALIBRATION_SAFETY_MARGIN,
    ) -> float:
        if len(correct_ratios) < 2:
            raise ValueError("At least two correct-posture samples are required for calibration.")

        max_ratio = max(correct_ratios)
        margin = max(0.0, safety_margin)
        return min(1.0, max_ratio * (1.0 + margin))

    @staticmethod
    def calculate_head_ratio(face_box: FaceBox, frame_shape: tuple[int, ...]) -> float:
        frame_height, frame_width = frame_shape[:2]
        if frame_width <= 0 or frame_height <= 0:
            return 0.0

        _, _, width, height = face_box
        face_area = max(0, width) * max(0, height)
        frame_area = frame_width * frame_height
        return face_area / frame_area

    @staticmethod
    def _face_area(face_box: FaceBox) -> int:
        return max(0, face_box[2]) * max(0, face_box[3])
