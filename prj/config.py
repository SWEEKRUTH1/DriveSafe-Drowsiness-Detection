"""
Configuration Module
Centralized configuration management
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class CameraConfig:
    """Camera configuration."""
    camera_id: int = 0
    frame_width: int = 640
    frame_height: int = 480
    fps: int = 30
    use_camera: bool = True


@dataclass
class DetectionConfig:
    """Face detection configuration."""
    model_path: str = "models/shape_predictor_68_face_landmarks.dat"
    confidence_threshold: float = 0.5
    use_dlib: bool = True
    calibration_period: int = 100


@dataclass
class DrowsinessConfig:
    """Drowsiness detection thresholds."""
    ear_threshold_drowsy: float = 0.25
    ear_threshold_critical: float = 0.15
    mar_threshold_yawn: float = 0.5
    consecutive_frames_drowsy: int = 15
    consecutive_frames_critical: int = 30
    feature_history_length: int = 30


@dataclass
class AlertConfig:
    """Alert configuration."""
    enable_audio: bool = True
    enable_visual: bool = True
    alert_cooldown: float = 5.0
    intervention_duration: float = 30.0
    math_difficulty: str = "medium"


@dataclass
class LocationConfig:
    """Location tracking configuration."""
    sos_enabled: bool = False
    api_key: str = ""
    contact_numbers: list = None
    update_interval: int = 5  # Update location every 5 seconds


@dataclass
class LoggingConfig:
    """Logging configuration."""
    log_directory: str = "logs"
    data_directory: str = "data"
    fatigue_log_file: str = "fatigue_log.csv"
    event_log_file: str = "events.json"
    save_video_clips: bool = True
    clip_duration_frames: int = 150
    log_level: str = "INFO"


@dataclass
class AppConfig:
    """Main application configuration."""
    camera: CameraConfig
    detection: DetectionConfig
    drowsiness: DrowsinessConfig
    alert: AlertConfig
    location: LocationConfig
    logging: LoggingConfig
    
    # UI Settings
    ui_theme: str = "dark"
    update_interval: int = 30  # UI update interval in ms
    dashboard_refresh_rate: float = 1.0  # Dashboard update rate in Hz
    show_fps: bool = True
    show_landmarks: bool = False  # Show facial landmarks
    
    # Performance
    enable_frame_skip: bool = False
    frame_skip_interval: int = 2
    max_frame_size: int = 640


def get_default_config() -> AppConfig:
    """Get default configuration."""
    return AppConfig(
        camera=CameraConfig(),
        detection=DetectionConfig(),
        drowsiness=DrowsinessConfig(),
        alert=AlertConfig(),
        location=LocationConfig(contact_numbers=[]),
        logging=LoggingConfig(),
    )


def create_config_from_dict(config_dict: dict) -> AppConfig:
    """Create configuration from dictionary."""
    try:
        camera = CameraConfig(**config_dict.get('camera', {}))
        detection = DetectionConfig(**config_dict.get('detection', {}))
        drowsiness = DrowsinessConfig(**config_dict.get('drowsiness', {}))
        alert = AlertConfig(**config_dict.get('alert', {}))
        location = LocationConfig(**config_dict.get('location', {}))
        logging_cfg = LoggingConfig(**config_dict.get('logging', {}))
        
        return AppConfig(
            camera=camera,
            detection=detection,
            drowsiness=drowsiness,
            alert=alert,
            location=location,
            logging=logging_cfg,
            ui_theme=config_dict.get('ui_theme', 'dark'),
            update_interval=config_dict.get('update_interval', 30),
            dashboard_refresh_rate=config_dict.get('dashboard_refresh_rate', 1.0),
            show_fps=config_dict.get('show_fps', True),
            show_landmarks=config_dict.get('show_landmarks', False),
            enable_frame_skip=config_dict.get('enable_frame_skip', False),
            frame_skip_interval=config_dict.get('frame_skip_interval', 2),
            max_frame_size=config_dict.get('max_frame_size', 640),
        )
    except Exception as e:
        print(f"Error creating config from dict: {e}")
        return get_default_config()
