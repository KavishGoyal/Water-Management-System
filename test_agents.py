import asyncio
from water_management_agents import *

async def test_sensor_agent():
    agent = SensorMonitorAgent()
    
    sensor_data = WaterSensorData(
        sensor_id="TEST_001",
        location="Test Tank",
        water_level=95.0,
        flow_rate=500,
        temperature=25.0,
        ph_level=7.0,
        timestamp=datetime.now()
    )
    
    result = await agent.analyze_sensor_data(sensor_data)
    return {"Sensor Agent Test Passed": result['alert_level'] == 'critical'}

async def test_prediction_agent():
    agent = PredictionAgent()
    
    current_data = {
        'water_level': 92,
        'flow_rate': 450,
        'location': 'Test Tank'
    }
    
    weather_data = {
        'rainfall_forecast_mm': [10, 15, 20],
        'temperature': 28
    }
    
    result = await agent.predict_overflow(current_data, weather_data)
    assert 'overflow_probability_6h' in result
    print("✅ Prediction Agent Test Passed")

# Run tests
print(asyncio.run(test_sensor_agent()))
asyncio.run(test_prediction_agent())