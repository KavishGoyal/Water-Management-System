from fastapi import FastAPI
from fastapi.responses import HTMLResponse

monitoring_app = FastAPI()

@monitoring_app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("water_dashboard.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content = html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(monitoring_app, host="0.0.0.0", port=8001)