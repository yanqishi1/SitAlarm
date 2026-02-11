from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PoseMetrics:
    visibility: float
    head_forward_ratio: float
    shoulder_raise_ratio: float
    trunk_lean_degrees: float
    trunk_available: bool = True


@dataclass(frozen=True)
class PostureResult:
    status: str
    reasons: tuple[str, ...]
    confidence: float | None
    debug_info: dict[str, object] | None = None


class RuleBasedPostureClassifier:
    def __init__(
        self,
        min_visibility: float = 0.5,
        head_forward_threshold: float = 0.18,
        shoulder_raise_threshold: float = 0.12,
        trunk_lean_threshold: float = 14.0,
    ) -> None:
        self.min_visibility = min_visibility
        self.head_forward_threshold = head_forward_threshold
        self.shoulder_raise_threshold = shoulder_raise_threshold
        self.trunk_lean_threshold = trunk_lean_threshold

    def classify(self, metrics: PoseMetrics) -> PostureResult:
        if metrics.visibility < self.min_visibility:
            return PostureResult(status="unknown", reasons=(), confidence=metrics.visibility)

        reasons: list[str] = []
        if metrics.head_forward_ratio >= self.head_forward_threshold:
            reasons.append("head_forward")
        if metrics.shoulder_raise_ratio >= self.shoulder_raise_threshold:
            reasons.append("shrugging")
        if metrics.trunk_available and metrics.trunk_lean_degrees >= self.trunk_lean_threshold:
            reasons.append("hunchback")

        status = "incorrect" if reasons else "correct"
        confidence = min(1.0, max(0.0, metrics.visibility))
        return PostureResult(status=status, reasons=tuple(reasons), confidence=confidence)


class MediaPipePostureDetector:
    """Pose detection wrapper. Falls back to unknown if mediapipe is missing."""

    def __init__(self, classifier: RuleBasedPostureClassifier | None = None) -> None:
        self.classifier = classifier or RuleBasedPostureClassifier()
        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
        except ImportError:
            self._cv2 = None
            self._mp = None
            self._pose = None
            return

        self._cv2 = cv2
        self._mp = mp
        try:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception:
            # Some environments cannot initialize MediaPipe GPU/GL context.
            self._pose = None

    def detect(self, frame: Any) -> PostureResult:
        if self._pose is None or self._cv2 is None or self._mp is None:
            return PostureResult(status="unknown", reasons=(), confidence=None)

        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return PostureResult(status="unknown", reasons=(), confidence=0.0)

        lm = result.pose_landmarks.landmark
        mp_pose = self._mp.solutions.pose.PoseLandmark

        def mean_visibility(*indices: int) -> float:
            values = [lm[index].visibility for index in indices]
            return sum(values) / len(values)

        left_shoulder = lm[mp_pose.LEFT_SHOULDER]
        right_shoulder = lm[mp_pose.RIGHT_SHOULDER]
        left_ear = lm[mp_pose.LEFT_EAR]
        right_ear = lm[mp_pose.RIGHT_EAR]
        left_hip = lm[mp_pose.LEFT_HIP]
        right_hip = lm[mp_pose.RIGHT_HIP]

        shoulder_width = abs(left_shoulder.x - right_shoulder.x) + 1e-6
        ear_to_shoulder = (
            abs(left_ear.x - left_shoulder.x) + abs(right_ear.x - right_shoulder.x)
        ) / 2.0
        head_forward_ratio = ear_to_shoulder / shoulder_width

        shoulder_raise_ratio = (
            abs(left_shoulder.y - left_ear.y) + abs(right_shoulder.y - right_ear.y)
        ) / 2.0

        upper_visibility = mean_visibility(
            mp_pose.LEFT_SHOULDER,
            mp_pose.RIGHT_SHOULDER,
            mp_pose.LEFT_EAR,
            mp_pose.RIGHT_EAR,
        )
        hip_visibility = mean_visibility(mp_pose.LEFT_HIP, mp_pose.RIGHT_HIP)
        trunk_available = hip_visibility >= 0.2

        trunk_lean_degrees = 0.0
        if trunk_available:
            shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0
            hip_mid_y = (left_hip.y + right_hip.y) / 2.0
            trunk_lean_degrees = max(0.0, (0.35 - (hip_mid_y - shoulder_mid_y)) * 100.0)

        metrics = PoseMetrics(
            visibility=upper_visibility,
            head_forward_ratio=head_forward_ratio,
            shoulder_raise_ratio=shoulder_raise_ratio,
            trunk_lean_degrees=trunk_lean_degrees,
            trunk_available=trunk_available,
        )
        result = self.classifier.classify(metrics)
        debug_info = {
            "upper_visibility": round(upper_visibility, 4),
            "hip_visibility": round(hip_visibility, 4),
            "head_forward_ratio": round(head_forward_ratio, 4),
            "shoulder_raise_ratio": round(shoulder_raise_ratio, 4),
            "trunk_lean_degrees": round(trunk_lean_degrees, 4),
            "trunk_available": trunk_available,
            "threshold_visibility": self.classifier.min_visibility,
            "threshold_head_forward": self.classifier.head_forward_threshold,
            "threshold_shrugging": self.classifier.shoulder_raise_threshold,
            "threshold_hunchback": self.classifier.trunk_lean_threshold,
        }
        return PostureResult(
            status=result.status,
            reasons=result.reasons,
            confidence=result.confidence,
            debug_info=debug_info,
        )
