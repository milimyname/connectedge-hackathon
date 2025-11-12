#!/usr/bin/env python3
"""
Simple MQTT Logger
Logs all messages from a specific topic to console and file
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
import argparse

class MQTTLogger:
    def __init__(self, broker, port=1883, topic="te/device/connectedge_test_device/#"):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.message_count = 0
        self.log_file = None
        
        # MQTT client
        self.client = mqtt.Client(client_id="mqtt-logger")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Connected to MQTT broker at {self.broker}:{self.port}")
            client.subscribe(self.topic)
            print(f"📡 Subscribed to: {self.topic}")
            print(f"📝 Logging messages...\n")
            print("=" * 80)
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Log incoming message"""
        self.message_count += 1
        timestamp = datetime.now().isoformat()
        
        # Try to pretty-print JSON, otherwise just show raw
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            payload_str = json.dumps(payload, indent=2)
            is_json = True
        except:
            payload_str = msg.payload.decode('utf-8', errors='ignore')
            is_json = False
        
        # Format log entry
        log_entry = f"""
[{self.message_count}] {timestamp}
Topic: {msg.topic}
Payload:
{payload_str}
{"=" * 80}
"""
        
        # Print to console
        print(log_entry)
        
        # Write to file if enabled
        if self.log_file:
            self.log_file.write(log_entry)
            self.log_file.flush()
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
        print(f"\n🔌 Disconnected from MQTT")
        print(f"📊 Total messages logged: {self.message_count}")
        if self.log_file:
            self.log_file.close()
            print(f"💾 Log saved")
    
    def enable_file_logging(self, filename=None):
        """Enable logging to file"""
        if filename is None:
            filename = f"mqtt_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        self.log_file = open(filename, 'w')
        print(f"💾 Logging to file: {filename}")
        return filename
    
    def run(self):
        """Run the logger (blocking)"""
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Logger stopped by user")

def main():
    parser = argparse.ArgumentParser(description="MQTT Message Logger")
    parser.add_argument("--broker", default="192.168.8.161", help="MQTT broker IP")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--topic", default="te/device/connectedge_test_device/#", 
                        help="MQTT topic to subscribe to (supports wildcards)")
    parser.add_argument("--save", "-s", action="store_true", 
                        help="Save logs to file")
    parser.add_argument("--file", "-f", help="Log file name (default: auto-generated)")
    
    args = parser.parse_args()
    
    # Create logger
    logger = MQTTLogger(
        broker=args.broker,
        port=args.port,
        topic=args.topic
    )
    
    # Enable file logging if requested
    if args.save:
        logger.enable_file_logging(args.file)
    
    # Connect and run
    if logger.connect():
        logger.run()
        logger.disconnect()
    else:
        print("Failed to start logger")

if __name__ == "__main__":
    main()