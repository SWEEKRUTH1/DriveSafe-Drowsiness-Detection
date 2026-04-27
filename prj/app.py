"""
DriveSafe: Intelligent Real-Time Driver Drowsiness Detection System
Redesigned Main Application
"""

import streamlit as st
import cv2
import time
from collections import deque
import pandas as pd
import numpy as np

# Import configurations
from config import get_default_config

# Import new modules
from modules.ui import inject_custom_css, render_metric_card, render_alert_banner
from modules.detection import DetectionModule
from modules.metrics import MetricsEngine
from modules.alert import AlertManager
from modules.logger import MetricsLogger

from utils import draw_face_box, draw_landmarks, draw_text

def initialize_system():
    if 'config' not in st.session_state:
        st.session_state.config = get_default_config()
    
    if 'detector' not in st.session_state:
        st.session_state.detector = DetectionModule(camera_id=st.session_state.config.camera.camera_id)
        
    if 'metrics' not in st.session_state:
        st.session_state.metrics = MetricsEngine(st.session_state.config.drowsiness)
        
    if 'alert' not in st.session_state:
        st.session_state.alert = AlertManager(st.session_state.config.alert)
        
    if 'logger' not in st.session_state:
        st.session_state.logger = MetricsLogger()
        
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False

    if 'ear_plot_data' not in st.session_state:
        st.session_state.ear_plot_data = deque(maxlen=50)

