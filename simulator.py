#!/usr/bin/env python3
"""
Simple Industrial Device Simulator
Generates realistic sensor data with occasional anomalies
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import math
from datetime import datetime
import argparse

class SimpleDeviceSimulator:
    def __init__(self, device_id="pump1", mqtt_broker="localhost", mqtt_port=1883):
        self.device_id = device_id
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        
        # MQTT client
        self.client = mqtt.Client(client_id=f"simulator-{device_id}")
        self.client.on_connect = self._on_connect
        
        # Normal operating values
        self.base_pressure = 60.0      # PSI
        self.base_temperature = 25.0   # Celsius
        self.base_vibration = 0.03     # mm/s
        self.base_flow_rate = 150.0    # L/min
        
        # Simulation state
        self.iteration = 0
        self.anomaly_mode = False
        self.anomaly_start = None
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def connect(self):
        """Connect to MQTT broker"""
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()
        time.sleep(1)  # Wait for connection
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
        print("🔌 Disconnected from MQTT")
    
    def generate_normal_reading(self):
        """Generate normal sensor readings with small variance"""
        # Add small random noise
        pressure = self.base_pressure + random.uniform(-3, 3)
        temperature = self.base_temperature + random.uniform(-2, 2)
        vibration = self.base_vibration + random.uniform(-0.005, 0.005)
        flow_rate = self.base_flow_rate + random.uniform(-5, 5)
        
        # Add gentle sine wave (simulates normal cycles)
        cycle = math.sin(self.iteration * 0.1)
        pressure += cycle * 2
        temperature += cycle * 1
        
        return {
            "pressure": round(pressure, 2),
            "temperature": round(temperature, 2),
            "vibration": round(vibration, 3),
            "flow_rate": round(flow_rate, 1)
        }
    
    def generate_anomaly_reading(self):
        """Generate anomalous readings (failure scenario)"""
        # Gradually increasing values (simulates equipment degradation)
        steps_since_start = self.iteration - self.anomaly_start
        
        pressure = self.base_pressure + (steps_since_start * 3)  # Rising fast
        temperature = self.base_temperature + (steps_since_start * 2)
        vibration = self.base_vibration + (steps_since_start * 0.01)
        flow_rate = self.base_flow_rate - (steps_since_start * 5)  # Dropping
        
        # Add noise
        pressure += random.uniform(-1, 3)
        temperature += random.uniform(-1, 2)
        vibration += random.uniform(0, 0.005)
        flow_rate += random.uniform(-3, 1)
        
        return {
            "pressure": round(min(pressure, 120), 2),  # Cap at 120
            "temperature": round(min(temperature, 95), 2),  # Cap at 95
            "vibration": round(min(vibration, 0.2), 3),  # Cap at 0.2
            "flow_rate": round(max(flow_rate, 50), 1)  # Floor at 50
        }
    
    def publish_reading(self, data):
        """Publish sensor data to thin-edge.io"""
        # Add metadata
        payload = {
            **data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "device_type": "centrifugal_pump",
            "status": "anomaly" if self.anomaly_mode else "normal"
        }
        
        # Publish to thin-edge.io topic
        topic = f"te/device/{self.device_id}/m/sensors"
        self.client.publish(topic, json.dumps(payload))
        
        # Print to console
        status_icon = "⚠️" if self.anomaly_mode else "✅"
        print(f"{status_icon} [{datetime.now().strftime('%H:%M:%S')}] "
              f"P:{data['pressure']:.1f} T:{data['temperature']:.1f} "
              f"V:{data['vibration']:.3f} F:{data['flow_rate']:.1f}")
    
    def run(self, interval=2.0, anomaly_at=None, duration=None):
        """
        Run simulation
        
        Args:
            interval: Seconds between readings
            anomaly_at: Iteration number to trigger anomaly (None = no anomaly)
            duration: Total iterations to run (None = forever)
        """
        print(f"🚀 Starting simulator for device: {self.device_id}")
        print(f"📊 Publishing to: te/device/{self.device_id}/m/sensors")
        
        if anomaly_at:
            print(f"⚠️  Anomaly scheduled at iteration {anomaly_at}")
        
        print("\n" + "="*60)
        
        try:
            while True:
                self.iteration += 1
                
                # Check if we should trigger anomaly
                if anomaly_at and self.iteration == anomaly_at:
                    self.anomaly_mode = True
                    self.anomaly_start = self.iteration
                    print(f"\n🚨 ANOMALY TRIGGERED at iteration {self.iteration}\n")
                
                # Generate reading
                if self.anomaly_mode:
                    data = self.generate_anomaly_reading()
                else:
                    data = self.generate_normal_reading()
                
                # Publish
                self.publish_reading(data)
                
                # Check duration
                if duration and self.iteration >= duration:
                    print(f"\n⏱️  Completed {duration} iterations")
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n⏹️  Simulation stopped by user")

def main():
    parser = argparse.ArgumentParser(description="Industrial Device Simulator")
    parser.add_argument("--device-id", default="pump1", help="Device ID")
    parser.add_argument("--broker", default="localhost", help="MQTT broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between readings")
    parser.add_argument("--anomaly-at", type=int, help="Trigger anomaly at iteration N")
    parser.add_argument("--duration", type=int, help="Run for N iterations")
    
    args = parser.parse_args()
    
    # Create and run simulator
    simulator = SimpleDeviceSimulator(
        device_id=args.device_id,
        mqtt_broker=args.broker,
        mqtt_port=args.port
    )
    
    simulator.connect()
    simulator.run(
        interval=args.interval,
        anomaly_at=args.anomaly_at,
        duration=args.duration
    )
    simulator.disconnect()

if __name__ == "__main__":
    main()