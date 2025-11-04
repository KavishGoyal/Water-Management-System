"""
Multi-Agent Water Crisis Management System
Powered by Groq API with MCP Integration
"""
import asyncio
import cv2
import json
import os
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

# Initialize Groq client
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ==================== Data Models ====================

class AlertLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class WaterSensorData:
    sensor_id: str
    location: str
    water_level: float  # percentage (0-100)
    flow_rate: float  # liters per minute
    temperature: float
    ph_level: float
    timestamp: datetime
    image_path: Optional[str] = None

@dataclass
class RedirectionAction:
    valve_id: str
    action: str  # "open", "close", "partial"
    percentage: int  # 0-100
    destination: str
    priority: int
    reason: str

# ==================== Agent 1: Sensor Monitor Agent ====================

class SensorMonitorAgent:
    """Monitors sensors and processes visual data using Llama-4-Scout"""
    
    def __init__(self):
        self.model = "llama-4-scout-preview"
        self.alert_threshold = 85  # percentage
        
    async def process_camera_feed(self, image_path: str) -> Dict:
        """Analyze water tank image for overflow detection"""
        
        # Read and encode image
        with open(image_path, "rb") as img_file:
            import base64
            image_data = base64.b64encode(img_file.read()).decode()
        
        prompt = """Analyze this water storage facility image and provide:
        1. Estimated water level (0-100%)
        2. Signs of overflow or leakage
        3. Structural condition assessment
        4. Any debris or contamination visible
        5. Urgency level (normal/warning/critical)
        
        Format response as JSON."""
        
        response = groq_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=1024
        )
        
        analysis = response.choices[0].message.content
        return self._parse_vision_analysis(analysis)
    
    def _parse_vision_analysis(self, analysis: str) -> Dict:
        """Parse LLM response into structured data"""
        try:
            # Extract JSON from markdown if present
            if "```json" in analysis:
                analysis = analysis.split("```json")[1].split("```")[0]
            return json.loads(analysis)
        except:
            return {
                "water_level": 0,
                "overflow_detected": False,
                "urgency": "normal",
                "raw_analysis": analysis
            }
    
    async def analyze_sensor_data(self, sensor_data: WaterSensorData) -> Dict:
        """Combine sensor readings with visual analysis"""
        
        alert_level = AlertLevel.NORMAL
        
        if sensor_data.water_level > self.alert_threshold:
            alert_level = AlertLevel.WARNING
        if sensor_data.water_level > 95:
            alert_level = AlertLevel.CRITICAL
        if sensor_data.water_level >= 100:
            alert_level = AlertLevel.EMERGENCY
        
        analysis = {
            "sensor_id": sensor_data.sensor_id,
            "location": sensor_data.location,
            "alert_level": alert_level.value,
            "water_level": sensor_data.water_level,
            "flow_rate": sensor_data.flow_rate,
            "requires_action": alert_level != AlertLevel.NORMAL,
            "timestamp": sensor_data.timestamp.isoformat()
        }
        
        # Add visual analysis if image available
        if sensor_data.image_path:
            vision_data = await self.process_camera_feed(sensor_data.image_path)
            analysis["vision_analysis"] = vision_data
        
        return analysis

# ==================== Agent 2: Prediction Agent ====================

class PredictionAgent:
    """Predicts overflow scenarios using historical data and weather"""
    
    def __init__(self):
        self.model = "llama-3.1-8b-instant"
    
    async def predict_overflow(self, current_data: Dict, weather_data: Dict) -> Dict:
        """Predict overflow probability in next 6-24 hours"""
        
        prompt = f"""As a water management AI, analyze this data and predict overflow risk:

Current Status:
- Water Level: {current_data['water_level']}%
- Flow Rate: {current_data['flow_rate']} L/min
- Location: {current_data['location']}

Weather Forecast:
{json.dumps(weather_data, indent=2)}

Provide:
1. Overflow probability in next 6h, 12h, 24h
2. Expected peak time
3. Estimated excess water volume
4. Recommended preemptive actions
5. Risk level assessment

Response as JSON with fields: overflow_probability_6h, overflow_probability_12h, 
overflow_probability_24h, peak_time, excess_volume_liters, recommendations, risk_level"""

        response = groq_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1500
        )
        
        return self._parse_prediction(response.choices[0].message.content)
    
    def _parse_prediction(self, content: str) -> Dict:
        """Parse prediction response"""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content)
        except:
            return {"error": "parsing_failed", "raw": content}

# ==================== Agent 3: Voice Interface Agent ====================

