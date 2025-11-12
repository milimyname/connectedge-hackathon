# ConnectEdge Hackathon - IoT Anomaly Detection & AI Agent

An intelligent IoT monitoring system built on thin-edge.io that detects anomalies in industrial sensor data and provides conversational AI diagnostics.

## 🎯 Overview

This project demonstrates:
- **Real-time anomaly detection** for industrial IoT sensors (pressure, temperature, vibration, flow rate)
- **Automated alerting** through thin-edge.io MQTT topics
- **AI-powered diagnostics** using Ollama for local LLM inference
- **Device simulation** for testing and demonstration

## 🏗️ Architecture

```
Device Simulator → MQTT (thin-edge.io) → Anomaly Detector → Alerts
                                       ↓
                              Conversational AI Agent
```

## 📁 Components

- **`simulator.py`** - Simulates industrial device sensor data with configurable anomalies
- **`anomaly_detector.py`** - Monitors sensor data and publishes alerts when thresholds are exceeded
- **`conversational_ai_ollama.py`** - AI agent that provides conversational diagnostics using Ollama
- **`conversational_ai.py`** - Alternative AI implementation
- **`mqtt_logger.py`** - Utility for logging MQTT messages
- **`docker-compose.yaml`** - thin-edge.io infrastructure setup

## 🚀 Quick Start

### Prerequisites

- Python 3.7+
- Docker & Docker Compose
- [Ollama](https://ollama.ai/) (for AI features)

### Installation

1. **Start thin-edge.io infrastructure:**
```bash
docker-compose up -d
```

2. **Install Python dependencies:**
```bash
pip3 install -r requirements.txt
```

3. **Pull Ollama model (for AI features):**
```bash
ollama pull llama3.1:8b
```

### Running the Demo

**Option 1: Quick Demo Script**
```bash
./run_demo.sh
```

**Option 2: Manual Start**

Start the anomaly detector:
```bash
python3 anomaly_detector.py
```

Start the device simulator (anomaly at iteration 15):
```bash
python3 simulator.py --device-id pump1 --anomaly-at 15 --duration 40
```

Start the AI agent (optional):
```bash
python3 conversational_ai_ollama.py
```

### Monitoring

Subscribe to alerts:
```bash
tedge mqtt sub 'te/device/+/e/ai_alert'
```

Monitor sensor data:
```bash
tedge mqtt sub 'te/device/+/m/sensors'
```

## 🔧 Configuration

### Anomaly Thresholds

Edit `anomaly_detector.py` to adjust sensor thresholds:
- **Pressure**: 40-85 PSI (critical: >95)
- **Temperature**: 15-70°C (critical: >85)
- **Vibration**: 0-0.08 mm/s (critical: >0.15)
- **Flow Rate**: 100-200 L/min (critical: <50)

### Simulator Parameters

```bash
python3 simulator.py \
  --device-id pump1 \
  --anomaly-at 15 \
  --duration 40 \
  --interval 2
```

## 📊 Features

- ✅ Real-time sensor monitoring
- ✅ Statistical anomaly detection
- ✅ Alert cooldown to prevent spam
- ✅ Multi-device support
- ✅ Conversational AI diagnostics
- ✅ Integration with thin-edge.io/Cumulocity

## 🤝 Contributing

This is a hackathon project. Feel free to fork and experiment!

## 📝 License

MIT License
