#!/usr/bin/env python3
"""
Simple Anomaly Detection Plugin for thin-edge.io
Publishes ALARMS to Cumulocity dashboard
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
from collections import deque
import statistics
import argparse

class AnomalyDetector:
    def __init__(self, mqtt_broker="localhost", mqtt_port=1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        
        # MQTT client
        self.client = mqtt.Client(client_id="anomaly-detector")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        # Store recent readings for trend analysis
        self.history = deque(maxlen=20)
        
        # FIXED Thresholds
        self.thresholds = {
            "pressure": {"min": 40, "max": 85, "critical": 95},
            "temperature": {"min": 15, "max": 70, "critical": 85},
            "vibration": {"min": 0, "max": 0.08, "critical": 0.15},
            "flow_rate": {"min": 100, "max": 200, "critical": 50}  # FIXED: critical is low flow
        }
        
        # Alert cooldown (don't spam same alert)
        self.last_alert = {}
        self.alert_cooldown = 10  # seconds
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Anomaly Detector connected to MQTT broker")
            # Subscribe to all device measurements
            client.subscribe("te/device/+/m/sensors")
            print(f"📡 Subscribed to: te/device/+/m/sensors")
            print("\n🎧 Listening for sensor data...\n")
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print("⚠️  Unexpected disconnect. Reconnecting...")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming sensor data"""
        try:
            # Parse message
            data = json.loads(msg.payload.decode('utf-8'))
            
            # Extract device ID from topic: te/device/DEVICE_ID/m/sensors
            device_id = msg.topic.split('/')[2]
            
            # Analyze data
            self.analyze_data(device_id, data)
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def analyze_data(self, device_id, data):
        """Analyze sensor data for anomalies"""
        # Store in history
        data['device_id'] = device_id
        data['analyzed_at'] = datetime.utcnow().isoformat()
        self.history.append(data)
        
        # Run detection algorithms
        alerts = []
        
        # 1. Threshold detection (immediate)
        threshold_alerts = self.detect_threshold_violations(device_id, data)
        alerts.extend(threshold_alerts)
        
        # 2. Trend analysis (if we have enough history)
        if len(self.history) >= 10:
            trend_alerts = self.detect_trends(device_id, data)
            alerts.extend(trend_alerts)
        
        # 3. Pattern detection
        pattern_alerts = self.detect_patterns(device_id, data)
        alerts.extend(pattern_alerts)
        
        # Publish alerts as ALARMS
        for alert in alerts:
            self.publish_alarm(device_id, alert)
    
    def detect_threshold_violations(self, device_id, data):
        """Detect values outside normal thresholds"""
        alerts = []
        
        for metric, thresholds in self.thresholds.items():
            if metric not in data:
                continue
            
            value = data[metric]
            
            # Critical threshold
            if 'critical' in thresholds:
                # For flow_rate, critical is LOW (below threshold)
                if metric == 'flow_rate' and value <= thresholds['critical']:
                    alerts.append({
                        "severity": "critical",
                        "type": "threshold_violation",
                        "metric": metric,
                        "value": value,
                        "message": f"CRITICAL: {metric} at {value} (threshold: {thresholds['critical']})",
                        "recommendation": f"Immediate action required - {metric} critically low"
                    })
                # For others, critical is HIGH (above threshold)
                elif metric != 'flow_rate' and value >= thresholds['critical']:
                    alerts.append({
                        "severity": "critical",
                        "type": "threshold_violation",
                        "metric": metric,
                        "value": value,
                        "message": f"CRITICAL: {metric} at {value} (threshold: {thresholds['critical']})",
                        "recommendation": f"Immediate action required - {metric} critically high"
                    })
            
            # Max threshold (warnings)
            if value > thresholds['max']:
                alerts.append({
                    "severity": "major",
                    "type": "threshold_violation",
                    "metric": metric,
                    "value": value,
                    "message": f"High {metric}: {value} (normal max: {thresholds['max']})",
                    "recommendation": f"Monitor {metric} closely"
                })
            
            # Min threshold (warnings)
            elif value < thresholds['min']:
                alerts.append({
                    "severity": "minor",
                    "type": "threshold_violation",
                    "metric": metric,
                    "value": value,
                    "message": f"Low {metric}: {value} (normal min: {thresholds['min']})",
                    "recommendation": f"Check {metric} sensor or system"
                })
        
        return alerts
    
    def detect_trends(self, device_id, data):
        """Detect concerning trends in the data"""
        alerts = []
        
        # Get recent history for this device
        recent = [h for h in list(self.history)[-10:] if h.get('device_id') == device_id]
        
        if len(recent) < 5:
            return alerts
        
        # Check pressure trend
        if all('pressure' in h for h in recent):
            pressures = [h['pressure'] for h in recent]
            rate = (pressures[-1] - pressures[0]) / len(pressures)
            
            if rate > 2:  # Rising more than 2 PSI per reading
                alerts.append({
                    "severity": "major",
                    "type": "trend_anomaly",
                    "metric": "pressure",
                    "value": data['pressure'],
                    "trend": f"+{rate:.2f} PSI/reading",
                    "message": f"Pressure rising rapidly: +{rate:.2f} PSI per reading",
                    "recommendation": "Investigate cause of pressure increase"
                })
        
        # Check temperature trend
        if all('temperature' in h for h in recent):
            temps = [h['temperature'] for h in recent]
            rate = (temps[-1] - temps[0]) / len(temps)
            
            if rate > 1.5:  # Rising more than 1.5°C per reading
                alerts.append({
                    "severity": "major",
                    "type": "trend_anomaly",
                    "metric": "temperature",
                    "value": data['temperature'],
                    "trend": f"+{rate:.2f}°C/reading",
                    "message": f"Temperature rising rapidly: +{rate:.2f}°C per reading",
                    "recommendation": "Check cooling system"
                })
        
        return alerts
    
    def detect_patterns(self, device_id, data):
        """Detect known failure patterns"""
        alerts = []
        
        # Get recent history for this device
        recent = [h for h in list(self.history)[-5:] if h.get('device_id') == device_id]
        
        if len(recent) < 3:
            return alerts
        
        # Pattern 1: High temp + high vibration = bearing failure
        if all(h.get('temperature', 0) > 65 for h in recent) and \
           all(h.get('vibration', 0) > 0.08 for h in recent):
            alerts.append({
                "severity": "critical",
                "type": "pattern_detected",
                "pattern": "bearing_failure",
                "metric": "bearing",
                "message": "Bearing failure pattern detected (sustained high temp + vibration)",
                "recommendation": "Schedule immediate bearing inspection"
            })
        
        # Pattern 2: Rising pressure + dropping flow = blockage
        if 'flow_rate' in data and data['flow_rate'] < 120:
            if 'pressure' in data and data['pressure'] > 75:
                alerts.append({
                    "severity": "major",
                    "type": "pattern_detected",
                    "pattern": "possible_blockage",
                    "metric": "blockage",
                    "message": "High pressure with low flow rate - possible blockage",
                    "recommendation": "Check for obstructions in system"
                })
        
        return alerts
    
    def publish_alarm(self, device_id, alert):
        """Publish alert as ALARM to thin-edge.io (for Cumulocity)"""
        # Check cooldown
        alert_key = f"{device_id}_{alert['type']}_{alert.get('metric', 'general')}"
        now = datetime.utcnow().timestamp()
        
        if alert_key in self.last_alert:
            if now - self.last_alert[alert_key] < self.alert_cooldown:
                return  # Skip, too soon
        
        self.last_alert[alert_key] = now
        
        # Map severity to Cumulocity levels
        # Cumulocity: CRITICAL, MAJOR, MINOR, WARNING
        severity_map = {
            "critical": "CRITICAL",
            "major": "MAJOR",
            "minor": "MINOR",
            "warning": "WARNING"
        }
        
        # Create alarm payload for Cumulocity
        alarm_payload = {
            "text": alert['message'],
            "severity": severity_map.get(alert['severity'], "MAJOR")
        }
        
        # Generate alarm type (used as unique identifier)
        metric = alert.get('metric', 'general')
        alarm_type = f"ai_{alert['type']}_{metric}"
        
        # Publish to thin-edge.io ALARM topic
        # Format: te/device/DEVICE_ID///a/ALARM_TYPE
        topic = f"te/device/{device_id}///a/{alarm_type}"
        self.client.publish(topic, json.dumps(alarm_payload))
        
        # Print to console
        severity_icon = "🚨" if alert['severity'] == 'critical' else "⚠️"
        print(f"{severity_icon} [{datetime.now().strftime('%H:%M:%S')}] "
              f"[{device_id}] ALARM: {alert['message']}")
    
    def connect(self):
        """Connect to MQTT broker"""
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
        print("🔌 Disconnected from MQTT")
    
    def run(self):
        """Run the detector (blocking)"""
        try:
            # Keep running
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Detector stopped by user")

def main():
    parser = argparse.ArgumentParser(description="Anomaly Detection Plugin")
    parser.add_argument("--broker", default="localhost", help="MQTT broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    
    args = parser.parse_args()
    
    # Create and run detector
    detector = AnomalyDetector(
        mqtt_broker=args.broker,
        mqtt_port=args.port
    )
    
    detector.connect()
    time.sleep(1)  # Wait for connection
    detector.run()
    detector.disconnect()

if __name__ == "__main__":
    import time
    main()