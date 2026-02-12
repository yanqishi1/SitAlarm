from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol


FaceBox = tuple[int, int, int, int]
PoseLandmarkPoint = tuple[int, int, float]
PoseConnection = tuple[int, int]

DEFAULT_HEAD_RATIO_THRESHOLD = 0.15
CALIBRATION_SAFETY_MARGIN = 0.15
DEFAULT_POSE_VISIBILITY_THRESHOLD = 0.35
DEFAULT_HIP_VISIBILITY_THRESHOLD = 0.25
DEFAULT_HEAD_FORWARD_THRESHOLD = 0.24
DEFAULT_HUNCHBACK_THRESHOLD_DEGREES = 14.0
DEFAULT_EAR_SPAN_TOO_CLOSE_THRESHOLD = 0.19


@dataclass(frozen=True)
class HeadRatioResult:
    status: str
    reasons: tuple[str, ...]
    head_ratio: float | None
    face_box: FaceBox | None
    threshold: float
    pose_status: str
    distance_status: str
    pose_landmarks: tuple[PoseLandmarkPoint, ...]
    pose_connections: tuple[PoseConnection, ...]
    pose_debug: dict[str, object]


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
            self._detector = None
            return

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
        pose_visibility_threshold: float = DEFAULT_POSE_VISIBILITY_THRESHOLD,
        hip_visibility_threshold: float = DEFAULT_HIP_VISIBILITY_THRESHOLD,
        head_forward_threshold: float = DEFAULT_HEAD_FORWARD_THRESHOLD,
        hunchback_threshold_degrees: float = DEFAULT_HUNCHBACK_THRESHOLD_DEGREES,
        ear_span_too_close_threshold: float = DEFAULT_EAR_SPAN_TOO_CLOSE_THRESHOLD,
    ) -> None:
        self.face_detector = face_detector or BlazeFaceFaceDetector()
        self.ratio_threshold = ratio_threshold
        self.pose_visibility_threshold = pose_visibility_threshold
        self.hip_visibility_threshold = hip_visibility_threshold
        self.head_forward_threshold = head_forward_threshold
        self.hunchback_threshold_degrees = hunchback_threshold_degrees
        self.ear_span_too_close_threshold = ear_span_too_close_threshold

        self._pose = None
        self._cv2 = None
        self._pose_landmark_ids: dict[str, int] = {}
        self._pose_connections: tuple[PoseConnection, ...] = ()
        self._smoothed_head_forward: float | None = None
        self._smoothed_trunk_angle: float | None = None

        self._init_pose_detector()

    def evaluate_frame(self, frame: Any) -> HeadRatioResult:
        faces = self.face_detector.detect(frame)
        face_box = max(faces, key=self._face_area) if faces else None
        head_ratio = self.calculate_head_ratio(face_box, frame.shape) if face_box else None

        distance_status = "unknown"
        too_close = False
        if head_ratio is not None:
            too_close = head_ratio >= self.ratio_threshold
            distance_status = "too_close" if too_close else "normal"

        pose_status, pose_reasons, landmarks, pose_debug = self._evaluate_pose(frame)

        # Fallback for near-camera scenes when face box detection fails.
        if head_ratio is None and bool(pose_debug.get("head_too_close_proxy", False)):
            too_close = True
            distance_status = "too_close_proxy"

        reasons: list[str] = []
        reasons.extend(pose_reasons)
        if too_close:
            reasons.append("head_too_close")

        if reasons:
            status = "incorrect"
        elif pose_status == "correct" or distance_status == "normal":
            # Avoid frequent unknown state when only lower body landmarks are missing.
            status = "correct"
        else:
            status = "unknown"

        return HeadRatioResult(
            status=status,
            reasons=tuple(reasons),
            head_ratio=head_ratio,
            face_box=face_box,
            threshold=self.ratio_threshold,
            pose_status=pose_status,
            distance_status=distance_status,
            pose_landmarks=landmarks,
            pose_connections=self._pose_connections,
            pose_debug=pose_debug,
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

    def _init_pose_detector(self) -> None:
        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
        except ImportError:
            return

        self._cv2 = cv2
        try:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception:
            self._pose = None
            return

        landmark_enum = mp.solutions.pose.PoseLandmark
        self._pose_landmark_ids = {
            "nose": int(landmark_enum.NOSE),
            "left_ear": int(landmark_enum.LEFT_EAR),
            "right_ear": int(landmark_enum.RIGHT_EAR),
            "left_shoulder": int(landmark_enum.LEFT_SHOULDER),
            "right_shoulder": int(landmark_enum.RIGHT_SHOULDER),
            "left_hip": int(landmark_enum.LEFT_HIP),
            "right_hip": int(landmark_enum.RIGHT_HIP),
        }
        self._pose_connections = tuple((int(a), int(b)) for a, b in mp.solutions.pose.POSE_CONNECTIONS)

    def _evaluate_pose(
        self,
        frame: Any,
    ) -> tuple[str, tuple[str, ...], tuple[PoseLandmarkPoint, ...], dict[str, object]]:
        if self._pose is None or self._cv2 is None:
            return "unknown", (), (), {"pose_available": False}

        frame_height, frame_width = frame.shape[:2]
        rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return "unknown", (), (), {"pose_available": True, "pose_detected": False}

        image_landmarks = result.pose_landmarks.landmark
        world_landmarks = result.pose_world_landmarks.landmark if result.pose_world_landmarks else None
        points = self._pack_landmarks(image_landmarks, frame_width, frame_height)

        id_map = self._pose_landmark_ids
        left_shoulder = image_landmarks[id_map["left_shoulder"]]
        right_shoulder = image_landmarks[id_map["right_shoulder"]]
        left_hip = image_landmarks[id_map["left_hip"]]
        right_hip = image_landmarks[id_map["right_hip"]]

        shoulder_visibility = (left_shoulder.visibility + right_shoulder.visibility) / 2.0
        hip_visibility = (left_hip.visibility + right_hip.visibility) / 2.0
        ear_span_ratio = self._ear_span_ratio(image_landmarks)

        debug: dict[str, object] = {
            "pose_available": True,
            "pose_detected": True,
            "shoulder_visibility": round(shoulder_visibility, 4),
            "hip_visibility": round(hip_visibility, 4),
            "ear_span_ratio": round(ear_span_ratio, 4) if ear_span_ratio is not None else None,
            "head_too_close_proxy": bool(
                ear_span_ratio is not None and ear_span_ratio >= self.ear_span_too_close_threshold
            ),
            "threshold_ear_span_too_close": round(self.ear_span_too_close_threshold, 4),
        }

        # Shoulder points are minimum requirement for posture analysis.
        if shoulder_visibility < self.pose_visibility_threshold:
            debug["pose_visibility_ok"] = False
            return "unknown", (), points, debug

        head_forward_ratio = self._head_forward_ratio(image_landmarks, world_landmarks)
        if head_forward_ratio is None:
            debug["pose_visibility_ok"] = False
            return "unknown", (), points, debug

        head_forward_ratio = self._ema(self._smoothed_head_forward, head_forward_ratio)
        self._smoothed_head_forward = head_forward_ratio

        trunk_angle: float | None = None
        if hip_visibility >= self.hip_visibility_threshold:
            shoulder_center = (
                (left_shoulder.x + right_shoulder.x) / 2.0,
                (left_shoulder.y + right_shoulder.y) / 2.0,
            )
            hip_center = (
                (left_hip.x + right_hip.x) / 2.0,
                (left_hip.y + right_hip.y) / 2.0,
            )
            trunk_angle_raw = self._trunk_angle_degrees(shoulder_center, hip_center)
            if trunk_angle_raw is not None:
                trunk_angle = self._ema(self._smoothed_trunk_angle, trunk_angle_raw)
                self._smoothed_trunk_angle = trunk_angle

        reasons: list[str] = []
        if head_forward_ratio >= self.head_forward_threshold:
            reasons.append("head_forward")
        if trunk_angle is not None and trunk_angle >= self.hunchback_threshold_degrees:
            reasons.append("hunchback")

        debug.update(
            {
                "pose_visibility_ok": True,
                "head_forward_ratio": round(head_forward_ratio, 4),
                "trunk_angle_degrees": round(trunk_angle, 4) if trunk_angle is not None else None,
                "threshold_head_forward": round(self.head_forward_threshold, 4),
                "threshold_hunchback": round(self.hunchback_threshold_degrees, 4),
            }
        )

        status = "incorrect" if reasons else "correct"
        return status, tuple(reasons), points, debug

    def _head_forward_ratio(self, image_landmarks: Any, world_landmarks: Any) -> float | None:
        ids = self._pose_landmark_ids
        left_shoulder = image_landmarks[ids["left_shoulder"]]
        right_shoulder = image_landmarks[ids["right_shoulder"]]

        if world_landmarks is not None:
            left_shoulder_w = world_landmarks[ids["left_shoulder"]]
            right_shoulder_w = world_landmarks[ids["right_shoulder"]]
            shoulder_width_world = self._dist3(
                left_shoulder_w.x,
                left_shoulder_w.y,
                left_shoulder_w.z,
                right_shoulder_w.x,
                right_shoulder_w.y,
                right_shoulder_w.z,
            )
            if shoulder_width_world > 1e-6:
                head_z_values: list[float] = []
                for name in ("nose", "left_ear", "right_ear"):
                    idx = ids[name]
                    if image_landmarks[idx].visibility >= 0.35:
                        head_z_values.append(float(world_landmarks[idx].z))
                if head_z_values:
                    shoulder_z = (float(left_shoulder_w.z) + float(right_shoulder_w.z)) / 2.0
                    head_z = sum(head_z_values) / len(head_z_values)
                    return (shoulder_z - head_z) / shoulder_width_world

        visible_x: list[float] = []
        for name in ("nose", "left_ear", "right_ear"):
            idx = ids[name]
            if image_landmarks[idx].visibility >= 0.35:
                visible_x.append(float(image_landmarks[idx].x))

        shoulder_width_2d = abs(float(left_shoulder.x) - float(right_shoulder.x))
        if shoulder_width_2d <= 1e-6 or not visible_x:
            return None

        head_x = sum(visible_x) / len(visible_x)
        shoulder_center_x = (float(left_shoulder.x) + float(right_shoulder.x)) / 2.0
        return abs(head_x - shoulder_center_x) / shoulder_width_2d

    def _ear_span_ratio(self, image_landmarks: Any) -> float | None:
        ids = self._pose_landmark_ids
        left_ear = image_landmarks[ids["left_ear"]]
        right_ear = image_landmarks[ids["right_ear"]]
        if left_ear.visibility < 0.35 or right_ear.visibility < 0.35:
            return None
        return abs(float(left_ear.x) - float(right_ear.x))

    @staticmethod
    def _trunk_angle_degrees(
        shoulder_center: tuple[float, float],
        hip_center: tuple[float, float],
    ) -> float | None:
        dx = shoulder_center[0] - hip_center[0]
        dy = shoulder_center[1] - hip_center[1]
        norm = math.hypot(dx, dy)
        if norm <= 1e-6:
            return None

        cos_theta = max(-1.0, min(1.0, (-dy) / norm))
        return math.degrees(math.acos(cos_theta))

    @staticmethod
    def _pack_landmarks(landmarks: Any, frame_width: int, frame_height: int) -> tuple[PoseLandmarkPoint, ...]:
        points: list[PoseLandmarkPoint] = []
        for lm in landmarks:
            x = int(max(0.0, min(1.0, float(lm.x))) * frame_width)
            y = int(max(0.0, min(1.0, float(lm.y))) * frame_height)
            points.append((x, y, float(lm.visibility)))
        return tuple(points)

    @staticmethod
    def _ema(previous: float | None, current: float, alpha: float = 0.35) -> float:
        if previous is None:
            return current
        return alpha * current + (1.0 - alpha) * previous

    @staticmethod
    def _dist3(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
