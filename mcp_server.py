"""
Model Context Protocol (MCP) Server for Water Management System
Handles external integrations: IoT devices, weather APIs, databases
"""

import asyncio
import json
from typing import Any, Dict, List
from datetime import datetime
import sqlite3

# Install: pip install mcp anthropic-mcp fastapi uvicorn

from mcp.server import Server
from mcp import types
from mcp.types import Resource, Tool, TextContent
import requests

# ==================== MCP Server Implementation ====================

class WaterManagementMCPServer:
    """MCP Server for water management integrations"""
    
    def __init__(self):
        self.server = Server("water-management-mcp")
        self.db_path = "water_management.db"
        self.setup_database()
        self.register_resources()
        self.register_tools()
    
    def setup_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sensor readings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                location TEXT NOT NULL,
                water_level REAL NOT NULL,
                flow_rate REAL NOT NULL,
                temperature REAL,
                ph_level REAL,
                alert_level TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Valve actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS valve_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                valve_id TEXT NOT NULL,
                action TEXT NOT NULL,
                percentage INTEGER,
                destination TEXT,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                message TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def register_resources(self):
        """Register MCP resources"""
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available data resources"""
            return [
                Resource(
                    uri="water://sensors/current",
                    name="Current Sensor Readings",
                    mimeType="application/json",
                    description="Real-time water level and flow data from all sensors"
                ),
                Resource(
                    uri="water://alerts/active",
                    name="Active Alerts",
                    mimeType="application/json",
                    description="Currently active water overflow alerts"
                ),
                Resource(
                    uri="water://valves/status",
                    name="Valve Status",
                    mimeType="application/json",
                    description="Current status of all water valves"
                )
            ]
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource data"""
            
            if uri == "water://sensors/current":
                return json.dumps(self.get_current_sensors())
            
            elif uri == "water://alerts/active":
                return json.dumps(self.get_active_alerts())
            
            elif uri == "water://valves/status":
                return json.dumps(self.get_valve_status())
            
            else:
                return json.dumps({"error": "Resource not found"})
    
    def register_tools(self):
        """Register MCP tools"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="get_weather_forecast",
                    description="Get weather forecast for a location including rainfall predictions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "Location name or coordinates"},
                            "hours": {"type": "integer", "description": "Forecast period in hours", "default": 24}
                        },
                        "required": ["location"]
                    }
                ),
                Tool(
                    name="control_valve",
                    description="Control water valve (open/close/partial)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "valve_id": {"type": "string", "description": "Valve identifier"},
                            "action": {"type": "string", "enum": ["open", "close", "partial"], "description": "Valve action"},
                            "percentage": {"type": "integer", "description": "Opening percentage (0-100)", "default": 100}
                        },
                        "required": ["valve_id", "action"]
                    }
                ),
                Tool(
                    name="record_sensor_reading",
                    description="Record a new sensor reading to database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sensor_id": {"type": "string"},
                            "location": {"type": "string"},
                            "water_level": {"type": "number"},
                            "flow_rate": {"type": "number"},
                            "temperature": {"type": "number"},
                            "ph_level": {"type": "number"},
                            "alert_level": {"type": "string"}
                        },
                        "required": ["sensor_id", "location", "water_level", "flow_rate"]
                    }
                ),
                Tool(
                    name="send_sms_alert",
                    description="Send SMS alert to water management authorities",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "phone_numbers": {"type": "array", "items": {"type": "string"}},
                            "message": {"type": "string"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
                        },
                        "required": ["phone_numbers", "message"]
                    }
                ),
                Tool(
                    name="get_tank_capacity",
                    description="Get remaining capacity of water storage tanks",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tank_ids": {"type": "array", "items": {"type": "string"}},
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            """Execute tool"""
            
            if name == "get_weather_forecast":
                result = await self.get_weather_forecast(
                    arguments["location"],
                    arguments.get("hours", 24)
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif name == "control_valve":
                result = await self.control_valve(
                    arguments["valve_id"],
                    arguments["action"],
                    arguments.get("percentage", 100)
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif name == "record_sensor_reading":
                result = self.record_sensor_reading(arguments)
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif name == "send_sms_alert":
                result = await self.send_sms_alert(
                    arguments["phone_numbers"],
                    arguments["message"],
                    arguments.get("priority", "medium")
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif name == "get_tank_capacity":
                result = self.get_tank_capacity(arguments.get("tank_ids", []))
                return [TextContent(type="text", text=json.dumps(result))]
            
            else:
                return [TextContent(type="text", text=json.dumps({"error": "Tool not found"}))]
 
    # ==================== Tool Implementations ====================
    
    async def get_weather_forecast(self, location: str, hours: int) -> Dict:
        """Fetch weather forecast from API"""
        # Example using OpenWeatherMap API
        api_key = "YOUR_OPENWEATHER_API_KEY"  # Set in environment
        
        try:
            # For demo purposes, returning simulated data
            # In production, use: requests.get(f"https://api.openweathermap.org/...")
            return {
                "location": location,
                "forecast_hours": hours,
                "rainfall_mm_per_hour": [2, 5, 8, 12, 15, 10, 5, 2],
                "temperature_celsius": [28, 27, 26, 25, 25, 26, 27, 28],
                "humidity_percent": [75, 78, 82, 85, 88, 85, 80, 75],
                "wind_speed_kmh": [12, 15, 18, 20, 18, 15, 12, 10],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def control_valve(self, valve_id: str, action: str, percentage: int) -> Dict:
        """Send command to IoT valve controller"""
        
        # In production, send HTTP/MQTT command to IoT gateway
        # Example: requests.post("http://iot-gateway/api/valves", json={...})
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO valve_actions (valve_id, action, percentage, destination, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (valve_id, action, percentage, "auto", "Overflow prevention"))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "valve_id": valve_id,
            "action": action,
            "percentage": percentage,
            "timestamp": datetime.now().isoformat()
        }
    
    def record_sensor_reading(self, data: Dict) -> Dict:
        """Save sensor reading to database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sensor_readings 
            (sensor_id, location, water_level, flow_rate, temperature, ph_level, alert_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["sensor_id"],
            data["location"],
            data["water_level"],
            data["flow_rate"],
            data.get("temperature"),
            data.get("ph_level"),
            data.get("alert_level", "normal")
        ))
        
        conn.commit()
        reading_id = cursor.lastrowid
        conn.close()
        
        return {
            "status": "success",
            "reading_id": reading_id,
            "sensor_id": data["sensor_id"]
        }
    
    async def send_sms_alert(self, phone_numbers: List[str], message: str, priority: str) -> Dict:
        """Send SMS via Twilio or similar service"""
        
        # In production, integrate with Twilio:
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # message = client.messages.create(body=message, from_='+...', to=phone)
        
        print(f"📱 SMS Alert [{priority.upper()}]: {message}")
        print(f"   Recipients: {', '.join(phone_numbers)}")
        
        return {
            "status": "success",
            "sent_to": phone_numbers,
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_tank_capacity(self, tank_ids: List[str]) -> Dict:
        """Query tank capacity information"""
        
        # Simulated tank data - in production, query from IoT sensors
        tanks = {
            "tank_drinking_1": {"total_capacity": 10000, "current_level": 5000},
            "reservoir_agri_2": {"total_capacity": 50000, "current_level": 35000},
            "recharge_pit_3": {"total_capacity": 20000, "current_level": 12000}
        }
        
        result = {}
        for tank_id in tank_ids if tank_ids else tanks.keys():
            if tank_id in tanks:
                data = tanks[tank_id]
                result[tank_id] = {
                    "capacity_liters": data["total_capacity"],
                    "current_level_liters": data["current_level"],
                    "available_capacity": data["total_capacity"] - data["current_level"],
                    "fill_percentage": (data["current_level"] / data["total_capacity"]) * 100
                }
        
        return result
    
    # ==================== Helper Methods ====================
    
    def get_current_sensors(self) -> List[Dict]:
        """Get latest sensor readings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sensor_id, location, water_level, flow_rate, temperature, 
                   ph_level, alert_level, timestamp
            FROM sensor_readings
            WHERE timestamp > datetime('now', '-1 hour')
            ORDER BY timestamp DESC
        """)
        
        readings = []
        for row in cursor.fetchall():
            readings.append({
                "sensor_id": row[0],
                "location": row[1],
                "water_level": row[2],
                "flow_rate": row[3],
                "temperature": row[4],
                "ph_level": row[5],
                "alert_level": row[6],
                "timestamp": row[7]
            })
        
        conn.close()
        return readings
    
    def get_active_alerts(self) -> List[Dict]:
        """Get unresolved alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, sensor_id, alert_level, message, timestamp
            FROM alerts
            WHERE resolved = FALSE
            ORDER BY timestamp DESC
        """)
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                "id": row[0],
                "sensor_id": row[1],
                "alert_level": row[2],
                "message": row[3],
                "timestamp": row[4]
            })
        
        conn.close()
        return alerts
    
    def get_valve_status(self) -> List[Dict]:
        """Get latest valve actions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT valve_id, action, percentage, destination, reason, timestamp
            FROM valve_actions
            WHERE timestamp > datetime('now', '-6 hours')
            ORDER BY timestamp DESC
        """)
        
        actions = []
        for row in cursor.fetchall():
            actions.append({
                "valve_id": row[0],
                "action": row[1],
                "percentage": row[2],
                "destination": row[3],
                "reason": row[4],
                "timestamp": row[5]
            })
        
        conn.close()
        return actions