class VoiceInterfaceAgent:
    """Handles voice input/output using Whisper"""
    
    def __init__(self):
        self.transcription_model = "whisper-large-v3"
        self.supported_languages = ["en", "hi", "es", "fr"]
    
    async def transcribe_command(self, audio_file_path: str) -> str:
        """Convert voice command to text"""
        
        with open(audio_file_path, "rb") as audio_file:
            response = groq_client.audio.transcriptions.create(
                model=self.transcription_model,
                file=audio_file,
                response_format="text"
            )
        
        return response
    
    async def generate_alert_message(self, alert_data: Dict, language: str = "en") -> str:
        """Generate voice alert message"""
        
        templates = {
            "en": f"Alert: Water level at {alert_data['location']} is {alert_data['water_level']}%. {alert_data.get('action', 'Monitoring situation.')}",
            "hi": f"चेतावनी: {alert_data['location']} पर पानी का स्तर {alert_data['water_level']}% है। {alert_data.get('action', 'स्थिति की निगरानी की जा रही है।')}"
        }
        
        return templates.get(language, templates["en"])
    
    def text_to_speech(self, text: str, output_path: str):
        """Convert text to speech (placeholder - integrate TTS service)"""
        # In production, use services like Google TTS, ElevenLabs, or similar
        print(f"🔊 Voice Alert: {text}")
        # Save to output_path

# ==================== Agent 4: Redirection Controller Agent ====================

class RedirectionControllerAgent:
    """Makes real-time valve control decisions"""
    
    def __init__(self):
        self.model = "llama-3.3-70b-versatile"
    
    async def calculate_redirection(self, sensor_analysis: Dict, 
                                   prediction: Dict,
                                   available_destinations: List[Dict]) -> List[RedirectionAction]:
        """Calculate optimal water redirection strategy"""
        
        prompt = f"""You are controlling a water management system. Calculate optimal valve settings:

Current Situation:
{json.dumps(sensor_analysis, indent=2)}

Predictions:
{json.dumps(prediction, indent=2)}

Available Destinations:
{json.dumps(available_destinations, indent=2)}

Priorities (highest to lowest):
1. Drinking water storage (critical)
2. Agricultural reservoirs
3. Industrial use tanks
4. Groundwater recharge pits
5. River/drain discharge (last resort)

Calculate:
1. Which valves to open/close
2. Flow percentage for each valve
3. Estimated time to normalize levels
4. Priority order of destinations

Response as JSON array of actions with: valve_id, action, percentage, destination, priority, reason"""

        response = groq_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        
        actions = self._parse_actions(response.choices[0].message.content)
        return actions
    
    def _parse_actions(self, content: str) -> List[RedirectionAction]:
        """Parse redirection actions"""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            actions_data = json.loads(content)
            
            if isinstance(actions_data, dict) and "actions" in actions_data:
                actions_data = actions_data["actions"]
            
            return [
                RedirectionAction(
                    valve_id=a["valve_id"],
                    action=a["action"],
                    percentage=a["percentage"],
                    destination=a["destination"],
                    priority=a.get("priority", 5),
                    reason=a["reason"]
                )
                for a in actions_data
            ]
        except Exception as e:
            print(f"Error parsing actions: {e}")
            return []

# ==================== Agent 5: MCP Integration Agent ====================

class MCPIntegrationAgent:
    """Handles external integrations via Model Context Protocol"""
    
    def __init__(self):
        self.weather_api_url = "https://api.weatherapi.com/v1"  # Example
        self.valve_control_url = "http://iot-gateway.local/valves"  # Example
    
    async def get_weather_forecast(self, location: str) -> Dict:
        """Fetch weather data via MCP"""
        # Simulated response - integrate real weather API
        return {
            "location": location,
            "rainfall_forecast_mm": [5, 12, 8, 2, 0, 0],  # next 6 hours
            "temperature": 28,
            "humidity": 75,
            "forecast_period": "next_24h"
        }
    
    async def control_valve(self, valve_id: str, action: str, percentage: int) -> Dict:
        """Send commands to IoT valves via MCP"""
        command = {
            "valve_id": valve_id,
            "action": action,
            "percentage": percentage,
            "timestamp": datetime.now().isoformat()
        }
        
        # In production: HTTP request to IoT gateway
        # response = requests.post(self.valve_control_url, json=command)
        
        print(f"🔧 Valve Control: {valve_id} -> {action} at {percentage}%")
        return {"status": "success", "command": command}
    
    async def update_database(self, record: Dict):
        """Update water management database"""
        # In production: Connect to PostgreSQL/MongoDB via MCP
        print(f"💾 Database Updated: {record['sensor_id']} at {record['timestamp']}")
    
    async def send_notifications(self, alert: Dict):
        """Send SMS/Email alerts to authorities"""
        # In production: Integrate with Twilio, SendGrid via MCP
        print(f"📱 Alert Sent: {alert['message']} to {alert.get('recipients', 'authorities')}")

