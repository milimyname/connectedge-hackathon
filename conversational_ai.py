#!/usr/bin/env python3
"""
Conversational AI Agent for Industrial IoT
Uses OpenRouter for natural language Q&A about device data
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
from collections import deque
import requests
import os
import argparse

class ConversationalAI:
    def __init__(self, 
                 mqtt_broker="localhost", 
                 mqtt_port=1883,
                 openrouter_api_key=None):
        
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        
        if not self.openrouter_api_key:
            raise ValueError("OpenRouter API key required! Set OPENROUTER_API_KEY env var")
        
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
        
        # LLM model to use
        # self.model = "kwaipilot/kat-coder-pro:free"  # Free tier!
        # self.model = "google/gemini-2.5-flash-lite"  # Free tier!
        self.model = "google/gemini-2.5-flash-lite"  # Free tier!
        # Alternative: "openai/gpt-3.5-turbo" (paid but better)
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Conversational AI connected to MQTT broker")
            
            # Subscribe to sensor data
            client.subscribe("te/device/+/m/sensors")
            print(f"📡 Subscribed to: te/device/+/m/sensors")
            
            # Subscribe to alerts
            client.subscribe("te/device/+/e/ai_alert")
            print(f"📡 Subscribed to: te/device/+/e/ai_alert")
            
            # Subscribe to questions
            client.subscribe("te/device/+/cmd/ask")
            print(f"📡 Subscribed to: te/device/+/cmd/ask")
            
            print("\n💬 Ready for conversations!\n")
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Route incoming messages"""
        # ADD THIS DEBUG LINE AT THE TOP
        # print(f"🔍 DEBUG: Received message on topic: {msg.topic}")
        # print(f"🔍 DEBUG: Payload: {msg.payload.decode('utf-8')[:100]}")
        
        try:
            topic = msg.topic
            device_id = topic.split('/')[2]
            
            # Handle sensor data
            if "/m/sensors" in topic:
                data = json.loads(msg.payload.decode('utf-8'))
                self.store_sensor_data(device_id, data)
                # print(f"✅ Stored sensor data for {device_id}")  # ADD THIS
            
            # Handle alerts
            elif "/e/ai_alert" in topic:
                alert = json.loads(msg.payload.decode('utf-8'))
                self.store_alert(device_id, alert)
                # print(f"✅ Stored alert for {device_id}")  # ADD THIS
            
            # Handle questions
            elif "/cmd/ask" in topic:
                print(f"📨 Received question for {device_id}")  # ADD THIS
                payload = msg.payload.decode('utf-8')
                try:
                    data = json.loads(payload)
                    question = data.get('question', payload)
                except:
                    question = payload
                
                self.handle_question(device_id, question)
        
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def store_sensor_data(self, device_id, data):
        """Store sensor reading in memory"""
        # Initialize if new device
        if device_id not in self.history:
            self.history[device_id] = deque(maxlen=None)  # Keep last 50 readings
        
        # Add timestamp if not present
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow().isoformat() + "Z"
        
        # Store
        self.current_state[device_id] = data
        self.history[device_id].append(data)
    
    def store_alert(self, device_id, alert):
        """Store alert in memory"""
        if device_id not in self.alerts:
            self.alerts[device_id] = deque(maxlen=None)  # Keep last 20 alerts
        
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
        
        metrics = ['pressure', 'temperature', 'vibration', 'flow_rate']
        
        for metric in metrics:
            values = [r.get(metric) for r in readings if metric in r]
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
        print(f"🔍 DEBUG: Building context...")  # ADD THIS
    
        # Build context
        context = self.build_context(device_id)
        print(f"🔍 DEBUG: Context has current_state: {'current_state' in context}")  # ADD THIS
        print(f"🔍 DEBUG: Context: {json.dumps(context, indent=2)[:200]}...")  # ADD THIS
        
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
        """Ask OpenRouter LLM"""
        
        # Build system prompt with context
        system_prompt = f"""You are an industrial equipment monitoring AI assistant for device {device_id}.

CURRENT EQUIPMENT STATUS:
{json.dumps(context, indent=2)}

Your role:
- Answer questions about this industrial pump equipment
- Explain sensor readings (pressure, temperature, vibration, flow_rate)
- Identify problems based on the data
- Provide actionable maintenance recommendations
- Be concise (2-3 sentences max)

IMPORTANT: Base all answers on the actual sensor data provided above. If data is missing, say so.
"""
        
        # Get conversation history
        if device_id not in self.conversations:
            self.conversations[device_id] = []
        
        # Add to conversation
        messages = [
            {"role": "system", "content": system_prompt}
        ] + self.conversations[device_id] + [
            {"role": "user", "content": question}
        ]
        
        try:
            # Call OpenRouter
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-hackathon-project",  # Optional
                    "X-Title": "Industrial IoT AI Agent"  # Optional
                },
                json={
                    "model": self.model,
                    "messages": messages
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            answer = result['choices'][0]['message']['content']
            
            # Store in conversation history
            self.conversations[device_id].append({"role": "user", "content": question})
            self.conversations[device_id].append({"role": "assistant", "content": answer})
            
            # Keep only last 10 messages
            if len(self.conversations[device_id]) > 10:
                self.conversations[device_id] = self.conversations[device_id][-10:]
            
            return answer
            
        except requests.exceptions.Timeout:
            return "Sorry, the AI service timed out. Please try again."
        except requests.exceptions.RequestException as e:
            print(f"❌ OpenRouter API error: {e}")
            return "Sorry, I couldn't connect to the AI service. Please check your API key and internet connection."
        except Exception as e:
            print(f"❌ Error: {e}")
            return "Sorry, I encountered an error processing your question."
    
    def publish_response(self, device_id, question, answer):
        """Publish AI response back to MQTT"""
        response = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat() + "Z"
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
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  AI Agent stopped by user")

    def interactive_mode(self, device_id="tedge_ai"):
        """Interactive Q&A mode"""
        import threading
        
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
                        import os
                        os._exit(0)
                    
                    # Send question via MQTT
                    self.client.publish(
                        f"te/device/{device_id}/cmd/ask",
                        question
                    )
                    
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    self.client.loop_stop()
                    import os
                    os._exit(0)
                except EOFError:
                    break
        
        # Start input thread
        input_thread = threading.Thread(target=input_loop, daemon=True)
        input_thread.start()
        
        # Keep main thread alive for MQTT
        try:
            while True:
                import time
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")

def main():
    parser = argparse.ArgumentParser(description="Conversational AI Agent")
    parser.add_argument("--broker", default="localhost", help="MQTT broker")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--api-key", help="OpenRouter API key")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive Q&A mode")  # ADD THIS
    parser.add_argument("--device-id", default="tedge_ai", help="Device ID for interactive mode")
    
    args = parser.parse_args()
    
    ai = ConversationalAI(
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        openrouter_api_key=args.api_key
    )
    
    ai.connect()
    time.sleep(2)  # Wait for data to start flowing
    
    # ADD THIS BLOCK
    if args.interactive:
        ai.interactive_mode(args.device_id)
        ai.disconnect()
        return
    
    # Otherwise run as service
    ai.run()
    ai.disconnect()


if __name__ == "__main__":
    import time
    main()