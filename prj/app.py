"""
DriveSafe: Intelligent Real-Time Driver Drowsiness Detection System
Main Streamlit Application
"""

import streamlit as st
import cv2
import numpy as np
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import mediapipe as mp
import pandas as pd

# Import modules
from modules.camera_init import create_camera_manager
from modules.feature_extraction import FacialFeatureExtractor
from modules.decision_logic import StateClassifier, DriverState
from modules.alerts_intervention import AlertManager, AlertLevel
from modules.location_sos import SOSManager
from modules.data_logger import DataLogger
from config import get_default_config
from utils import (
    setup_logging, draw_face_box, draw_landmarks, draw_eyes,
    draw_text, calculate_fps, resize_for_display, frame_to_rgb
)

# Setup logging
logger = setup_logging(log_level="INFO")

# Page config
st.set_page_config(
    page_title="DriveSafe - Driver Drowsiness Detection",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 8px;
    }
    .alert-critical {
        background-color: #da3633;
        color: white;
        padding: 15px;
        border-radius: 8px;
    }
    .alert-warning {
        background-color: #9e6a03;
        color: white;
        padding: 15px;
        border-radius: 8px;
    }
    .alert-info {
        background-color: #0969da;
        color: white;
        padding: 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


class DriveSafeApp:
    """Main DriveSafe application class."""
    
    def __init__(self):
        """Initialize application."""
        self.config = get_default_config()
        self.camera_manager = None
        self.face_mesh = None
        self.mp_face_mesh = None
        self.feature_extractor = FacialFeatureExtractor()
        self.classifier = StateClassifier(
            calibration_period=self.config.detection.calibration_period,
            ear_threshold_drowsy=self.config.drowsiness.ear_threshold_drowsy,
            ear_threshold_critical=self.config.drowsiness.ear_threshold_critical,
            mar_threshold_yawn=self.config.drowsiness.mar_threshold_yawn,
        )
        self.alert_manager = AlertManager(alert_cooldown=self.config.alert.alert_cooldown)
        self.location_manager = SOSManager()
        self.data_logger = DataLogger()
        
        self.frame_count = 0
        self.frame_times = []
        self.is_running = False
        self.current_frame = None
        self.current_state = DriverState.UNKNOWN
        self.drowsy_start_time = None
        self.critical_start_time = None
        self.last_sos_time = None
        self.blink_count = 0
        self.last_eye_closed = False
        self.detection_start_time = None
        
    def initialize_detectors(self) -> bool:
        """Initialize face and landmark detectors."""
        try:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            logger.info("MediaPipe Face Mesh initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing detectors: {str(e)}")
            return False
    
    def initialize_camera(self) -> bool:
        """Initialize camera."""
        try:
            self.camera_manager = create_camera_manager(vars(self.config.camera))
            success = self.camera_manager.initialize()
            if success:
                logger.info("Camera initialized")
            return success
        except Exception as e:
            logger.error(f"Error initializing camera: {str(e)}")
            return False
    
    def detect_drowsiness(self, features: Dict[str, float]) -> Tuple[DriverState, Dict[str, float]]:
        """Classify driver state based on extracted facial features."""
        # Update classifier thresholds from UI settings before classification
        self.classifier.ear_threshold_drowsy = self.config.drowsiness.ear_threshold_drowsy
        self.classifier.ear_threshold_critical = self.config.drowsiness.ear_threshold_critical
        return self.classifier.classify_state(features)
    
    def trigger_alert(self, state: DriverState, state_info: Dict) -> Dict:
        """Trigger alert workflow based on driver state and persistence."""
        alert_result = {'triggered': False}
        if state == DriverState.CRITICAL:
            alert_result = self.alert_manager.trigger_alert(
                AlertLevel.CRITICAL,
                "WAKE UP! DROWSINESS DETECTED"
            )
            if alert_result.get('triggered'):
                self.data_logger.log_event(
                    'critical_alert',
                    {
                        'message': alert_result.get('message'),
                        'state_info': state_info,
                    }
                )
        elif state == DriverState.DROWSY:
            alert_result = self.alert_manager.trigger_alert(
                AlertLevel.WARNING,
                "WARNING: Drowsiness detected"
            )
            if alert_result.get('triggered'):
                self.data_logger.log_event(
                    'drowsy_alert',
                    {
                        'message': alert_result.get('message'),
                        'state_info': state_info,
                    }
                )
        else:
            self.alert_manager.stop_alert()
            self.drowsy_start_time = None
            self.critical_start_time = None

        return alert_result
    
    def update_alert_timers(self, state: DriverState):
        """Track how long the system has remained in drowsy or critical states."""
        now = time.time()
        if state == DriverState.DROWSY:
            if self.drowsy_start_time is None:
                self.drowsy_start_time = now
        else:
            self.drowsy_start_time = None

        if state == DriverState.CRITICAL:
            if self.critical_start_time is None:
                self.critical_start_time = now
        else:
            self.critical_start_time = None

        if self.critical_start_time and (now - self.critical_start_time) >= 10:
            if not self.last_sos_time or (now - self.last_sos_time) >= 30:
                sos_result = self.location_manager.send_sos_alert(
                    "Critical drowsiness persisted for 10 seconds",
                    {'state_info': state.value}
                )
                self.data_logger.log_event('sos_alert', {'result': sos_result})
                self.last_sos_time = now

    def reset_session(self):
        """Reset session state when detection stops."""
        self.frame_count = 0
        self.frame_times.clear()
        self.current_frame = None
        self.current_state = DriverState.UNKNOWN
        self.drowsy_start_time = None
        self.critical_start_time = None
        self.last_sos_time = None
        self.blink_count = 0
        self.last_eye_closed = False
        self.detection_start_time = None
        self.classifier.reset()
        self.alert_manager.reset()
        self.data_logger.reset()
        logger.info("DriveSafe session reset")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Process single frame for drowsiness detection.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Tuple of (processed_frame, analysis_data)
        """
        analysis = {
            'faces_detected': 0,
            'state': DriverState.UNKNOWN.value,
            'ear': 0.0,
            'mar': 0.0,
            'alert_triggered': False,
            'drowsy_frame_count': 0,
            'critical_frame_count': 0,
            'blink_count': self.blink_count,
            'calibrated': False,
        }

        state_color = {
            DriverState.ACTIVE: (0, 255, 0),
            DriverState.DROWSY: (0, 165, 255),
            DriverState.CRITICAL: (0, 0, 255),
            DriverState.UNKNOWN: (128, 128, 128),
        }
        
        try:
            # Detect faces using MediaPipe Face Mesh
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb)
            if not results.multi_face_landmarks:
                return frame, analysis
            
            face_landmarks = results.multi_face_landmarks[0]
            landmarks_array = np.array([
                [int(point.x * frame.shape[1]), int(point.y * frame.shape[0])]
                for point in face_landmarks.landmark
            ], dtype=np.int32)
            
            if landmarks_array.size == 0:
                return frame, analysis
            
            analysis['faces_detected'] = 1
            
            # Extract features
            features = self.feature_extractor.extract_features(landmarks_array)
            
            # Classify state with time-based detection
            state, state_info = self.detect_drowsiness(features)
            
            analysis['state'] = state_info['state']
            analysis['ear'] = features['ear']
            analysis['mar'] = features['mar']
            analysis['is_drowsy'] = state_info['is_drowsy']
            analysis['is_yawning'] = state_info['is_yawning']
            analysis['drowsy_frame_count'] = state_info.get('drowsy_frame_count', 0)
            analysis['critical_frame_count'] = state_info.get('critical_frame_count', 0)
            analysis['blink_count'] = self.blink_count
            analysis['calibrated'] = state_info.get('calibrated', False)
            
            self.current_state = state
            self.update_alert_timers(state)
            
            # Blink event counting
            eyes_closed = features['ear'] < self.classifier.ear_threshold_drowsy
            if eyes_closed and not self.last_eye_closed:
                self.last_eye_closed = True
            elif not eyes_closed and self.last_eye_closed:
                self.blink_count += 1
                self.last_eye_closed = False
            
            alert_info = self.trigger_alert(state, state_info)
            if alert_info.get('triggered') or self.alert_manager.active_alert:
                analysis['alert_triggered'] = True
            
            if state == DriverState.CRITICAL and not self.alert_manager.intervention_active:
                self.alert_manager.activate_intervention()
            
            # Draw state and metrics
            state_color = {
                DriverState.ACTIVE: (0, 255, 0),
                DriverState.DROWSY: (0, 165, 255),
                DriverState.CRITICAL: (0, 0, 255),
                DriverState.UNKNOWN: (128, 128, 128),
            }
            
            x_min = int(np.min(landmarks_array[:, 0]))
            y_min = int(np.min(landmarks_array[:, 1]))
            x_max = int(np.max(landmarks_array[:, 0]))
            y_max = int(np.max(landmarks_array[:, 1]))
            box_color = state_color.get(state, (128, 128, 128))
            frame = draw_face_box(frame, (x_min, y_min, x_max, y_max), color=box_color)
            
            if self.config.show_landmarks:
                frame = draw_landmarks(frame, landmarks_array)
            
            frame = draw_eyes(frame, landmarks_array, features['left_ear'], 
                            features['right_ear'], self.config.drowsiness.ear_threshold_drowsy)
            
            color = state_color.get(state, (128, 128, 128))
            frame = draw_text(frame, f"State: {state.value}", (10, 30), color=color)
            frame = draw_text(frame, f"EAR: {features['ear']:.3f}", (10, 60))
            frame = draw_text(frame, f"MAR: {features['mar']:.3f}", (10, 90))
            
            # Log frame data
            self.data_logger.log_measurement({
                'frame_number': self.frame_count,
                'driver_state': state.value,
                'ear': features['ear'],
                'left_ear': features['left_ear'],
                'right_ear': features['right_ear'],
                'mar': features['mar'],
                'ear_mean': features['ear_mean'],
                'ear_std': features['ear_std'],
                'is_drowsy': state_info['is_drowsy'],
                'is_yawning': state_info['is_yawning'],
                'alert_triggered': analysis['alert_triggered'],
            })
            
            # Record frame for video clip
            self.data_logger.record_frame(frame)
            
            self.frame_count += 1
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
        
        return frame, analysis
    
    def run_detection_loop(self, output_container):
        """Run main detection loop."""
        if not self.camera_manager or not self.face_mesh:
            st.error("Detectors not initialized")
            return
        
        self.is_running = True
        frame_placeholder = output_container.empty()
        metrics_placeholder = output_container.empty()
        alert_placeholder = st.empty()
        debug_placeholder = st.empty()
        
        try:
            while self.is_running:
                ret, frame = self.camera_manager.capture_frame()
                if not ret:
                    st.error("Failed to capture frame")
                    break
                
                # Save current frame
                self.current_frame = frame
                
                # Process frame
                processed_frame, analysis = self.process_frame(frame)
                
                # Convert to RGB for display
                display_frame = frame_to_rgb(processed_frame)
                
                # Update display
                frame_placeholder.image(display_frame, width=700)
                
                # Update metrics
                col1, col2, col3, col4 = metrics_placeholder.columns(4)
                
                with col1:
                    st.metric("State", analysis['state'])
                with col2:
                    status_text = "ON" if self.alert_manager.active_alert else "OK"
                    st.metric("Alert", status_text)
                with col3:
                    st.metric("EAR", f"{analysis['ear']:.3f}")
                with col4:
                    st.metric("MAR", f"{analysis['mar']:.3f}")
                
                # Alert banner and debug panel
                if self.alert_manager.active_alert or analysis['state'] in [DriverState.DROWSY.value, DriverState.CRITICAL.value]:
                    if analysis['state'] == DriverState.CRITICAL.value:
                        alert_placeholder.markdown(
                            '<div style="padding: 16px; border-radius: 10px; background-color: #c92a2a; color: white; font-weight: bold;">'
                            '🚨 WAKE UP! DROWSINESS DETECTED - Critical state</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        alert_placeholder.markdown(
                            '<div style="padding: 16px; border-radius: 10px; background-color: #ff9800; color: white; font-weight: bold;">'
                            '⚠️ Warning: Drowsiness detected</div>',
                            unsafe_allow_html=True
                        )
                else:
                    alert_placeholder.markdown(
                        '<div style="padding: 12px; border-radius: 10px; background-color: #198754; color: white; font-weight: bold;">'
                        '✅ System Normal</div>',
                        unsafe_allow_html=True
                    )
                
                debug_placeholder.markdown(
                    f"**Debug Panel**  \n"
                    f"EAR threshold: {self.classifier.ear_threshold_drowsy:.2f}  \n"
                    f"Critical threshold: {self.classifier.ear_threshold_critical:.2f}  \n"
                    f"Blink count: {self.blink_count}  \n"
                    f"Drowsy frames: {analysis['drowsy_frame_count']}  \n"
                    f"Critical frames: {analysis['critical_frame_count']}  \n"
                    f"Alert active: {self.alert_manager.active_alert}",
                    unsafe_allow_html=True
                )
                
                # Check intervention
                if self.alert_manager.intervention_active:
                    intervention_status = self.alert_manager.get_intervention_status()
                    with st.sidebar:
                        st.warning("🔒 Math Challenge Active!")
                        st.write(intervention_status['question'])
                        answer = st.number_input("Your answer:", key=f"answer_{int(time.time()*1000)}")
                        
                        if st.button("Submit Answer"):
                            result = self.alert_manager.submit_intervention_answer(int(answer))
                            if result.get('correct'):
                                st.success("✓ Correct! Stay alert!")
                            else:
                                st.error(result.get('message'))
                
                time.sleep(0.03)  # ~30 FPS
                
        except Exception as e:
            st.error(f"Error in detection loop: {str(e)}")
            logger.error(f"Detection loop error: {str(e)}")
        finally:
            self.is_running = False
            if self.camera_manager:
                self.camera_manager.release()


def main():
    """Main Streamlit application."""
    st.title("🚗 DriveSafe - Driver Drowsiness Detection")
    st.markdown("*Real-time AI system for detecting and alerting driver fatigue*")
    
    # Initialize session state
    if 'app' not in st.session_state:
        st.session_state.app = DriveSafeApp()
        st.session_state.initialized = False
    
    app = st.session_state.app
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Initialize system
        if st.button("🚀 Start Detection", use_container_width=True):
            if not st.session_state.initialized:
                with st.spinner("Initializing..."):
                    if app.initialize_detectors() and app.initialize_camera():
                        st.session_state.initialized = True
                        st.success("System initialized!")
                    else:
                        st.error("Failed to initialize system")
            
            if st.session_state.initialized:
                st.session_state.running = True
        
        if st.button("🛑 Stop Detection", use_container_width=True):
            st.session_state.running = False
            app.is_running = False
        
        st.divider()
        st.subheader("Detection Settings")
        
        app.config.drowsiness.ear_threshold_drowsy = st.slider(
            "EAR Drowsy Threshold",
            0.1, 0.5, app.config.drowsiness.ear_threshold_drowsy, 0.01
        )
        
        app.config.drowsiness.ear_threshold_critical = st.slider(
            "EAR Critical Threshold",
            0.05, 0.3, app.config.drowsiness.ear_threshold_critical, 0.01
        )
        
        app.alert_manager.alert_cooldown = st.slider(
            "Alert Cooldown (sec)",
            1, 15, int(app.alert_manager.alert_cooldown)
        )
        
        app.config.show_landmarks = st.checkbox("Show Landmarks", value=app.config.show_landmarks)
        app.alert_manager.enable_audio = st.checkbox("Audio Alerts", value=app.alert_manager.enable_audio)
        
        if st.button("🛑 Stop Alert", use_container_width=True):
            stop_result = app.alert_manager.stop_alert()
            if stop_result.get('stopped'):
                st.success("Alert stopped")
            else:
                st.info("No active alert to stop")
        
        st.divider()
        st.subheader("Location & SOS")
        
        if st.button("📍 Update GPS Location"):
            app.location_manager.update_location(40.7128, -74.0060)
            st.success("Location updated!")
        
        if st.button("🆘 Send SOS Alert"):
            result = app.location_manager.send_sos_alert("Manual SOS triggered")
            if result.get('success'):
                st.success("SOS alert sent!")
            else:
                st.error(f"SOS failed: {result.get('error')}")
    
    # Main content
    if not st.session_state.initialized:
        st.info("👈 Click 'Start Detection' in the sidebar to begin")
        
        # Show info tabs
        tab1, tab2, tab3 = st.tabs(["About", "Features", "How It Works"])
        
        with tab1:
            st.subheader("About DriveSafe")
            st.write("""
            DriveSafe is an intelligent real-time driver drowsiness detection system
            that uses computer vision and AI to:
            
            - Detect facial landmarks in real-time
            - Calculate Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR)
            - Classify driver states (Active, Drowsy, Critical)
            - Trigger audio/visual alerts
            - Record events and video clips
            - Track location and send SOS alerts
            """)
        
        with tab2:
            st.subheader("Key Features")
            st.write("""
            ✅ Real-time face and landmark detection
            ✅ EAR/MAR-based drowsiness detection
            ✅ Adaptive calibration per user
            ✅ Math challenge intervention lock
            ✅ GPS tracking and SOS alerts
            ✅ Event logging and video recording
            ✅ Dashboard with metrics and graphs
            ✅ Production-ready architecture
            """)
        
        with tab3:
            st.subheader("Technical Workflow")
            st.write("""
            1. **Video Capture**: OpenCV captures frames at 30 FPS
            2. **Face Detection**: Dlib detects faces in each frame
            3. **Landmark Extraction**: 68 facial landmarks are extracted
            4. **Feature Engineering**: EAR and MAR are calculated
            5. **State Classification**: Driver state is determined with temporal filtering
            6. **Alert Generation**: Alerts triggered based on state
            7. **Data Logging**: Events and metrics are logged to CSV/JSON
            8. **Dashboard Update**: UI metrics and graph are refreshed
            """)
    
    else:
        # Detection running
        if 'running' not in st.session_state:
            st.session_state.running = False
        
        if st.session_state.running:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.subheader("📹 Live Feed")
                output_container = st.container()
            
            with col2:
                st.subheader("📊 Alerts")
                alert_container = st.container()
                
                with alert_container:
                    if app.current_state == DriverState.CRITICAL:
                        st.markdown('<div class="alert-critical">🚨 CRITICAL STATE</div>', 
                                  unsafe_allow_html=True)
                    elif app.current_state == DriverState.DROWSY:
                        st.markdown('<div class="alert-warning">⚠️ DROWSY</div>', 
                                  unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="alert-info">✅ ACTIVE</div>', 
                                  unsafe_allow_html=True)
            
            with col3:
                st.subheader("📈 Stats")
                stats_container = st.container()
            
            # Run detection in thread
            app.run_detection_loop(output_container)
            
            # Show statistics
            with stats_container:
                summary = app.data_logger.get_summary()
                st.metric("Alerts", app.alert_manager.get_alert_summary()['total_alerts'])
                st.metric("Frames", app.frame_count)
                st.metric("Video Clips", summary['video_clips'])
            
            # Download logs
            st.divider()
            st.subheader("📥 Export Data")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📊 Download Fatigue Log"):
                    try:
                        with open(app.data_logger.fatigue_logger.log_file, 'r') as f:
                            st.download_button(
                                label="CSV Log",
                                data=f.read(),
                                file_name=f"fatigue_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                    except Exception as e:
                        st.error(f"Error downloading log: {str(e)}")
            
            with col2:
                if st.button("📹 Save Video Clip"):
                    clip_path = app.data_logger.save_video_clip("session_highlight")
                    if clip_path:
                        st.success(f"Clip saved: {clip_path}")
                    else:
                        st.error("Failed to save clip")


if __name__ == "__main__":
    main()
