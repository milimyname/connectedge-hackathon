#!/usr/bin/env python3
"""
Conversational AI Agent for Industrial IoT
Uses Ollama for local LLM inference - no API keys needed!
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
from collections import deque
import os
import argparse
import ollama

class ConversationalAI:
    def __init__(self, 
                 mqtt_broker="localhost", 
                 mqtt_port=1883,
                 model="llama3.1:8b"):
        
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.model = model
        
        # MQTT client
        self.client = mqtt.Client(client_id="conversational-ai")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        # Store sensor data in memory
        self.current_state = {}  # Latest reading per device
        self.history = {}  # Device ID -> deque of readings
        self.alerts = {}  # Device ID -> list of alerts
        
        # Conversation history
        self.conversations = {}  # Device ID -> conversation history
        
        print(f"🤖 Using Ollama model: {self.model}")
        
        # Test Ollama connection
        try:
            ollama.list()
            print("✅ Ollama is running")
        except Exception as e:
            print(f"⚠️  Warning: Could not connect to Ollama: {e}")
            print("   Make sure Ollama is running: ollama serve")
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Conversational AI connected to MQTT broker")
            
            client.subscribe("te/device/connectedge_test_device/#")
            print(f"📡 Subscribed to: te/device/connectedge_test_device/#")
            
            client.subscribe("te/device/+/+/+/cmd/ask")
            print(f"📡 Subscribed to: te/device/+/+/+/cmd/ask")
            
            print("\n💬 Ready for conversations!\n")
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Route incoming messages"""
        try:
            topic = msg.topic
            parts = topic.split('/')
            
            # Extract device_id (should be at index 2)
            if len(parts) >= 3:
                device_id = parts[2]
            else:
                print(f"⚠️  Unexpected topic format: {topic}")
                return
            
            # Handle sensor data (any message type with /m/)
            if "/m/" in topic:
                data = json.loads(msg.payload.decode('utf-8'))
                self.store_sensor_data(device_id, data)
                # print(f"📊 Stored sensor data from {device_id}")
            
            # Handle alerts (any event with /e/)
            elif "/e/" in topic and "/e/ai_response" not in topic:
                alert = json.loads(msg.payload.decode('utf-8'))
                self.store_alert(device_id, alert)
                # print(f"🚨 Stored alert from {device_id}")
            
            # Handle questions
            elif "/cmd/ask" in topic:
                payload = msg.payload.decode('utf-8')
                try:
                    data = json.loads(payload)
                    question = data.get('question', payload)
                except:
                    question = payload
                
                self.handle_question(device_id, question)
        
        except Exception as e:
            print(f"❌ Error processing message on topic {msg.topic}: {e}")
    
    def store_sensor_data(self, device_id, data):
        """Store sensor reading in memory"""
        # print(f"💾 Raw sensor data for device {device_id}: {data}")
        
        # Initialize if new device
        if device_id not in self.history:
            self.history[device_id] = deque(maxlen=50)  # Keep last 50 readings
        
        # Flatten nested structure if needed
        # Example: {"Waterpump": {"Temperature": 15875.0}} -> {"Temperature": 15875.0, "source": "Waterpump"}
        flattened_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # Nested structure - flatten it
                flattened_data["source"] = key  # Save the parent key as "source"
                flattened_data.update(value)  # Merge nested values
            else:
                # Already flat
                flattened_data[key] = value
        
        # Add timestamp if not present
        if 'timestamp' not in flattened_data:
            flattened_data['timestamp'] = datetime.utcnow().isoformat() + "Z"
        
        # Store
        self.current_state[device_id] = flattened_data
        self.history[device_id].append(flattened_data)
        
        # print(f"✅ Stored flattened data: {flattened_data}")
    
    def store_alert(self, device_id, alert):
        """Store alert in memory"""
        if device_id not in self.alerts:
            self.alerts[device_id] = deque(maxlen=20)  # Keep last 20 alerts
        
        self.alerts[device_id].append(alert)
    
    def build_context(self, device_id):
        """Build context for LLM"""
        context = {
            "device_id": device_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Current state
        if device_id in self.current_state:
            context["current_state"] = self.current_state[device_id]
        
        # Recent history (last 10 readings)
        if device_id in self.history:
            recent = list(self.history[device_id])[-10:]
            context["recent_history"] = recent
            
            # Calculate trends
            if len(recent) >= 5:
                context["trends"] = self.calculate_trends(recent)
        
        # Active alerts
        if device_id in self.alerts:
            context["active_alerts"] = list(self.alerts[device_id])[-5:]
        
        return context
    
    def calculate_trends(self, readings):
        """Calculate simple trends from readings"""
        trends = {}
        
        # Get all numeric fields from the first reading
        if not readings:
            return trends
        
        # Find all numeric fields (except timestamp and source)
        sample = readings[0]
        numeric_fields = [
            key for key, value in sample.items() 
            if isinstance(value, (int, float)) 
            and key not in ['timestamp', 'time']
        ]
        
        # Calculate trends for each numeric field
        for metric in numeric_fields:
            values = [r.get(metric) for r in readings if metric in r and isinstance(r.get(metric), (int, float))]
            if len(values) >= 3:
                change = values[-1] - values[0]
                rate = change / len(values)
                
                if abs(rate) > 0.01:  # Significant change
                    direction = "rising" if rate > 0 else "falling"
                    trends[metric] = f"{direction} ({rate:+.2f} per reading)"
        
        return trends
    
    def handle_question(self, device_id, question):
        """Handle user question"""
        print(f"\n❓ [{device_id}] Question: {question}")
        
        # Build context
        context = self.build_context(device_id)
        
        if not context.get('current_state'):
            # No data yet
            answer = "I don't have any sensor data for this device yet. Please wait for data to arrive."
        else:
            # Ask LLM
            answer = self.ask_llm(device_id, question, context)
        
        print(f"🤖 [{device_id}] Answer: {answer}\n")
        
        # Publish response
        self.publish_response(device_id, question, answer)
    
    def ask_llm(self, device_id, question, context):
        """Ask Ollama LLM"""
        
        # Build system prompt with context
        system_prompt = f"""You are an industrial equipment monitoring AI assistant for device {device_id}.

CURRENT EQUIPMENT STATUS:
{json.dumps(context, indent=2)}

Your role:
- Answer questions about this industrial equipment
- Explain sensor readings and measurements from the data
- Identify problems or anomalies based on the data
- Provide actionable maintenance recommendations when appropriate
- Be concise (2-3 sentences max)
- Use the actual field names from the sensor data

IMPORTANT: Base all answers on the actual sensor data provided above. If data is missing, say so.
"""
        
        # Get conversation history
        if device_id not in self.conversations:
            self.conversations[device_id] = []
        
        # Build messages for Ollama
        messages = [
            {"role": "system", "content": system_prompt}
        ] + self.conversations[device_id] + [
            {"role": "user", "content": question}
        ]
        
        try:
            # Call Ollama
            print(f"🧠 Thinking with {self.model}...")
            response = ollama.chat(
                model=self.model,
                messages=messages
            )
            
            answer = response['message']['content']
            
            # Store in conversation history
            self.conversations[device_id].append({"role": "user", "content": question})
            self.conversations[device_id].append({"role": "assistant", "content": answer})
            
            # Keep only last 10 messages to avoid context overflow
            if len(self.conversations[device_id]) > 10:
                self.conversations[device_id] = self.conversations[device_id][-10:]
            
            return answer
            
        except Exception as e:
            print(f"❌ Ollama error: {e}")
            return f"Sorry, I encountered an error: {str(e)}. Make sure Ollama is running with the {self.model} model."
    
    def publish_response(self, device_id, question, answer):
        """Publish AI response back to MQTT"""
        response = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "model": self.model
        }
        
        topic = f"te/device/{device_id}/e/ai_response"
        self.client.publish(topic, json.dumps(response))
    
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
        """Run the AI agent (blocking)"""
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  AI Agent stopped by user")

    def interactive_mode(self, device_id="connectedge_test_device"):
        """Interactive Q&A mode"""
        import threading
        import time
        
        print(f"\n💬 Interactive mode for device: {device_id}")
        print("📝 Type your questions (or 'quit' to exit)\n")
        
        def input_loop():
            while True:
                try:
                    question = input("You: ").strip()
                    
                    if not question:
                        continue
                    
                    if question.lower() in ['quit', 'exit', 'q']:
                        print("👋 Goodbye!")
                        self.client.loop_stop()
                        os._exit(0)
                    
                    # Send question via MQTT
                    self.client.publish(
                        f"te/device/{device_id}///cmd/ask",
                        question
                    )
                    
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    self.client.loop_stop()
                    os._exit(0)
                except EOFError:
                    break
        
        # Start input thread
        input_thread = threading.Thread(target=input_loop, daemon=True)
        input_thread.start()
        
        # Keep main thread alive for MQTT
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")

def main():
    parser = argparse.ArgumentParser(description="Conversational AI Agent with Ollama")
    parser.add_argument("--broker", default="192.168.8.161", help="MQTT broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model to use")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive Q&A mode")
    parser.add_argument("--device-id", default="connectedge_test_device", help="Device ID for interactive mode")
    
    args = parser.parse_args()
    
    ai = ConversationalAI(
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        model=args.model
    )
    
    ai.connect()
    
    import time
    time.sleep(2)  # Wait for connection and initial data
    
    if args.interactive:
        ai.interactive_mode(args.device_id)
        ai.disconnect()
        return
    
    # Otherwise run as service
    ai.run()
    ai.disconnect()


if __name__ == "__main__":
    main()