# ==================== FastAPI REST API Wrapper ====================

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Water Management MCP API")
mcp_server = WaterManagementMCPServer()

@app.get("/")
async def root():
    return {"message": "Water Management MCP Server", "status": "running"}

@app.get("/resources")
async def list_resources():
    """List all MCP resources"""
    resources = mcp_server.server.list_resources()
    return {"resources": [r.dict() for r in resources]}

@app.get("/tools")
async def list_tools():
    """List all MCP tools"""
    # tools = mcp_server.server.list_tools()
    req = types.ListToolsRequest()
    response = await mcp_server.server.request_handlers[types.ListToolsRequest](req)
    # Extract the list of tools from the wrapped result
    tools = response
    return {"tools": [i for i in tools]}

@app.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, arguments: Dict):
    """Execute a specific tool"""
    # if "params" not in arguments:
    #     arguments = {"params": arguments}
    # result = await mcp_server.server.call_tool(tool_name, arguments)
    req = types.CallToolRequest(name=tool_name, **arguments)
    print(req)
    response = await mcp_server.server.request_handlers[types.CallToolRequest](req)
    # response.result.output contains TextContent or equivalent
    # print(response)
    # return {"result": response.get("root") if response else None}
    return response

@app.get("/sensors/current")
async def get_sensors():
    """Get current sensor readings"""
    return mcp_server.get_current_sensors()

@app.get("/alerts/active")
async def get_alerts():
    """Get active alerts"""
    return mcp_server.get_active_alerts()

@app.post("/valve/control")
async def control_valve(valve_id: str, action: str, percentage: int = 100):
    """Control a valve"""
    result = await mcp_server.control_valve(valve_id, action, percentage)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
