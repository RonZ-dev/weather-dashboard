# 🌤️ Weather Dashboard

A self-hosted web dashboard that combines **live webcam snapshots** with **real-time weather data** from your local weather station. Weather sensor data is received over MQTT and displayed alongside a webcam image and a 7-day weather forecast, all in one web page.

---

## Features

- 📸 **Webcam snapshots** — captures images at a configurable interval from a USB webcam or an IP camera (HTTP snapshot URL)
- 🌡️ **Live sensor data** — receives temperature, humidity, wind direction, and wind speed from your local weather station via MQTT
- 📡 **MQTT integration** — subscribes to per-sensor topics or a single combined topic
- 📈 **24-hour history charts** — temperature and humidity trends stored in a local SQLite database
- 🗓️ **7-day forecast** — pulled automatically from [Open-Meteo](https://open-meteo.com/) using your configured latitude/longitude (no API key needed)
- 🐳 **Docker-ready** — ships with a `Dockerfile` and `docker-compose.yml` for easy deployment

<img width="1043" height="863" alt="image" src="https://github.com/user-attachments/assets/ad39d144-f0ee-408f-84f5-9b1b528de7d1" />

---

## Requirements

- Docker & Docker Compose (recommended), **or** Python 3.9+ with `pip`
- An MQTT broker (e.g. [Mosquitto](https://mosquitto.org/)) accessible on your network
- A webcam — either a USB device (`/dev/video0`) or an IP camera with an HTTP snapshot endpoint

---

## Quick Start

### With Docker Compose (recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/RonZ-dev/weather-dashboard.git
   cd weather-dashboard
   ```

2. Copy the example environment file and edit it:
   ```bash
   cp example.env .env
   nano .env
   ```

3. Start the container:
   ```bash
   docker compose up -d
   ```

4. Open your browser at `http://localhost:5000` (or whichever port you set in `WEB_PORT`).

> **USB webcam users:** Uncomment the `devices` section in `docker-compose.yml` to pass `/dev/video0` through to the container.

---

### Without Docker (bare Python)

```bash
pip install -r requirements.txt
cp example.env .env
# edit .env with your values
export $(cat .env | xargs)
python app.py
```

---

## Configuration

All configuration is done through environment variables. Copy `example.env` to `.env` and adjust the values to match your setup.

```bash
cp example.env .env
```

### MQTT Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `MQTT_BROKER_HOST` | ✅ Yes | — | Hostname or IP address of your MQTT broker |
| `MQTT_BROKER_PORT` | No | `1883` | Port your MQTT broker listens on |
| `MQTT_USERNAME` | No | — | MQTT username (if your broker requires authentication) |
| `MQTT_PASSWORD` | No | — | MQTT password (if your broker requires authentication) |
| `MQTT_TOPIC` | No | — | Generic topic for raw/combined weather payloads (JSON or plain text). Optional if you use the specific sensor topics below |
| `MQTT_QOS` | No | `0` | MQTT Quality of Service level (`0`, `1`, or `2`) |

### Sensor Topics

These allow you to map individual MQTT topics to specific sensor readings. Leave any variable empty or omit it if your station doesn't publish that sensor.

| Variable | Required | Description |
|---|---|---|
| `MQTT_TEMP_TOPIC` | No | MQTT topic that publishes outdoor temperature values |
| `MQTT_HUM_TOPIC` | No | MQTT topic that publishes outdoor humidity values |
| `MQTT_WIND_DIR_TOPIC` | No | MQTT topic that publishes wind direction values |
| `MQTT_WIND_SPEED_TOPIC` | No | MQTT topic that publishes average wind speed values |

> **Tip:** If you use Home Assistant with a weather station, these topics are often in the format `homeassistant/sensor/<entity_name>/state`.

### Webcam Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEBCAM_SOURCE` | ✅ Yes | `0` | Camera source. Use `0` for the first USB webcam, or a full HTTP URL (e.g. `http://192.168.1.50/snapshot.jpg`) for an IP camera |
| `CAPTURE_INTERVAL` | No | `60` | How often (in seconds) to capture a new snapshot from the webcam |

### Location & Forecast

| Variable | Required | Description |
|---|---|---|
| `LATITUDE` | Recommended | Your location's latitude, used to fetch the 7-day weather forecast from Open-Meteo |
| `LONGITUDE` | Recommended | Your location's longitude |

> If `LATITUDE` and `LONGITUDE` are not set, the forecast section will not be shown. You can find your coordinates by right-clicking any location on Google Maps.

### Web Server

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEB_PORT` | No | `5000` | The port the web dashboard is served on |

---

## Data Storage

Screenshots are saved to the `./screenshots/` directory (mounted as a volume in Docker). The 24-hour sensor history is stored in a SQLite database at `./data/history.db`. Both directories are created automatically on first run.

Data older than 24 hours is cleaned up automatically.

---

## Project Structure

```
weather-dashboard/
├── app.py               # Main Flask application
├── templates/           # Jinja2 HTML templates
├── data/                # SQLite database (auto-created)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── example.env          # Configuration template
```

---

## License

This project is open source. Feel free to fork, modify, and share.
