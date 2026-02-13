from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sitalarm.config import AppSettings, get_capture_base_dir
from sitalarm.services.capture_service import CameraCaptureService, CaptureError
from sitalarm.services.compute_device_service import effective_compute_device, gpu_available
from sitalarm.services.file_service import cleanup_old_capture_dirs, ensure_day_capture_dir
from sitalarm.services.head_ratio_detector import (
    CALIBRATION_SAFETY_MARGIN,
    DEFAULT_HEAD_FORWARD_THRESHOLD,
    DEFAULT_HEAD_RATIO_THRESHOLD,
    DEFAULT_HUNCHBACK_THRESHOLD_DEGREES,
    HeadRatioPostureDetector,
)
from sitalarm.services.live_preview_service import LivePreviewService
from sitalarm.services.posture_detector import PostureResult
from sitalarm.services.reminder_service import ReminderPolicy
from sitalarm.services.settings_service import SettingsService
from sitalarm.services.stats_service import DaySummary, PostureRecord, StatsService
from sitalarm.services.storage import Storage
from sitalarm.services.system_usage_service import SystemUsageService


class SitAlarmController(QObject):
    state_changed = pyqtSignal(str)
    summary_updated = pyqtSignal(object)
    history_updated = pyqtSignal(object)

    posture_records_updated = pyqtSignal(object)
    event_logged = pyqtSignal(object)
    reminder_triggered = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    debug_info_updated = pyqtSignal(object)
    live_debug_frame_updated = pyqtSignal(object)
    calibration_required = pyqtSignal(str)
    calibration_status_updated = pyqtSignal(object)

    def __init__(self, storage: Storage, settings_service: SettingsService, stats_service: StatsService) -> None:
        super().__init__()
        self._log = logging.getLogger(__name__)
        self.storage = storage
        self.settings_service = settings_service
        self.stats_service = stats_service

        self.settings = self.settings_service.load()
        self._gpu_available = gpu_available()
        self._gpu_delegate_warned = False
        self.capture_service = CameraCaptureService(camera_index=self.settings.camera_index)
        self._compute_device = effective_compute_device(getattr(self.settings, "compute_device", "cpu"))
        try:
            import cv2  # type: ignore

            if hasattr(cv2, "ocl") and cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(self._compute_device == "gpu")
        except Exception:
            pass
        self.detector = HeadRatioPostureDetector(
            ratio_threshold=self._effective_head_ratio_threshold(self.settings.head_ratio_threshold),
            compute_device=self._compute_device,
            pose_model_complexity=getattr(self.settings, "pose_model_complexity", 1),
            camera_angle_mode=getattr(self.settings, "camera_angle_mode", "upper_body"),
        )
        self.reminder_policy = ReminderPolicy(self.settings.reminder_cooldown_minutes)

        self.capture_base_dir = get_capture_base_dir()
        self.capture_base_dir.mkdir(parents=True, exist_ok=True)

        self._paused = False
        self._screen_start = datetime.now()
        self._last_posture_status: str | None = None
        # Consecutive incorrect detections counter – requires N consecutive
        # "incorrect" results before a reminder is triggered to avoid false alarms.
        self._consecutive_incorrect: int = 0
        self._consecutive_incorrect_threshold: int = 1  # need 1 consecutive incorrect (immediate reminder)
        self._required_calibration_samples = 3
        self._calibration_ratios: list[float] = []
        self._calibration_head_forward_ratios: list[float] = []
        self._calibration_image_paths: list[str] = []
        # Incorrect-posture calibration (phase 2)
        self._required_incorrect_samples = 2
        self._calibration_incorrect_ratios: list[float] = []
        self._calibration_incorrect_head_forward_ratios: list[float] = []
        self._calibration_incorrect_image_paths: list[str] = []
        self._system_usage = SystemUsageService()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.run_detection_now)

        self._live_preview_service = LivePreviewService(camera_index=self.capture_service.camera_index)
        self._live_preview_timer = QTimer(self)
        self._live_preview_timer.setInterval(150)
        self._live_preview_timer.timeout.connect(self._push_live_debug_frame)
        
        # 缓存实时预览的最后一帧，用于确保实时检测和立即检测结果一致
        self._last_live_frame: Any | None = None
        self._last_live_frame_lock = False

    def start(self) -> None:
        self._log.info("Controller start. settings=%s", self.settings)
        self._system_usage.tick()
        self.apply_settings(self.settings)
        self._publish_stats()
        if self._is_calibrated():
            self.state_changed.emit("检测中")
        else:
            self.state_changed.emit("待校准")
            self._emit_calibration_required()

    def stop(self) -> None:
        self._log.info("Controller stop.")
        self._timer.stop()
        self.stop_live_debug()
        self.state_changed.emit("已停止")
        # 触发垃圾回收，释放 numpy 数组内存
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    def pause_detection(self) -> None:
        self._log.info("Pause detection.")
        self._paused = True
        self._timer.stop()
        self.state_changed.emit("已暂停")

    def resume_detection(self) -> None:
        if not self._ensure_calibrated_for_detection():
            return

        self._log.info("Resume detection. interval_seconds=%s", self.settings.capture_interval_seconds)
        self._paused = False
        now = datetime.now()
        self.stats_service.record_detection_start_if_missing(now.date(), now)
        self._timer.start(self.settings.capture_interval_seconds * 1000)
        self.state_changed.emit("检测中")

    def start_live_debug(self) -> None:
        if self._live_preview_service.started:
            return

        try:
            self._log.info("Start live preview. camera_index=%s", self._live_preview_service.camera_index)
            self._live_preview_service.start()
        except CaptureError as exc:
            self._log.exception("Start live preview failed: %s", exc)
            self.error_occurred.emit(str(exc))
            return

        self._live_preview_timer.start()

    def stop_live_debug(self) -> None:
        if self._live_preview_service.started:
            self._log.info("Stop live preview.")
        self._live_preview_timer.stop()
        try:
            self._live_preview_service.stop()
        except Exception:
            pass
        # 清理缓存的帧
        self._last_live_frame = None
        # 触发垃圾回收，释放 numpy 数组内存
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    def update_settings(self, **changes: object) -> AppSettings:
        self._log.info("Update settings: %s", changes)
        self.settings = self.settings_service.update(**changes)
        self.apply_settings(self.settings)
        return self.settings

    def apply_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        self.reminder_policy = ReminderPolicy(settings.reminder_cooldown_minutes)

        previous_compute_device = getattr(self, "_compute_device", "cpu")
        requested_compute_device = getattr(settings, "compute_device", "cpu")
        self._compute_device = effective_compute_device(requested_compute_device)
        # Enable/disable OpenCV OpenCL. This makes the UMat path actually use GPU when available.
        try:
            import cv2  # type: ignore

            if hasattr(cv2, "ocl") and cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(self._compute_device == "gpu")
        except Exception:
            pass

        self.detector = HeadRatioPostureDetector(
            ratio_threshold=self.detector.ratio_threshold,
            pose_visibility_threshold=self.detector.pose_visibility_threshold,
            hip_visibility_threshold=self.detector.hip_visibility_threshold,
            head_forward_threshold=self.detector.head_forward_threshold,
            hunchback_threshold_degrees=self.detector.hunchback_threshold_degrees,
            ear_span_too_close_threshold=self.detector.ear_span_too_close_threshold,
            compute_device=self._compute_device,
            pose_model_complexity=getattr(settings, "pose_model_complexity", 1),
            camera_angle_mode=getattr(settings, "camera_angle_mode", "upper_body"),
        )

        base = self._effective_head_ratio_threshold(settings.head_ratio_threshold)
        multiplier = self._threshold_multiplier(settings.detection_mode)
        self.detector.ratio_threshold = min(1.0, base * multiplier)

        # Use calibrated head forward threshold if available, otherwise use default
        calibrated_head_forward = getattr(settings, "head_forward_threshold_calibrated", 0.0)
        if calibrated_head_forward > 0:
            # Use calibrated threshold with detection mode multiplier
            self.detector.head_forward_threshold = min(1.0, calibrated_head_forward * multiplier)
        else:
            # Use default threshold with detection mode multiplier
            self.detector.head_forward_threshold = min(1.0, DEFAULT_HEAD_FORWARD_THRESHOLD * multiplier)

        self.detector.hunchback_threshold_degrees = min(45.0, DEFAULT_HUNCHBACK_THRESHOLD_DEGREES * multiplier)
        backend_details = self.detector.backend_details()
        if str(requested_compute_device).lower() == "gpu":
            pose_backend = str(backend_details.get("pose_backend") or "")
            face_backend = str(backend_details.get("face_backend") or "")
            if pose_backend == "tasks:gpu" and face_backend == "tasks:gpu":
                self._gpu_delegate_warned = False
            elif not self._gpu_delegate_warned:
                self._gpu_delegate_warned = True
                pose_err = backend_details.get("pose_gpu_init_error")
                face_err = None
                face_details = backend_details.get("face_details")
                if isinstance(face_details, dict):
                    face_err = face_details.get("gpu_init_error")
                message = "已尝试启用 GPU 加速，但 MediaPipe GPU Delegate 初始化失败/不支持，已自动回退到 CPU。"
                if pose_err or face_err:
                    message += f"\nPose: {pose_err}\nFace: {face_err}"
                self._log.warning(message)
                self.error_occurred.emit(message)
        else:
            self._gpu_delegate_warned = False
        self._log.info(
            "Applied detection threshold. base=%.4f mode=%s multiplier=%.2f effective=%.4f head_forward=%.4f (calibrated=%.4f) hunchback=%.2f compute=%s requested_compute=%s gpu_available=%s pose_backend=%s face_backend=%s",
            base,
            settings.detection_mode,
            multiplier,
            self.detector.ratio_threshold,
            self.detector.head_forward_threshold,
            calibrated_head_forward,
            self.detector.hunchback_threshold_degrees,
            self._compute_device,
            requested_compute_device,
            self._gpu_available,
            backend_details.get("pose_backend"),
            backend_details.get("face_backend"),
        )
        self._apply_camera_index(settings.camera_index)
        cleanup_old_capture_dirs(self.capture_base_dir, settings.retention_days, datetime.now().date())

        self._timer.stop()
        if self._paused:
            self._emit_calibration_status(phase="paused", message="检测已暂停。")
            return

        if not self._is_calibrated():
            self.state_changed.emit("待校准")
            self._emit_calibration_status(
                phase="required",
                message="请先在设置页拍摄 3 张正确坐姿照片完成校准。",
            )
            return

        now = datetime.now()
        self.stats_service.record_detection_start_if_missing(now.date(), now)
        self._timer.start(settings.capture_interval_seconds * 1000)
        self._emit_calibration_status(phase="ready", message="头占比阈值已完成校准。")

    def _apply_camera_index(self, camera_index: int) -> None:
        camera_index = int(camera_index)
        if camera_index == self.capture_service.camera_index and camera_index == self._live_preview_service.camera_index:
            return

        # If live preview is running, restart to apply new camera.
        was_live = self._live_preview_service.started
        if was_live:
            self.stop_live_debug()

        self.capture_service.camera_index = camera_index
        self._live_preview_service.camera_index = camera_index

        if was_live:
            self.start_live_debug()

    def run_detection_now(self) -> None:
        if self._paused:
            return
        if not self._ensure_calibrated_for_detection():
            return

        now = datetime.now()
        usage_day, usage_delta = self._system_usage.tick()
        if usage_delta > 0:
            self.stats_service.record_screen_usage(usage_day, usage_delta)
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"{now.strftime('%H%M%S')}.jpg"

        try:
            self._log.info("Detection start. image_path=%s camera_index=%s", image_path, self.capture_service.camera_index)
            raw_frame = self._capture_frame_for_detection()
            frame, brightness_info = self._prepare_frame_for_detection(raw_frame)
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self._log.exception("Detection capture/save failed: %s", exc)
            self.error_occurred.emit(str(exc))
            return

        result = self._detect_posture(frame, brightness_info=brightness_info)
        self._log.info("Detection result. status=%s reasons=%s confidence=%s", result.status, list(result.reasons), result.confidence)
        self._emit_debug_info(now=now, image_path=image_path, frame=frame, result=result, source="scheduled")
        self._record_event(now, image_path, result)
        self._publish_stats()
        self._trigger_reminders(now, result)

    def run_debug_capture(self) -> None:
        now = datetime.now()
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"debug_{now.strftime('%H%M%S')}.jpg"

        try:
            raw_frame = self._capture_frame_for_detection()
            frame, brightness_info = self._prepare_frame_for_detection(raw_frame)
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            return

        result = self._detect_posture(frame, brightness_info=brightness_info)
        self._emit_debug_info(now=now, image_path=image_path, frame=frame, result=result, source="manual")

    def capture_head_ratio_calibration_sample(self) -> None:
        now = datetime.now()
        sample_index = len(self._calibration_ratios) + 1
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"calib_correct_{sample_index}_{now.strftime('%H%M%S')}.jpg"

        try:
            raw_frame = self._capture_frame_for_detection()
            frame, _ = self._prepare_frame_for_detection(raw_frame)
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            self._emit_calibration_status(phase="error", message=str(exc))
            return

        ratio_result = self.detector.evaluate_frame(frame)
        if ratio_result.head_ratio is None:
            self.error_occurred.emit("未识别到头部，请调整光线或角度后重试。")
            self._emit_calibration_status(
                phase="error",
                message=f"第 {sample_index}/{self._required_calibration_samples} 张未识别到头部，请保持正对摄像头并重拍。",
            )
            return

        # Collect data
        self._calibration_ratios.append(ratio_result.head_ratio)
        self._calibration_image_paths.append(str(image_path))

        head_forward_ratio = ratio_result.pose_debug.get("head_forward_ratio")
        if head_forward_ratio is not None and isinstance(head_forward_ratio, (int, float)):
            self._calibration_head_forward_ratios.append(float(head_forward_ratio))
            self._log.info(
                "Calibration sample %d: head_ratio=%.4f, head_forward_ratio=%.4f",
                sample_index, ratio_result.head_ratio, head_forward_ratio,
            )
        else:
            # Pad with 0.0 to keep indices aligned with _calibration_ratios
            self._calibration_head_forward_ratios.append(0.0)
            self._log.info(
                "Calibration sample %d: head_ratio=%.4f, head_forward_ratio=None",
                sample_index, ratio_result.head_ratio,
            )

        captured_count = len(self._calibration_ratios)
        if captured_count < self._required_calibration_samples:
            self._emit_calibration_status(
                phase="partial",
                message=f"正确坐姿：已完成第 {captured_count}/{self._required_calibration_samples} 张，请保持正确坐姿继续拍下一张。",
            )
            return

        # Phase 1 done – correct posture samples collected.
        # Transition to phase 2: collect incorrect posture samples.
        self._log.info(
            "Correct posture calibration done. ratios=%s head_forward=%s",
            [round(r, 4) for r in self._calibration_ratios],
            [round(r, 4) for r in self._calibration_head_forward_ratios],
        )
        self._emit_calibration_status(
            phase="correct_done",
            message="正确坐姿采集完成！请做出不正确坐姿（如低头/前倾），然后点击「拍摄错误姿势样本」。",
        )

    def capture_incorrect_posture_calibration_sample(self) -> None:
        """Phase 2 of calibration: capture an incorrect-posture sample."""
        if len(self._calibration_ratios) < self._required_calibration_samples:
            self.error_occurred.emit("请先完成正确坐姿采集。")
            return

        now = datetime.now()
        sample_index = len(self._calibration_incorrect_ratios) + 1
        day_dir = ensure_day_capture_dir(self.capture_base_dir, now.date())
        image_path = day_dir / f"calib_incorrect_{sample_index}_{now.strftime('%H%M%S')}.jpg"

        try:
            raw_frame = self._capture_frame_for_detection()
            frame, _ = self._prepare_frame_for_detection(raw_frame)
            self.capture_service.save_frame(frame, image_path)
        except CaptureError as exc:
            self.error_occurred.emit(str(exc))
            self._emit_calibration_status(phase="error", message=str(exc))
            return

        ratio_result = self.detector.evaluate_frame(frame)
        if ratio_result.head_ratio is None:
            self.error_occurred.emit("未识别到头部，请调整光线或角度后重试。")
            self._emit_calibration_status(
                phase="error",
                message=f"错误坐姿第 {sample_index}/{self._required_incorrect_samples} 张未识别到头部，请保持正对摄像头并重拍。",
            )
            return

        self._calibration_incorrect_ratios.append(ratio_result.head_ratio)
        self._calibration_incorrect_image_paths.append(str(image_path))

        head_forward_ratio = ratio_result.pose_debug.get("head_forward_ratio")
        if head_forward_ratio is not None and isinstance(head_forward_ratio, (int, float)):
            self._calibration_incorrect_head_forward_ratios.append(float(head_forward_ratio))
            self._log.info(
                "Incorrect calibration sample %d: head_ratio=%.4f, head_forward_ratio=%.4f",
                sample_index, ratio_result.head_ratio, head_forward_ratio,
            )
        else:
            self._calibration_incorrect_head_forward_ratios.append(0.0)
            self._log.info(
                "Incorrect calibration sample %d: head_ratio=%.4f, head_forward_ratio=None",
                sample_index, ratio_result.head_ratio,
            )

        captured_count = len(self._calibration_incorrect_ratios)
        if captured_count < self._required_incorrect_samples:
            self._emit_calibration_status(
                phase="collecting_incorrect",
                message=f"错误坐姿：已完成第 {captured_count}/{self._required_incorrect_samples} 张，请保持错误坐姿继续拍下一张。",
            )
            return

        # ------ Both phases done: calculate midpoint thresholds ------
        self._finalize_calibration()

    def _finalize_calibration(self) -> None:
        """Calculate thresholds from both correct & incorrect posture samples."""
        max_correct_ratio = max(self._calibration_ratios)
        min_incorrect_ratio = min(self._calibration_incorrect_ratios)

        # Head ratio threshold: midpoint between correct-max and incorrect-min.
        # If incorrect ratio is surprisingly lower (edge case), fall back to safety-margin method.
        if min_incorrect_ratio > max_correct_ratio:
            head_ratio_threshold = round((max_correct_ratio + min_incorrect_ratio) / 2.0, 4)
        else:
            head_ratio_threshold = round(max_correct_ratio * (1.0 + CALIBRATION_SAFETY_MARGIN), 4)

        self._log.info(
            "Head ratio calibration: correct_max=%.4f incorrect_min=%.4f → threshold=%.4f",
            max_correct_ratio, min_incorrect_ratio, head_ratio_threshold,
        )

        # Head forward threshold: same midpoint logic.
        head_forward_threshold = 0.0
        if self._calibration_head_forward_ratios and self._calibration_incorrect_head_forward_ratios:
            max_correct_hf = max(self._calibration_head_forward_ratios)
            min_incorrect_hf = min(self._calibration_incorrect_head_forward_ratios)
            if min_incorrect_hf > max_correct_hf:
                head_forward_threshold = round((max_correct_hf + min_incorrect_hf) / 2.0, 4)
            else:
                head_forward_threshold = round(max_correct_hf * (1.0 + CALIBRATION_SAFETY_MARGIN), 4)
            self._log.info(
                "Head forward calibration: correct_max=%.4f incorrect_min=%.4f → threshold=%.4f",
                max_correct_hf, min_incorrect_hf, head_forward_threshold,
            )

        self.update_settings(
            head_ratio_threshold=head_ratio_threshold,
            head_forward_threshold_calibrated=head_forward_threshold,
        )

        self.state_changed.emit("检测中")

        message = f"校准完成！头占比阈值：{head_ratio_threshold:.4f}"
        if head_forward_threshold > 0:
            message += f"，头部前倾阈值：{head_forward_threshold:.4f}"
        self._emit_calibration_status(phase="completed", message=message)

        # Clear all calibration buffers.
        self._clear_calibration_buffers()

    def remove_correct_calibration_sample(self, index: int) -> None:
        """Remove a correct-posture calibration sample by index."""
        if 0 <= index < len(self._calibration_ratios):
            self._calibration_ratios.pop(index)
            if index < len(self._calibration_head_forward_ratios):
                self._calibration_head_forward_ratios.pop(index)
            if index < len(self._calibration_image_paths):
                self._calibration_image_paths.pop(index)
            self._log.info("Removed correct calibration sample at index %d", index)
            self._emit_calibration_status(
                phase="partial",
                message=f"已删除第 {index + 1} 张正确坐姿样本，请重新拍摄。",
            )

    def remove_incorrect_calibration_sample(self, index: int) -> None:
        """Remove an incorrect-posture calibration sample by index."""
        if 0 <= index < len(self._calibration_incorrect_ratios):
            self._calibration_incorrect_ratios.pop(index)
            if index < len(self._calibration_incorrect_head_forward_ratios):
                self._calibration_incorrect_head_forward_ratios.pop(index)
            if index < len(self._calibration_incorrect_image_paths):
                self._calibration_incorrect_image_paths.pop(index)
            self._log.info("Removed incorrect calibration sample at index %d", index)
            self._emit_calibration_status(
                phase="collecting_incorrect",
                message=f"已删除第 {index + 1} 张错误坐姿样本，请重新拍摄。",
            )

    def _clear_calibration_buffers(self) -> None:
        self._calibration_ratios.clear()
        self._calibration_head_forward_ratios.clear()
        self._calibration_image_paths.clear()
        self._calibration_incorrect_ratios.clear()
        self._calibration_incorrect_head_forward_ratios.clear()
        self._calibration_incorrect_image_paths.clear()

    def reset_head_ratio_calibration(self) -> None:
        self._clear_calibration_buffers()
        self.update_settings(head_ratio_threshold=0.0, head_forward_threshold_calibrated=0.0)
        self._emit_calibration_required()

    def open_today_capture_dir(self) -> Path:
        return ensure_day_capture_dir(self.capture_base_dir, datetime.now().date())

    def _capture_frame_for_detection(self) -> object:
        """获取检测用的帧。
        
        如果实时预览正在运行，优先使用缓存的实时预览帧，
        这样可以确保实时画面和立即检测的结果一致。
        """
        if self._live_preview_service.started:
            # 如果实时预览正在运行，使用缓存的最后一帧
            if self._last_live_frame is not None:
                return self._last_live_frame
            try:
                return self._live_preview_service.read_frame()
            except CaptureError:
                pass
        return self.capture_service.capture_frame()

    def _push_live_debug_frame(self) -> None:
        if not self._live_preview_service.started:
            return

        try:
            raw_frame = self._live_preview_service.read_frame()
        except CaptureError as exc:
            self.stop_live_debug()
            self.error_occurred.emit(str(exc))
            return

        # 缓存原始帧（深拷贝），供立即检测使用，确保实时画面和立即检测结果一致
        try:
            import numpy as np
            self._last_live_frame = raw_frame.copy() if hasattr(raw_frame, 'copy') else raw_frame
        except Exception:
            self._last_live_frame = raw_frame

        usage_day, usage_delta = self._system_usage.tick()
        if usage_delta > 0:
            self.stats_service.record_screen_usage(usage_day, usage_delta)

        frame, brightness_info = self._prepare_frame_for_detection(raw_frame)
        result = self._detect_posture(frame, brightness_info=brightness_info)

        debug_info = result.debug_info or {}
        preview_frame = self._live_preview_service.draw_pose_overlay(
            frame,
            debug_info.get("pose_landmarks"),
            debug_info.get("pose_connections"),
            status=result.status,
        )

        payload = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "frame": preview_frame,
            "status": result.status,
            "reasons": list(result.reasons),
            "confidence": result.confidence,
            "source": "live",
            "brightness": round(self.capture_service.frame_brightness(frame), 2),
            "compute_device": self._compute_device,
            "debug_info": debug_info,
        }
        self.live_debug_frame_updated.emit(payload)

        # 优化：在发送完成后清理本地引用（但要保留 payload 引用的数据直到 Qt 处理完）
        # 注意：不能立即 del raw_frame, frame, preview_frame，因为 payload 中引用了 preview_frame
        # Qt 会自动管理这些对象的引用计数，所以不需要手动清理

    def _prepare_frame_for_detection(self, frame: object) -> tuple[object, dict[str, object]]:
        return self.capture_service.normalize_frame_brightness(frame)

    def _detect_posture(self, frame: object, brightness_info: dict[str, object] | None = None) -> PostureResult:
        ratio_result = self.detector.evaluate_frame(frame)

        debug_info = {
            "head_ratio": round(ratio_result.head_ratio, 4) if ratio_result.head_ratio is not None else None,
            "threshold_head_ratio": round(self.detector.ratio_threshold, 4),
            "face_box": ratio_result.face_box,
            "pose_status": ratio_result.pose_status,
            "distance_status": ratio_result.distance_status,
            "pose_landmarks": list(ratio_result.pose_landmarks),
            "pose_connections": list(ratio_result.pose_connections),
            "calibrated": self._is_calibrated(),
            **ratio_result.pose_debug,
            **(brightness_info or {}),
        }

        return PostureResult(
            status=ratio_result.status,
            reasons=ratio_result.reasons,
            confidence=ratio_result.head_ratio,
            debug_info=debug_info,
        )

    def _record_event(self, now: datetime, image_path: Path, result: PostureResult) -> None:
        self.storage.insert_posture_event(
            captured_at=now,
            status=result.status,
            reasons=result.reasons,
            image_path=image_path,
            confidence=result.confidence,
        )
        self.stats_service.record_detection(
            day=now.date(),
            status=result.status,
            interval_seconds=self.settings.capture_interval_seconds,
        )

        # Build a "current message" for UI refresh on every detection.
        debug = result.debug_info or {}
        head_ratio_val = debug.get("head_ratio")
        threshold_val = debug.get("threshold_head_ratio")
        ratio_hint = ""
        if head_ratio_val is not None and threshold_val is not None:
            ratio_hint = f"（头占比 {head_ratio_val:.4f} / 阈值 {threshold_val:.4f}）"

        if result.status == "incorrect":
            ui_message = self.reminder_policy.build_message(result.reasons) + ratio_hint
        elif result.status == "correct":
            ui_message = f"坐姿正常，继续保持。{ratio_hint}"
        else:
            ui_message = "未识别到头部，请调整角度/光线后重试。"

        payload = {
            "time": now.strftime("%H:%M:%S"),
            "status": result.status,
            "reasons": ", ".join(result.reasons) if result.reasons else "-",
            "message": ui_message,
            "image_path": str(image_path),
            "confidence": result.confidence,
            # Detection metrics for dashboard display
            "head_ratio": debug.get("head_ratio"),
            "threshold_head_ratio": debug.get("threshold_head_ratio"),
            "head_forward_ratio": debug.get("head_forward_ratio"),
            "threshold_head_forward": debug.get("threshold_head_forward"),
        }
        self.event_logged.emit(payload)

    def _publish_stats(self) -> None:
        today = datetime.now().date()
        summary: DaySummary = self.stats_service.get_day_summary(today)
        history = self.stats_service.get_last_days(days=7, today=today)
        records: list[PostureRecord] = self.stats_service.get_posture_records(today, limit=200)
        self.summary_updated.emit(summary)
        self.history_updated.emit(history)
        self.posture_records_updated.emit(records)

    def _trigger_reminders(self, now: datetime, result: PostureResult) -> None:
        # IMPORTANT:
        # The dashboard always shows the latest status message per detection.
        # Actual reminder (dim/popup) should trigger at least once when posture
        # transitions into incorrect, even if cooldown would otherwise suppress it.
        #
        # Anti-false-alarm: require N consecutive "incorrect" detections before
        # actually triggering a reminder.  A single transient mis-detection
        # (e.g. momentary head movement) is silently ignored.
        if result.status == "unknown":
            self._consecutive_incorrect = 0
            transitioned = self._last_posture_status != "unknown"
            reasons = ("detection_failed",)
            due = transitioned or self.reminder_policy.should_notify(reasons, now)
            if due:
                self._log.info("Detection failed reminder. transitioned=%s", transitioned)
                self.reminder_triggered.emit(self.reminder_policy.build_message(reasons))

        elif result.status == "incorrect":
            self._consecutive_incorrect += 1
            self._log.info(
                "Incorrect detected. consecutive=%d/%d",
                self._consecutive_incorrect,
                self._consecutive_incorrect_threshold,
            )
            if self._consecutive_incorrect >= self._consecutive_incorrect_threshold:
                transitioned = self._last_posture_status != "incorrect"
                due = transitioned or self.reminder_policy.should_notify(result.reasons, now)
                if due:
                    message = self.reminder_policy.build_message(result.reasons)
                    self._log.info(
                        "Reminder triggered. transitioned=%s reasons=%s consecutive=%d",
                        transitioned,
                        list(result.reasons),
                        self._consecutive_incorrect,
                    )
                    self.reminder_triggered.emit(message)
                else:
                    self._log.info("Reminder suppressed by cooldown. reasons=%s", list(result.reasons))
            else:
                self._log.info(
                    "Incorrect but below consecutive threshold (%d/%d), not triggering yet.",
                    self._consecutive_incorrect,
                    self._consecutive_incorrect_threshold,
                )
        else:
            # correct posture – reset the counter
            self._consecutive_incorrect = 0

        self._last_posture_status = result.status

        if not self.settings.screen_time_enabled:
            return

        elapsed_minutes = (now - self._screen_start).total_seconds() / 60.0
        if elapsed_minutes < self.settings.screen_time_threshold_minutes:
            return

        if self.reminder_policy.should_notify(["screen_time"], now):
            self.reminder_triggered.emit(self.reminder_policy.build_message(["screen_time"]))
            self._screen_start = now

    def settings_as_dict(self) -> dict[str, object]:
        return asdict(self.settings)

    def _emit_debug_info(
        self,
        now: datetime,
        image_path: Path,
        frame: object,
        result: PostureResult,
        source: str,
    ) -> None:
        debug_info = result.debug_info or {}
        payload = {
            "time": now.strftime("%H:%M:%S"),
            "image_path": str(image_path),
            "status": result.status,
            "reasons": list(result.reasons),
            "confidence": result.confidence,
            "source": source,
            "brightness": round(self.capture_service.frame_brightness(frame), 2),
            "debug_info": debug_info,
        }
        self.debug_info_updated.emit(payload)

    def _is_calibrated(self) -> bool:
        return self.settings.head_ratio_threshold > 0.0

    def _effective_head_ratio_threshold(self, threshold: float) -> float:
        if threshold > 0.0:
            return threshold
        return DEFAULT_HEAD_RATIO_THRESHOLD

    @staticmethod
    def _threshold_multiplier(mode: str) -> float:
        mode = str(mode or "strict").lower().strip()
        if mode == "normal":
            return 1.1
        if mode in ("loose", "宽松"):
            return 1.2
        return 1.0

    def _ensure_calibrated_for_detection(self) -> bool:
        if self._is_calibrated():
            return True

        self.state_changed.emit("待校准")
        self.error_occurred.emit("请先在设置页完成坐姿校准（拍摄 3 张正确 + 2 张错误坐姿照片）。")
        self._emit_calibration_required()
        return False

    def _emit_calibration_required(self) -> None:
        message = "首次使用请先校准：拍 3 张正确坐姿 + 2 张错误坐姿照片，系统会自动计算阈值。"
        self.calibration_required.emit(message)
        self._emit_calibration_status(
            phase="required",
            message="请先拍摄 3 张正确坐姿照片开始校准。",
        )

    def _emit_calibration_status(self, phase: str, message: str) -> None:
        payload = {
            "phase": phase,
            "message": message,
            "captured_correct": len(self._calibration_ratios),
            "required_correct": self._required_calibration_samples,
            "captured_incorrect": len(self._calibration_incorrect_ratios),
            "required_incorrect": self._required_incorrect_samples,
            "threshold": self.settings.head_ratio_threshold,
            "head_forward_threshold": getattr(self.settings, "head_forward_threshold_calibrated", 0.0),
            "correct_image_paths": list(self._calibration_image_paths),
            "incorrect_image_paths": list(self._calibration_incorrect_image_paths),
        }
        self.calibration_status_updated.emit(payload)

