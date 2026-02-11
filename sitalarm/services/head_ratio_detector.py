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


class HaarCascadeFaceDetector:
    def __init__(
        self,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: tuple[int, int] = (40, 40),
        cascade_path: str | None = None,
    ) -> None:
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

        try:
            import cv2  # type: ignore
        except ImportError:
            self._cv2 = None
            self._detector = None
            return

        self._cv2 = cv2
        path = cascade_path or (cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        detector = cv2.CascadeClassifier(path)
        self._detector = detector if not detector.empty() else None

    def detect(self, frame: Any) -> list[FaceBox]:
        if self._cv2 is None or self._detector is None:
            return []

        gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        faces = self._detector.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )
        return [tuple(int(value) for value in face) for face in faces]


class HeadRatioPostureDetector:
    def __init__(
        self,
        face_detector: FaceDetector | None = None,
        ratio_threshold: float = DEFAULT_HEAD_RATIO_THRESHOLD,
    ) -> None:
        self.face_detector = face_detector or HaarCascadeFaceDetector()
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
