import os
import json
import time
import threading
import cv2
import requests
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, send_file, jsonify
import paho.mqtt.client as mqtt

app = Flask(__name__)

# Config from .env (same as before)
MQTT_BROKER = os.getenv('MQTT_BROKER_HOST')
MQTT_PORT = int(os.getenv('MQTT_BROKER_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC') or None

MQTT_TEMP_TOPIC = os.getenv('MQTT_TEMP_TOPIC') or None
MQTT_HUM_TOPIC = os.getenv('MQTT_HUM_TOPIC') or None
MQTT_WIND_DIR_TOPIC = os.getenv('MQTT_WIND_DIR_TOPIC') or None
MQTT_WIND_SPEED_TOPIC = os.getenv('MQTT_WIND_SPEED_TOPIC') or None

WEBCAM_SOURCE = os.getenv('WEBCAM_SOURCE', '0')
CAPTURE_INTERVAL = int(os.getenv('CAPTURE_INTERVAL', 60))
LAT = os.getenv('LATITUDE')
LON = os.getenv('LONGITUDE')

IMAGE_PATH = '/app/screenshots/latest.jpg'
os.makedirs('/app/screenshots', exist_ok=True)

# Globals
latest_weather = {}
forecast_data = []
sensor_values = {
    'temperature': None,
    'humidity': None,
    'wind_direction': None,
    'wind_speed': None
}
next_capture_time = time.time() + CAPTURE_INTERVAL

sensor_topics = {}
if MQTT_TEMP_TOPIC:      sensor_topics[MQTT_TEMP_TOPIC] = 'temperature'
if MQTT_HUM_TOPIC:       sensor_topics[MQTT_HUM_TOPIC] = 'humidity'
if MQTT_WIND_DIR_TOPIC:  sensor_topics[MQTT_WIND_DIR_TOPIC] = 'wind_direction'
if MQTT_WIND_SPEED_TOPIC: sensor_topics[MQTT_WIND_SPEED_TOPIC] = 'wind_speed'

# SQLite setup
DB_PATH = '/app/data/history.db'
os.makedirs('/app/data', exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_history (
            timestamp TEXT,
            temperature REAL,
            humidity REAL
        )
    ''')
    conn.commit()
    conn.close()

def cleanup_old_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    c.execute("DELETE FROM sensor_history WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()

def save_sensor_data(temp=None, hum=None):
    if temp is None and hum is None:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute('''
        INSERT INTO sensor_history (timestamp, temperature, humidity)
        VALUES (?, ?, ?)
    ''', (now, temp, hum))
    conn.commit()
    conn.close()
    cleanup_old_data()

init_db()

# ============== MQTT ==============
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT")
    if MQTT_TOPIC:
        client.subscribe(MQTT_TOPIC)
    for topic in sensor_topics.keys():
        client.subscribe(topic)

def on_message(client, userdata, msg):
    global latest_weather
    payload_str = msg.payload.decode().strip()

    # Generic topic
    if MQTT_TOPIC and msg.topic == MQTT_TOPIC:
        try:
            latest_weather = json.loads(payload_str)
        except:
            latest_weather = {"raw": payload_str}

    # Specific sensors
    if msg.topic in sensor_topics:
        key = sensor_topics[msg.topic]
        try:
            value = float(payload_str)
        except ValueError:
            value = payload_str  # keep as string if not numeric

        sensor_values[key] = value

        # Save to history only for temp & hum (numeric)
        if key == 'temperature' or key == 'humidity':
            temp = value if key == 'temperature' else None
            hum  = value if key == 'humidity'    else None
            save_sensor_data(temp=temp, hum=hum)

client = mqtt.Client()
if os.getenv('MQTT_USERNAME'):
    client.username_pw_set(os.getenv('MQTT_USERNAME'), os.getenv('MQTT_PASSWORD'))
client.on_connect = on_connect
client.on_message = on_message

# ============== Webcam capture ==============
def cleanup_old_screenshots():
    now = time.time()
    cutoff = now - (24 * 3600)  # 24 hours ago
    folder = '/app/screenshots'
    for f in os.listdir(folder):
        file_path = os.path.join(folder, f)
        if f == 'latest.jpg' or not os.path.isfile(file_path):
            continue
        if os.path.getmtime(file_path) < cutoff:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Cleanup error deleting {f}: {e}")

def capture_webcam():
    global next_capture_time
    while True:
        try:
            source = int(WEBCAM_SOURCE) if WEBCAM_SOURCE.isdigit() else WEBCAM_SOURCE
            cap = cv2.VideoCapture(source)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(IMAGE_PATH, frame)
                ts = time.strftime("%Y%m%d_%H%M%S")
                cv2.imwrite(f"/app/screenshots/{ts}.jpg", frame)
                print(f"📸 Screenshot saved at {ts}")
                cleanup_old_screenshots()
            cap.release()
        except Exception as e:
            print(f"Webcam error: {e}")

        next_capture_time = time.time() + CAPTURE_INTERVAL
        time.sleep(CAPTURE_INTERVAL)

def update_forecast():
    global forecast_data
    while True:
        if LAT and LON:
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    daily = data.get('daily', {})
                    new_forecast = []
                    
                    wmo_codes = {
                        0: "☀️ Clear", 1: "🌤️ Mainly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
                        45: "🌫️ Fog", 48: "🌫️ Rime fog",
                        51: "🌦️ Light drizzle", 53: "🌦️ Moderate drizzle", 55: "🌦️ Dense drizzle",
                        61: "🌧️ Slight rain", 63: "🌧️ Moderate rain", 65: "🌧️ Heavy rain",
                        71: "❄️ Slight snow", 73: "❄️ Moderate snow", 75: "❄️ Heavy snow",
                        95: "⚡ Thunderstorm"
                    }

                    for i in range(len(daily.get('time', []))):
                        code = daily.get('weather_code', [])[i]
                        new_forecast.append({
                            'date': daily['time'][i],
                            'condition': wmo_codes.get(code, "☁️ Cloudy"),
                            'max': daily['temperature_2m_max'][i],
                            'min': daily['temperature_2m_min'][i],
                            'precip': daily['precipitation_probability_max'][i]
                        })
                    forecast_data = new_forecast
            except Exception as e:
                print(f"Forecast error: {e}")
        time.sleep(3600)  # Update every hour

# ============== Flask routes ==============
@app.route('/')
def index():
    return render_template('index.html',
                           weather=latest_weather,
                           sensors=sensor_values,
                           forecast=forecast_data,
                           lat=LAT,
                           lon=LON,
                           capture_interval=CAPTURE_INTERVAL)

@app.route('/latest_image')
def latest_image():
    if os.path.exists(IMAGE_PATH):
        response = send_file(IMAGE_PATH, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return "No image yet", 404

@app.route('/next_capture')
def next_capture():
    global next_capture_time
    seconds = max(0, int(next_capture_time - time.time()))
    return jsonify({'seconds_left': seconds})

@app.route('/history_data')
def history_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    c.execute("""
        SELECT timestamp, temperature, humidity
        FROM sensor_history
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    """, (cutoff,))
    rows = c.fetchall()
    conn.close()

    labels = []
    temps = []
    hums = []

    for row in rows:
        ts, t, h = row
        labels.append(ts)
        temps.append(t if t is not None else None)
        hums.append(h if h is not None else None)

    return jsonify({
        'labels': labels,
        'temperature': temps,
        'humidity': hums
    })

# ============== Start everything ==============
if __name__ == '__main__':
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    threading.Thread(target=capture_webcam, daemon=True).start()
    threading.Thread(target=update_forecast, daemon=True).start()

    port = int(os.getenv('WEB_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