# ==================== Agent 6: Orchestrator Agent ====================

class OrchestratorAgent:
    """Coordinates all agents and manages workflow"""
    
    def __init__(self):
        self.model = "llama-3.3-70b-versatile"
        self.sensor_agent = SensorMonitorAgent()
        self.prediction_agent = PredictionAgent()
        self.voice_agent = VoiceInterfaceAgent()
        self.controller_agent = RedirectionControllerAgent()
        self.mcp_agent = MCPIntegrationAgent()
    
    async def process_overflow_scenario(self, sensor_data: WaterSensorData):
        """Main orchestration workflow"""
        
        print(f"\n{'='*60}")
        print(f"🌊 WATER MANAGEMENT SYSTEM - Processing Alert")
        print(f"{'='*60}\n")
        
        # Step 1: Analyze sensor data
        print("📊 Step 1: Analyzing sensor data...")
        sensor_analysis = await self.sensor_agent.analyze_sensor_data(sensor_data)
        print(f"   Alert Level: {sensor_analysis['alert_level']}")
        print(f"   Water Level: {sensor_analysis['water_level']}%")
        
        # Step 2: Get weather forecast via MCP
        print("\n🌦️  Step 2: Fetching weather forecast...")
        weather_data = await self.mcp_agent.get_weather_forecast(sensor_data.location)
        print(f"   Rainfall forecast: {sum(weather_data['rainfall_forecast_mm'])}mm")
        
        # Step 3: Predict overflow
        print("\n🔮 Step 3: Predicting overflow probability...")
        prediction = await self.prediction_agent.predict_overflow(sensor_analysis, weather_data)
        if "overflow_probability_6h" in prediction:
            print(f"   6h risk: {prediction['overflow_probability_6h']}")
            print(f"   12h risk: {prediction['overflow_probability_12h']}")
        
        # Step 4: Calculate redirection strategy
        if sensor_analysis['requires_action']:
            print("\n🎯 Step 4: Calculating redirection strategy...")
            
            available_destinations = [
                {"id": "tank_drinking_1", "type": "drinking_water", "capacity_remaining": 5000},
                {"id": "reservoir_agri_2", "type": "agriculture", "capacity_remaining": 15000},
                {"id": "recharge_pit_3", "type": "groundwater", "capacity_remaining": 8000}
            ]
            
            actions = await self.controller_agent.calculate_redirection(
                sensor_analysis, prediction, available_destinations
            )
            
            # Step 5: Execute valve controls via MCP
            print("\n⚙️  Step 5: Executing valve controls...")
            for action in actions:
                await self.mcp_agent.control_valve(
                    action.valve_id, 
                    action.action, 
                    action.percentage
                )
                print(f"   ✓ {action.valve_id}: {action.action} -> {action.destination}")
            
            # Step 6: Generate and send voice alert
            print("\n🔊 Step 6: Generating voice alerts...")
            alert_message = await self.voice_agent.generate_alert_message(sensor_analysis)
            await self.mcp_agent.send_notifications({
                "message": alert_message,
                "recipients": ["water_dept", "field_ops"]
            })
            
            # Step 7: Update database
            print("\n💾 Step 7: Updating records...")
            await self.mcp_agent.update_database({
                "sensor_id": sensor_data.sensor_id,
                "timestamp": datetime.now().isoformat(),
                "actions_taken": [vars(a) for a in actions],
                "alert_level": sensor_analysis['alert_level']
            })
        
        print(f"\n{'='*60}")
        print("✅ Workflow Complete")
        print(f"{'='*60}\n")
        
        return {
            "sensor_analysis": sensor_analysis,
            "prediction": prediction,
            "actions_taken": [vars(a) for a in actions] if sensor_analysis['requires_action'] else []
        }

# ==================== Main Execution ====================

async def main():
    """Simulate water overflow scenario"""
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent()
    
    # Simulate sensor data from overflow situation
    sensor_data = WaterSensorData(
        sensor_id="WS_TANK_001",
        location="Community Tank - Sector 12, Jaipur",
        water_level=92.5,  # Critical level
        flow_rate=450,  # High inflow
        temperature=26.5,
        ph_level=7.2,
        timestamp=datetime.now(),
        image_path=None  # Set to actual image path if available
    )
    
    # Process the scenario
    result = await orchestrator.process_overflow_scenario(sensor_data)
    
    # Display summary
    print("\n📋 SUMMARY REPORT")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
