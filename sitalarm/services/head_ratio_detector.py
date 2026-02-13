from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, Tuple

from sitalarm.services.compute_device_service import effective_compute_device
from sitalarm.services.mediapipe_model_service import (
    ensure_face_detector_model,
    ensure_pose_landmarker_model,
)

FaceBox = Tuple[int, int, int, int]
PoseLandmarkPoint = Tuple[int, int, float]
PoseConnection = Tuple[int, int]

DEFAULT_HEAD_RATIO_THRESHOLD = 0.15
CALIBRATION_SAFETY_MARGIN = 0.30
DEFAULT_POSE_VISIBILITY_THRESHOLD = 0.35
DEFAULT_HIP_VISIBILITY_THRESHOLD = 0.25
DEFAULT_HEAD_FORWARD_THRESHOLD = 0.28
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
    """Face detector powered by MediaPipe.

    Behavior:
    - compute_device=cpu: use MediaPipe Solutions (no extra model downloads)
    - compute_device=gpu: try MediaPipe Tasks + GPU delegate; fall back to Solutions on failure
    """

    def __init__(
        self,
        model_selection: int = 1,
        min_detection_confidence: float = 0.5,
        compute_device: str = "cpu",
    ) -> None:
        self._compute_device = effective_compute_device(compute_device)
        self._mp = None
        self._tasks_detector = None
        self._solutions_detector = None
        self._backend = "unavailable"
        self._gpu_init_error: str | None = None

        try:
            import mediapipe as mp  # type: ignore

            self._mp = mp
        except ImportError:
            return

        if self._compute_device == "gpu":
            try:
                from mediapipe.tasks.python import BaseOptions  # type: ignore
                from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions  # type: ignore

                model_path = ensure_face_detector_model()
                options = FaceDetectorOptions(
                    base_options=BaseOptions(
                        model_asset_path=str(model_path),
                        delegate=BaseOptions.Delegate.GPU,
                    )
                )
                self._tasks_detector = FaceDetector.create_from_options(options)
                self._backend = "tasks:gpu"
                return
            except Exception as exc:
                self._gpu_init_error = str(exc)

        try:
            self._solutions_detector = self._mp.solutions.face_detection.FaceDetection(
                model_selection=model_selection,
                min_detection_confidence=min_detection_confidence,
            )
            self._backend = "solutions:cpu"
        except Exception:
            self._solutions_detector = None

    def backend_name(self) -> str:
        return self._backend

    def backend_details(self) -> dict[str, object]:
        return {
            "backend": self._backend,
            "compute_device": self._compute_device,
            "gpu_init_error": self._gpu_init_error,
        }

    def __del__(self):
        """Release MediaPipe resources when this instance is garbage-collected."""
        try:
            if hasattr(self, '_solutions_detector') and self._solutions_detector is not None:
                self._solutions_detector.close()
            if hasattr(self, '_tasks_detector') and self._tasks_detector is not None:
                self._tasks_detector.close()
        except Exception:
            pass
        finally:
            if hasattr(self, '_solutions_detector'):
                self._solutions_detector = None
            if hasattr(self, '_tasks_detector'):
                self._tasks_detector = None
            if hasattr(self, '_mp'):
                self._mp = None

    def detect(self, frame: Any) -> list[FaceBox]:
        if self._mp is None:
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
            if self._compute_device == "gpu" and hasattr(cv2, "ocl") and cv2.ocl.haveOpenCL():
                infer_frame = cv2.resize(cv2.UMat(frame), (infer_width, infer_height)).get()
            else:
                infer_frame = cv2.resize(frame, (infer_width, infer_height))
            scale_x = frame_width / infer_width
            scale_y = frame_height / infer_height

        if self._compute_device == "gpu" and hasattr(cv2, "ocl") and cv2.ocl.haveOpenCL():
            rgb = cv2.cvtColor(cv2.UMat(infer_frame), cv2.COLOR_BGR2RGB).get()
        else:
            rgb = cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB)

        # Tasks (GPU)
        if self._tasks_detector is not None:
            try:
                mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                result = self._tasks_detector.detect(mp_image)
                detections = getattr(result, "detections", None) or []
            except Exception:
                detections = []

            boxes: list[FaceBox] = []
            for detection in detections:
                bbox = getattr(detection, "bounding_box", None)
                if bbox is None:
                    continue
                x = int(getattr(bbox, "origin_x", 0))
                y = int(getattr(bbox, "origin_y", 0))
                w = int(getattr(bbox, "width", 0))
                h = int(getattr(bbox, "height", 0))

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

        # Solutions (CPU)
        if self._solutions_detector is None:
            return []

        result = self._solutions_detector.process(rgb)
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
        compute_device: str = "cpu",
        pose_model_complexity: int = 1,
        camera_angle_mode: str = "upper_body",
        ema_alpha: float = 0.25,
    ) -> None:
        self.compute_device = effective_compute_device(compute_device)
        self.face_detector = face_detector or BlazeFaceFaceDetector(compute_device=self.compute_device)
        self.ratio_threshold = ratio_threshold
        self.pose_visibility_threshold = pose_visibility_threshold
        self.hip_visibility_threshold = hip_visibility_threshold
        self.head_forward_threshold = head_forward_threshold
        self.hunchback_threshold_degrees = hunchback_threshold_degrees
        self.ear_span_too_close_threshold = ear_span_too_close_threshold
        self.pose_model_complexity = max(0, min(2, pose_model_complexity))
        self.camera_angle_mode = camera_angle_mode
        self.ema_alpha = ema_alpha

        self._pose = None
        self._pose_tasks = None
        self._pose_backend = "unavailable"
        self._pose_gpu_init_error: str | None = None
        self._mp = None
        self._cv2 = None
        self._pose_landmark_ids: dict[str, int] = {}
        self._pose_connections: tuple[PoseConnection, ...] = ()
        self._smoothed_head_forward: float | None = None
        self._smoothed_trunk_angle: float | None = None

        self._init_pose_detector()

    def backend_details(self) -> dict[str, object]:
        face_backend = getattr(self.face_detector, "backend_name", lambda: "unknown")()
        face_detail_getter = getattr(self.face_detector, "backend_details", None)
        face_details = face_detail_getter() if callable(face_detail_getter) else {"backend": face_backend}
        return {
            "pose_backend": self._pose_backend,
            "pose_gpu_init_error": self._pose_gpu_init_error,
            "face_backend": face_backend,
            "face_details": face_details,
            "compute_device": self.compute_device,
        }


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
        pose_debug.setdefault("face_backend", getattr(self.face_detector, "backend_name", lambda: "unknown")())
        pose_debug.setdefault("backend_details", self.backend_details())

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

        import math as _math

        margin = max(0.0, safety_margin)
        max_ratio = max(correct_ratios)
        mean_ratio = sum(correct_ratios) / len(correct_ratios)
        # Use whichever is larger: max-based or (mean + 1 stddev)-based.
        if len(correct_ratios) >= 3:
            variance = sum((r - mean_ratio) ** 2 for r in correct_ratios) / len(correct_ratios)
            stddev = _math.sqrt(variance)
            base = max(max_ratio, mean_ratio + stddev)
        else:
            base = max_ratio
        return min(1.0, base * (1.0 + margin))

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
        # Reset before init.
        self._pose = None
        self._pose_tasks = None
        self._pose_backend = "unavailable"
        self._pose_gpu_init_error = None

        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
        except ImportError:
            return

        self._cv2 = cv2
        self._mp = mp

        # Landmark indices are stable across Solutions/Tasks.
        self._pose_landmark_ids = {
            "nose": 0,
            "left_ear": 7,
            "right_ear": 8,
            "left_shoulder": 11,
            "right_shoulder": 12,
            "left_hip": 23,
            "right_hip": 24,
        }
        try:
            self._pose_connections = tuple((int(a), int(b)) for a, b in mp.solutions.pose.POSE_CONNECTIONS)
        except Exception:
            self._pose_connections = ()

        # GPU: load MediaPipe Tasks landmarker (GPU delegate) and return.
        if self.compute_device == "gpu":
            try:
                from mediapipe.tasks.python import BaseOptions  # type: ignore
                from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions  # type: ignore
                from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode  # type: ignore

                model_path = ensure_pose_landmarker_model()
                options = PoseLandmarkerOptions(
                    base_options=BaseOptions(
                        model_asset_path=str(model_path),
                        delegate=BaseOptions.Delegate.GPU,
                    ),
                    running_mode=VisionTaskRunningMode.IMAGE,
                    num_poses=1,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._pose_tasks = PoseLandmarker.create_from_options(options)
                self._pose_backend = "tasks:gpu"
                return
            except Exception as exc:
                self._pose_tasks = None
                self._pose_gpu_init_error = str(exc)

        # CPU fallback: MediaPipe Solutions.
        try:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=self.pose_model_complexity,
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._pose_backend = "solutions:cpu"
        except Exception:
            self._pose = None
            self._pose_backend = "unavailable"


    def _evaluate_pose(
        self,
        frame: Any,
    ) -> tuple[str, tuple[str, ...], tuple[PoseLandmarkPoint, ...], dict[str, object]]:
        if self._cv2 is None:
            return "unknown", (), (), {"pose_available": False}

        frame_height, frame_width = frame.shape[:2]

        if self.compute_device == "gpu" and hasattr(self._cv2, "ocl") and self._cv2.ocl.haveOpenCL():
            rgb = self._cv2.cvtColor(self._cv2.UMat(frame), self._cv2.COLOR_BGR2RGB).get()
        else:
            rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

        image_landmarks = None
        world_landmarks = None

        if self._pose_tasks is not None and self._mp is not None:
            try:
                mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                result = self._pose_tasks.detect(mp_image)
                if not getattr(result, "pose_landmarks", None):
                    return "unknown", (), (), {
                        "pose_available": True,
                        "pose_detected": False,
                        "pose_backend": self._pose_backend,
                        "compute_device": self.compute_device,
            "pose_gpu_init_error": self._pose_gpu_init_error,
                    }

                image_landmarks = result.pose_landmarks[0]
                if getattr(result, "pose_world_landmarks", None):
                    world_landmarks = result.pose_world_landmarks[0]
            except Exception:
                image_landmarks = None

        if image_landmarks is None:
            if self._pose is None:
                return "unknown", (), (), {"pose_available": False}

            result = self._pose.process(rgb)
            if not result.pose_landmarks:
                return "unknown", (), (), {
                    "pose_available": True,
                    "pose_detected": False,
                    "pose_backend": self._pose_backend,
                    "compute_device": self.compute_device,
            "pose_gpu_init_error": self._pose_gpu_init_error,
                }

            image_landmarks = result.pose_landmarks.landmark
            world_landmarks = result.pose_world_landmarks.landmark if result.pose_world_landmarks else None

        points = self._pack_landmarks(image_landmarks, frame_width, frame_height)

        id_map = self._pose_landmark_ids
        left_shoulder = image_landmarks[id_map["left_shoulder"]]
        right_shoulder = image_landmarks[id_map["right_shoulder"]]
        left_hip = image_landmarks[id_map["left_hip"]]
        right_hip = image_landmarks[id_map["right_hip"]]

        shoulder_visibility = (self._vis(left_shoulder) + self._vis(right_shoulder)) / 2.0
        hip_visibility = (self._vis(left_hip) + self._vis(right_hip)) / 2.0
        ear_span_ratio = self._ear_span_ratio(image_landmarks)

        debug: dict[str, object] = {
            "pose_available": True,
            "pose_detected": True,
            "pose_backend": self._pose_backend,
            "compute_device": self.compute_device,
            "pose_gpu_init_error": self._pose_gpu_init_error,
            "model_complexity": self.pose_model_complexity,
            "camera_angle_mode": self.camera_angle_mode,
            "shoulder_visibility": round(shoulder_visibility, 4),
            "hip_visibility": round(hip_visibility, 4),
            "ear_span_ratio": round(ear_span_ratio, 4) if ear_span_ratio is not None else None,
            "head_too_close_proxy": bool(
                ear_span_ratio is not None and ear_span_ratio >= self.ear_span_too_close_threshold
            ),
            "threshold_ear_span_too_close": round(self.ear_span_too_close_threshold, 4),
        }

        if shoulder_visibility < self.pose_visibility_threshold:
            debug["pose_visibility_ok"] = False
            return "unknown", (), points, debug

        head_forward_ratio = self._head_forward_ratio(image_landmarks, world_landmarks)
        if head_forward_ratio is None:
            debug["pose_visibility_ok"] = False
            return "unknown", (), points, debug

        head_forward_ratio = self._ema(self._smoothed_head_forward, head_forward_ratio, self.ema_alpha)
        self._smoothed_head_forward = head_forward_ratio

        # Determine if we're in upper body mode (hips not visible or user configured)
        upper_body_mode = (
            self.camera_angle_mode == "upper_body"
            or hip_visibility < self.hip_visibility_threshold
        )
        debug["upper_body_mode"] = upper_body_mode

        trunk_angle: float | None = None
        if not upper_body_mode and hip_visibility >= self.hip_visibility_threshold:
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
                trunk_angle = self._ema(self._smoothed_trunk_angle, trunk_angle_raw, self.ema_alpha)
                self._smoothed_trunk_angle = trunk_angle

        # Adjust head forward threshold for upper body / laptop webcam mode.
        # Low-angle cameras exaggerate the perceived head-forward offset due to
        # perspective distortion, so we RELAX the threshold to compensate.
        effective_head_forward_threshold = self.head_forward_threshold
        if upper_body_mode:
            effective_head_forward_threshold = self.head_forward_threshold * 1.15

        reasons: list[str] = []
        if head_forward_ratio >= effective_head_forward_threshold:
            reasons.append("head_forward")
        if trunk_angle is not None and trunk_angle >= self.hunchback_threshold_degrees:
            reasons.append("hunchback")

        debug.update(
            {
                "pose_visibility_ok": True,
                "head_forward_ratio": round(head_forward_ratio, 4),
                "trunk_angle_degrees": round(trunk_angle, 4) if trunk_angle is not None else None,
                "threshold_head_forward": round(effective_head_forward_threshold, 4),
                "threshold_head_forward_base": round(self.head_forward_threshold, 4),
                "threshold_hunchback": round(self.hunchback_threshold_degrees, 4),
                "ema_alpha": self.ema_alpha,
            }
        )

        status = "incorrect" if reasons else "correct"
        return status, tuple(reasons), points, debug
    @staticmethod
    def _vis(lm: Any) -> float:
        value = getattr(lm, "visibility", 0.0)
        return float(value) if isinstance(value, (int, float)) else 0.0


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
                    if self._vis(image_landmarks[idx]) >= 0.35:
                        head_z_values.append(float(world_landmarks[idx].z))
                if head_z_values:
                    shoulder_z = (float(left_shoulder_w.z) + float(right_shoulder_w.z)) / 2.0
                    head_z = sum(head_z_values) / len(head_z_values)
                    return (shoulder_z - head_z) / shoulder_width_world

        visible_x: list[float] = []
        for name in ("nose", "left_ear", "right_ear"):
            idx = ids[name]
            if self._vis(image_landmarks[idx]) >= 0.35:
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
        if self._vis(left_ear) < 0.35 or self._vis(right_ear) < 0.35:
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
            vis = getattr(lm, "visibility", 0.0)
            vis_f = float(vis) if isinstance(vis, (int, float)) else 0.0
            points.append((x, y, vis_f))
        return tuple(points)

    @staticmethod
    def _ema(previous: float | None, current: float, alpha: float = 0.35) -> float:
        if previous is None:
            return current
        return alpha * current + (1.0 - alpha) * previous

    @staticmethod
    def _dist3(ax: float, ay: float, az: float, bx: float, by: float, bz: float) -> float:
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)


    def __del__(self):
        """Release MediaPipe resources when this instance is garbage-collected."""
        try:
            if hasattr(self, '_pose') and self._pose is not None:
                self._pose.close()
            if hasattr(self, '_pose_tasks') and self._pose_tasks is not None:
                self._pose_tasks.close()
        except Exception:
            pass
        finally:
            if hasattr(self, '_pose'):
                self._pose = None
            if hasattr(self, '_pose_tasks'):
                self._pose_tasks = None
            if hasattr(self, '_mp'):
                self._mp = None
            if hasattr(self, '_cv2'):
                self._cv2 = None
