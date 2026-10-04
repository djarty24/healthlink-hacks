import streamlit as st
import serial
import pandas as pd
import sqlite3
import time
from datetime import datetime
import altair as alt
import joblib
import os
from dotenv import load_dotenv
from twilio.rest import Client

# --- LOAD SECRETS FROM .env FILE ---
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_FROM  = os.getenv("TWILIO_PHONE_FROM")
DOCTOR_PHONE_TO    = os.getenv("DOCTOR_PHONE_TO")

# --- CONFIGURATION ---
st.set_page_config(page_title="Solemate AI Clinical", layout="wide")
SERIAL_PORT = '/dev/cu.usbserial-110'
BAUD_RATE = 9600

@st.cache_resource
def load_model():
    return joblib.load('ulcer_model.pkl')

rf_model = load_model()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
html, body, [class*="css"]  { font-family: 'Inter', sans-serif !important; }
div[data-testid="stMetricValue"] { font-weight: 600; letter-spacing: -1px; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE SETUP ---
conn = sqlite3.connect('patient_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS foot_temps") 
c.execute('''CREATE TABLE foot_temps (timestamp DATETIME, temp_f REAL, accel_g REAL, risk_score REAL)''')
conn.commit()

# --- DYNAMIC STATE, COOLDOWN & TIMERS ---
if 'baseline_temp' not in st.session_state:
    st.session_state.baseline_temp = None
if 'data_buffer' not in st.session_state:
    st.session_state.data_buffer = []
if 'last_sms_time' not in st.session_state:
    st.session_state.last_sms_time = 0
if 'critical_start_time' not in st.session_state:
    st.session_state.critical_start_time = None 

# --- UI: PATIENT PROFILE ---
st.title("Solemate: Predictive Monitor for Inflammation")
st.markdown("Dynamic baseline auto-calibration with IMU gait fusion & Sustained SMS Alerting.")

with st.expander("👤 Patient Profile: Active", expanded=True):
    p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 1])
    p_col1.caption("Name / Condition")
    p_col1.write("**Richard H. | Type 2 Diabetes**")
    
    p_col2.caption("Live Calibrated Baseline")
    baseline_display = f"**{st.session_state.baseline_temp:.1f} °F**" if st.session_state.baseline_temp else "**Calibrating...**"
    p_col2.write(baseline_display)
    
    p_col3.caption("Clinical Ulcer History")
    p_col3.write("**2022:** Grade 1 (Left Heel)")
    
    with p_col4:
        st.write("")
        if st.button("🔄 Recalibrate Baseline"):
            st.session_state.baseline_temp = None
            st.session_state.data_buffer = []
            st.session_state.last_sms_time = 0
            st.session_state.critical_start_time = None

st.divider()

col1, col2, col3 = st.columns(3)
metric_placeholder = col1.empty()
imu_placeholder = col2.empty()
ai_placeholder = col3.empty()

st.write("") 
status_placeholder = st.empty()
pause_stream = st.checkbox("Pause Data Stream (Analyze Mode)")
chart_placeholder = st.empty()

# --- SERIAL CONNECTION ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
except Exception as e:
    st.error(f"Hardware Disconnected. Please check USB port: {SERIAL_PORT}")
    st.stop()

