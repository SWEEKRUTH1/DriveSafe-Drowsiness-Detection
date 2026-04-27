"""
Configuration file reader
Loads configuration from .env and config files
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Example configuration from environment
CONFIG = {
    'camera': {
        'camera_id': int(os.getenv('CAMERA_ID', 0)),
        'frame_width': int(os.getenv('CAMERA_WIDTH', 640)),
        'frame_height': int(os.getenv('CAMERA_HEIGHT', 480)),
        'fps': int(os.getenv('CAMERA_FPS', 30)),
    },
    'detection': {
        'model_path': os.getenv('DETECTION_MODEL_PATH', 'models/shape_predictor_68_face_landmarks.dat'),
        'confidence_threshold': float(os.getenv('CONFIDENCE_THRESHOLD', 0.5)),
    },
    'drowsiness': {
        'ear_threshold_drowsy': float(os.getenv('EAR_THRESHOLD_DROWSY', 0.25)),
        'ear_threshold_critical': float(os.getenv('EAR_THRESHOLD_CRITICAL', 0.15)),
        'mar_threshold_yawn': float(os.getenv('MAR_THRESHOLD_YAWN', 0.5)),
    },
    'alerts': {
        'enable_audio': os.getenv('ENABLE_AUDIO_ALERTS', 'true').lower() == 'true',
        'enable_visual': os.getenv('ENABLE_VISUAL_ALERTS', 'true').lower() == 'true',
        'alert_cooldown': int(os.getenv('ALERT_COOLDOWN', 5)),
    },
    'location': {
        'sos_enabled': os.getenv('SOS_ENABLED', 'false').lower() == 'true',
        'api_endpoint': os.getenv('SOS_API_ENDPOINT', ''),
        'api_key': os.getenv('SOS_API_KEY', ''),
    },
    'logging': {
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_directory': os.getenv('LOG_DIRECTORY', 'logs'),
        'data_directory': os.getenv('DATA_DIRECTORY', 'data'),
    }
}

# Ensure directories exist
Path(CONFIG['logging']['log_directory']).mkdir(parents=True, exist_ok=True)
Path(CONFIG['logging']['data_directory']).mkdir(parents=True, exist_ok=True)