def main():
    st.set_page_config(
        page_title="DriveSafe AI",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_custom_css()
    initialize_system()
    
    cfg = st.session_state.config
    detector = st.session_state.detector
    metrics = st.session_state.metrics
    alert_mgr = st.session_state.alert
    logger = st.session_state.logger
    plot_data = st.session_state.ear_plot_data
    
    # Sidebar
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #58a6ff;'>DriveSafe AI</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #8b949e;'>Intelligent Drowsiness Detection</p>", unsafe_allow_html=True)
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Start", type="primary"):
                st.session_state.is_running = True
        with col2:
            if st.button("🟥 Stop"):
                st.session_state.is_running = False
                detector.release()
                alert_mgr.stop_alert()
                st.rerun()

        if st.button("🛑 Stop Alert"):
            if hasattr(alert_mgr, 'mute_current_alert'):
                alert_mgr.mute_current_alert()
            else:
                alert_mgr.stop_alert()

        st.divider()
        st.subheader("⚙️ Detection Settings")
        
        cfg.drowsiness.ear_threshold_drowsy = st.slider(
            "EAR Threshold", 0.15, 0.40, cfg.drowsiness.ear_threshold_drowsy, 0.01)
        
        cfg.drowsiness.mar_threshold_yawn = st.slider(
            "MAR Threshold", 0.30, 0.90, cfg.drowsiness.mar_threshold_yawn, 0.01)
            
        cfg.drowsiness.head_tilt_threshold = st.slider(
            "Head Tilt (°)", 5.0, 45.0, float(cfg.drowsiness.head_tilt_threshold), 1.0)
            
        st.divider()
        cfg.alert.enable_audio = st.toggle("🔊 Sound Alerts", value=cfg.alert.enable_audio)
        cfg.show_landmarks = st.toggle("👁️ Show Landmarks", value=cfg.show_landmarks)
        
    # Main Dashboard
    if not st.session_state.is_running:
        st.info("👈 Click 'Start' to activate the system.")
        return

    # Real-time UI placeholders
    alert_placeholder = st.empty()
    st.divider()
    
    # Cards Layer
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        ear_placeholder = st.empty()
    with m_col2:
        mar_placeholder = st.empty()
    with m_col3:
        blinks_placeholder = st.empty()
    with m_col4:
        fatigue_placeholder = st.empty()
        
    st.divider()
    
    # Middle Layer: Camera & Plot
    mid_col1, mid_col2 = st.columns([1.5, 1])
    with mid_col1:
        st.caption("📷 LIVE FEED")
        frame_placeholder = st.empty()
    with mid_col2:
        st.caption("📈 EAR OVER TIME")
        chart_placeholder = st.empty()

    # Logs Box
    st.divider()
    exp = st.expander("📋 EVENT HISTORY", expanded=True)
    log_table_placeholder = exp.empty()
    log_file_col1, log_file_col2 = exp.columns(2)
    
    # Static Data Download buttons
    with log_file_col1:
        csv_placeholder = st.empty()
    with log_file_col2:
        json_placeholder = st.empty()

    # Start loop
    while st.session_state.is_running:
        ret, frame = detector.get_frame()
        if not ret:
            # Re-init camera
            detector.__init__(camera_id=cfg.camera.camera_id)
            time.sleep(1)
            continue
            
        # Process detection
        frame, data = detector.process_frame(frame)
        
        ear = mar = tilt = 0
        current_state = -1
        fatigue = 0
        
        if data and data.get('face_detected', False):
            ear = data['ear']
            mar = data['mar']
            tilt = data['tilt']
            is_proper = data.get('is_proper', True)
            
            # Draw on frame
            if cfg.show_landmarks:
                for point in data['landmarks_array']:
                    cv2.circle(frame, (point[0], point[1]), 1, (0, 255, 0), -1)
                    
            # Metrics and State
            current_state, fatigue = metrics.update(True, is_proper, ear, mar, tilt)
        else:
            # Tell metrics no face is registered
            current_state, fatigue = metrics.update(False, False)
        
        # Audio Alerts
        if current_state == 2:
            alert_mgr.start_alert(2)
        elif current_state == 1:
            alert_mgr.start_alert(1)
        else: # Covers 0, -1, -2
            if hasattr(alert_mgr, 'unmute'):
                alert_mgr.unmute()
            alert_mgr.stop_alert()
        
        plot_data.append({"Time": time.time(), "EAR": ear})
        
        # UI Updates
        # 1. Alert Banner
        with alert_placeholder.container():
            render_alert_banner(current_state)
            
        # 2. Cards
        color_eval = lambda e, limit: "#ff7b72" if e < limit else "#58a6ff"
        with ear_placeholder.container():
            render_metric_card("👁️ EAR", f"{ear:.3f}", "", color_eval(ear, cfg.drowsiness.ear_threshold_drowsy))
        with mar_placeholder.container():
            c_mar = "#ff7b72" if mar > cfg.drowsiness.mar_threshold_yawn else "#58a6ff"
            render_metric_card("🗣️ MAR", f"{mar:.3f}", "", c_mar)
        with blinks_placeholder.container():
            render_metric_card("⏱️ BLINKS", metrics.blinks)
        with fatigue_placeholder.container():
            f_color = "#ff7b72" if fatigue > 60 else "#d29922" if fatigue > 30 else "#3fb950"
            render_metric_card("🧠 FATIGUE", fatigue, "%", f_color)

        # 3. Live Feed overlay
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Overlay warning text on frame
        if current_state > 0:
            c_color = (255, 0, 0) if current_state == 2 else (255, 165, 0)
            cv2.putText(frame, "WARNING", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, c_color, 2)
            
        frame_placeholder.image(frame)
        
        # 4. Chart
        if len(plot_data) > 0:
            df = pd.DataFrame(plot_data).set_index("Time")
            chart_placeholder.line_chart(df['EAR'], height=350)
            
        # 5. Logger
        status_txt = "NORMAL" if current_state == 0 else ("WARNING" if current_state == 1 else "CRITICAL")
        logger.log_event(ear, mar, fatigue, status_txt)
        
        log_df = logger.get_dataframe()
        if not log_df.empty:
            log_table_placeholder.dataframe(log_df, hide_index=True)
            
            # Update download buttons (streamit allows putting widgets in placeholders)
            csv_placeholder.download_button("Download CSV", logger.export_csv(), file_name="logs.csv", key=f"csv_{time.time()}")
            json_placeholder.download_button("Download JSON", logger.export_json(), file_name="logs.json", key=f"json_{time.time()}")

        time.sleep(0.03)

if __name__ == "__main__":
    main()
