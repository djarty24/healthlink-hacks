import streamlit as st
import serial
import pandas as pd
import sqlite3
import time
from datetime import datetime
import altair as alt

st.set_page_config(page_title="ThermaSole Clinical", layout="wide")
SERIAL_PORT = '/dev/cu.usbserial-110'
BAUD_RATE = 9600

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
html, body, [class*="css"]  { font-family: 'Inter', sans-serif !important; }
div[data-testid="stMetricValue"] { font-weight: 600; letter-spacing: -1px; }
</style>
""", unsafe_allow_html=True)

conn = sqlite3.connect('patient_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS foot_temps") 
c.execute('''CREATE TABLE foot_temps (timestamp DATETIME, temp_f REAL, accel_g REAL, activity TEXT)''')
conn.commit()

BASELINE_LOWER = 74.2
BASELINE_UPPER = 75.8
CRITICAL_THRESHOLD = BASELINE_UPPER + 4.0

st.title("ThermaSole: Context-Aware Diagnostic Monitor")
st.markdown("Fusing thermal anomalies with IMU gait mechanics to predict and prevent tissue breakdown.")

with st.expander("👤 Patient Profile: Active", expanded=True):
    p_col1, p_col2, p_col3 = st.columns([1, 1, 2])
    p_col1.caption("Name / Condition")
    p_col1.write("**Richard H. | Type 2 Diabetes (Neuropathy)**")
    
    p_col2.caption("Established Baseline Range")
    p_col2.write(f"**{BASELINE_LOWER} °F — {BASELINE_UPPER} °F**")
    
    p_col3.caption("Clinical Ulcer History")
    p_col3.write("**2022:** Grade 1 (Left Heel) | **2024:** Grade 2 (Right Plantar Metatarsal)")

st.divider()

col1, col2, col3 = st.columns(3)
metric_placeholder = col1.empty()
imu_placeholder = col2.empty()
status_placeholder = col3.empty()

st.write("") 
pause_stream = st.checkbox("⏸️ Pause Data Stream (Analyze Mode)")
chart_placeholder = st.empty()

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
except Exception as e:
    st.error(f"Hardware Disconnected. Please check USB port: {SERIAL_PORT}")
    st.stop()

if 'data_buffer' not in st.session_state:
    st.session_state.data_buffer = []

while not pause_stream:
    if ser.in_waiting > 0:
        try:
            raw_line = ser.readline()
            line = raw_line.decode('utf-8').strip()
            parts = line.split(',')
            
            if len(parts) == 2:
                current_temp = float(parts[0])
                accel_mag = float(parts[1])
                now = datetime.now()
                
                if abs(accel_mag - 9.81) > 2.0:
                    activity_state = "High (Walking / Shear Friction)"
                else:
                    activity_state = "Low (Resting)"
                
                c.execute("INSERT INTO foot_temps VALUES (?, ?, ?, ?)", (now, current_temp, accel_mag, activity_state))
                conn.commit()
                
                st.session_state.data_buffer.append({
                    "Temperature": current_temp, 
                    "Activity": activity_state,
                    "Accel": accel_mag
                })
                if len(st.session_state.data_buffer) > 100:
                    st.session_state.data_buffer.pop(0) 
                
                df = pd.DataFrame(st.session_state.data_buffer)
                df['X'] = range(len(df)) 
                
                recent_temps = df['Temperature'].tail(15)
                rolling_avg_temp = recent_temps.mean()
                
                metric_placeholder.metric(label="Sustained Plantar Temp (Rolling)", 
                                          value=f"{rolling_avg_temp:.1f} °F", 
                                          delta=f"{(rolling_avg_temp - BASELINE_UPPER):.1f} °F from upper limit", 
                                          delta_color="inverse")
                
                imu_placeholder.metric(label="Gait / Friction Context", value=activity_state)
                
                if rolling_avg_temp >= CRITICAL_THRESHOLD:
                    if "Walking" in activity_state:
                        status_placeholder.error("🚨 CRITICAL: Sustained Temp Spike + Active Friction.")
                    else:
                        status_placeholder.warning("⚠️ WARNING: Elevated Temp (Patient is resting).")
                else:
                    status_placeholder.success("✅ Baseline Maintained. No active tissue breakdown.")
                        
                # Render Zoomable Chart
                base_upper = alt.Chart(pd.DataFrame({'y': [BASELINE_UPPER]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y')
                base_lower = alt.Chart(pd.DataFrame({'y': [BASELINE_LOWER]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y')
                
                line_chart = alt.Chart(df).mark_line(
                    interpolate='monotone', color='#00E5FF', strokeWidth=3
                ).encode(
                    x=alt.X('X:Q', scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(labels=False, title=None, ticks=False, grid=False)),
                    y=alt.Y('Temperature:Q', scale=alt.Scale(domain=[70, 100]), title="Degrees (°F)")
                )
                
                chart = (line_chart + base_upper + base_lower).properties(height=450).interactive()
                chart_placeholder.altair_chart(chart, use_container_width=True)
                
            else:
                chart_placeholder.warning(f"⚠️ **Data Format Error:** Waiting for dual-sensor data (Temp, Accel). Currently receiving: `{line}`. \\n\\nPlease upload the updated C++ code to your Arduino.")
                    
        except ValueError:
            pass
        except UnicodeDecodeError:
            pass
        
    time.sleep(0.05)

if pause_stream and len(st.session_state.data_buffer) > 0:
    df = pd.DataFrame(st.session_state.data_buffer)
    df['X'] = range(len(df))
    base_upper = alt.Chart(pd.DataFrame({'y': [BASELINE_UPPER]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y')
    base_lower = alt.Chart(pd.DataFrame({'y': [BASELINE_LOWER]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y')
    line_chart = alt.Chart(df).mark_line(interpolate='monotone', color='#00E5FF', strokeWidth=3).encode(
        x=alt.X('X:Q', axis=alt.Axis(labels=False, title=None, ticks=False, grid=False)),
        y=alt.Y('Temperature:Q', scale=alt.Scale(domain=[70, 100]), title="Degrees (°F)")
    )
    chart = (line_chart + base_upper + base_lower).properties(height=450).interactive()
    chart_placeholder.altair_chart(chart, use_container_width=True)