# --- REAL-TIME LOOP ---
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
                current_time = time.time()
                
                # --- AUTO CALIBRATION ---
                if st.session_state.baseline_temp is None:
                    st.session_state.baseline_temp = current_temp
                    st.rerun() 
                
                # Buffer Management
                st.session_state.data_buffer.append({"Temperature": current_temp, "Accel": accel_mag})
                if len(st.session_state.data_buffer) > 100:
                    st.session_state.data_buffer.pop(0) 
                
                df = pd.DataFrame(st.session_state.data_buffer)
                df['X'] = range(len(df)) 
                
                rolling_avg_temp = df['Temperature'].tail(15).mean()
                current_delta = rolling_avg_temp - st.session_state.baseline_temp
                
                # ASK THE AI FOR RISK SCORE
                input_features = pd.DataFrame([[current_delta, accel_mag]], columns=['Temp_Delta', 'Accel_Magnitude'])
                risk_score = rf_model.predict(input_features)[0]
                
                c.execute("INSERT INTO foot_temps VALUES (?, ?, ?, ?)", (now, current_temp, accel_mag, risk_score))
                conn.commit()
                
                # --- UPDATE METRICS ---
                metric_placeholder.metric(label="Sustained Plantar Temp", value=f"{rolling_avg_temp:.1f} °F", delta=f"+{current_delta:.1f} °F above baseline", delta_color="inverse")
                activity_state = "High (Walking/Friction)" if abs(accel_mag - 9.81) > 2.0 else "Low (Resting)"
                imu_placeholder.metric(label="Gait Mechanics", value=activity_state)
                ai_placeholder.metric(label="Inflammation Probability", value=f"{risk_score:.1f}%")
                
                # --- SUSTAINED TRIGGER LOGIC & TWILIO SMS ---
                if risk_score >= 80:
                    status_placeholder.error("CRITICAL: High Probability of Impending Tissue Breakdown.")
                    
                    if st.session_state.critical_start_time is None:
                        st.session_state.critical_start_time = current_time
                        
                    elif (current_time - st.session_state.critical_start_time) >= 5.0:
                        if (current_time - st.session_state.last_sms_time) > 60:
                            if TWILIO_ACCOUNT_SID: 
                                try:
                                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                                    
                                    # The TwiML tells the Twilio robot what to say to the patient
                                    twiml_instructions = (
                                        "<Response><Say voice='alice'>Hello. This is an automated alert from your "
                                        "Therma-sole monitor. We have detected elevated friction and heat. "
                                        "Please sit down and remove your shoe to rest your foot.</Say></Response>"
                                    )
                                    
                                    call = client.calls.create(
                                        twiml=twiml_instructions,
                                        from_=TWILIO_PHONE_FROM,
                                        to=DOCTOR_PHONE_TO # This is still your cell phone for the demo!
                                    )
                                    st.session_state.last_sms_time = current_time
                                    st.toast("📞 Automated call dispatched to patient!", icon="🚨")
                                except Exception as e:
                                    st.toast(f"Twilio Error: {e}")
                            else:
                                st.toast(".env keys not found. Skipping SMS.")
                                st.session_state.last_sms_time = current_time
                            
                elif risk_score >= 30:
                    st.session_state.critical_start_time = None 
                    status_placeholder.warning("WARNING: Elevated Risk. Remove pressure from foot.")
                else:
                    st.session_state.critical_start_time = None 
                    status_placeholder.success("Tissue Normal. No active breakdown detected.")
                        
                # --- RENDER CHARTS ---
                with chart_placeholder:
                    x_axis = alt.X('X:Q', scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(labels=False, title=None, ticks=False, grid=False))
                    base_line = alt.Chart(pd.DataFrame({'y': [st.session_state.baseline_temp]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y')
                    
                    y_min = st.session_state.baseline_temp - 2.0
                    y_max = st.session_state.baseline_temp + 10.0
                    
                    temp_line = alt.Chart(df).mark_line(interpolate='monotone', color='#00E5FF', strokeWidth=3).encode(
                        x=x_axis, y=alt.Y('Temperature:Q', scale=alt.Scale(domain=[y_min, y_max]), title="Temp (°F)")
                    ).properties(height=300)
                    top_chart = temp_line + base_line
                    
                    imu_area = alt.Chart(df).mark_area(interpolate='monotone', color='#FF9100', opacity=0.3).encode(
                        x=x_axis, y=alt.Y('Accel:Q', scale=alt.Scale(domain=[8, 20]), title="Force (g)")
                    ).properties(height=150)
                    
                    combined_chart = alt.vconcat(top_chart, imu_area).resolve_scale(x='shared')
                    st.altair_chart(combined_chart, use_container_width=True)
                
            else:
                chart_placeholder.warning(f"Data Format Error: Received: `{line}`")
                    
        except ValueError:
            pass
        
    time.sleep(0.05)