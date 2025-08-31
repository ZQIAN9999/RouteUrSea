# run command: uvicorn backend.main:app --reload
# backend/main.py
import os
from fastapi import FastAPI, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict
import requests
import datetime

app = FastAPI(title="RouteUrSea - Emissions & Sustainability Module")

# Mount static directory
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if not os.path.isdir(static_dir):
    raise RuntimeError(f"Static directory not found: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/")
def read_home():
    return FileResponse(os.path.join("static", "home.html"))
    
# Serve index.html at root
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(static_dir, "index.html"))


# -------------------------------
# Weather API integration
# -------------------------------
OPEN_METEO_URL = "https://marine-api.open-meteo.com/v1/marine"

@app.get("/weather")
def get_weather(lat: float, lon: float, date: str = None):
    # Forecast API (temperature, wind, visibility, precipitation, cloud cover)
    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,windspeed_10m,weathercode,visibility,precipitation,cloudcover"
        f"&timezone=auto"
    )
    forecast_res = requests.get(forecast_url).json()

    # Marine API (waves)
    marine_url = (
        f"https://marine-api.open-meteo.com/v1/marine?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=wave_height,wave_direction,wave_period"
        f"&timezone=auto"
    )
    marine_res = requests.get(marine_url).json()

    # Merge hourly data (keep only same timestamps)
    merged_data = []
    if "hourly" in forecast_res and "hourly" in marine_res:
        times = forecast_res["hourly"]["time"]
        for i, t in enumerate(times):
            merged_data.append({
                "time": t,
                "temperature": forecast_res["hourly"]["temperature_2m"][i],
                "windspeed": forecast_res["hourly"]["windspeed_10m"][i],
                "weathercode": forecast_res["hourly"]["weathercode"][i],
                "visibility": forecast_res["hourly"]["visibility"][i],         # NEW
                "precipitation": forecast_res["hourly"]["precipitation"][i],   # NEW
                "cloudcover": forecast_res["hourly"]["cloudcover"][i],         # NEW
                "wave_height": marine_res["hourly"]["wave_height"][i],
                "wave_direction": marine_res["hourly"]["wave_direction"][i],
                "wave_period": marine_res["hourly"]["wave_period"][i],
            })

    return {
        "location": {"lat": lat, "lon": lon},
        "hourly": merged_data
    }

# -------------------------------
# Existing emissions calculation
# -------------------------------
class CalcRequest(BaseModel):
    vessel_type: str
    speed_knots: float
    distance_nm: float
    fuel_type: str
    weather_resistance: Optional[float] = 1.0

# Base fuel rates (liters per NM at nominal speed)
BASE_RATES = {
    "small_coastal": {"base_rate": 0.25, "nominal_speed": 10.0},
    "medium_cargo": {"base_rate": 0.9, "nominal_speed": 12.0},
    "large_container": {"base_rate": 2.8, "nominal_speed": 18.0},
}

# Emission factors (kg CO₂ per liter)
EMISSION_FACTORS = {
    "HFO": 3.114,
    "MDO": 3.206,
    "LNG": 2.75
}

# Sustainability scoring thresholds
ECO_BADGES = {
    "carbon_cutter": 20.0,
    "low_emission_rider": 10.0
}

def compute_fuel(base_rate, nominal_speed, actual_speed, distance_nm, weather_resistance):
    speed_factor = max(actual_speed / nominal_speed, 0.5) if nominal_speed > 0 else 1.0
    return base_rate * distance_nm * speed_factor * weather_resistance

def compute_emissions(fuel_liters, fuel_type):
    ef = EMISSION_FACTORS.get(fuel_type, EMISSION_FACTORS["HFO"])
    return fuel_liters * ef

def get_badge(improvement_pct):
    if improvement_pct >= ECO_BADGES["carbon_cutter"]:
        return "🌱 Carbon Cutter"
    elif improvement_pct >= ECO_BADGES["low_emission_rider"]:
        return "💨 Low Emission Rider"
    else:
        return "🚢 Standard Mode"

#======================================================
#                Check Compliance
#======================================================
def check_marpol_limits(vessel_type: str, fuel_type: str, co2_kg: float, speed_knots: float):
    """
    MARPOL compliance checks.
    Returns a dict with each annex:
    - message: explanatory string
    - passed: True/False
    """
    compliance = {}

    # Annex VI – Air Pollution (emissions)
    if (vessel_type == "small_coastal" and co2_kg > 2500) or \
       (vessel_type == "medium_cargo" and co2_kg > 6000) or \
       (vessel_type == "large_container" and co2_kg > 20000):
        compliance["annex_vi_Air_Pollution"] = {
            "message": "❌ Exceeds emission threshold (Annex VI)",
            "passed": False
        }
    else:
        compliance["annex_vi_Air_Pollution"] = {
            "message": "✅ Within emission limits (Annex VI)",
            "passed": True
        }


    # Annex I – Oil pollution (simplified)
    if vessel_type == "small_coastal" and fuel_type == "HFO":
        compliance["annex_i"] = {
            "message": "⚠️ HFO restricted for small coastal vessels (Annex I)",
            "passed": False
        }
    else:
        compliance["annex_i"] = {
            "message": "✅ Fuel use compliant (Annex I)",
            "passed": True
        }

    # Annex VI – Speed optimization check (eco-speed)
    if (vessel_type == "small_coastal" and speed_knots > 9) or \
       (vessel_type == "medium_cargo" and speed_knots > 12) or \
       (vessel_type == "large_container" and speed_knots > 18):
        compliance["annex_vi_eco_speed"] = {
            "message": "⚠️ Above eco-speed, may increase emissions (Annex VI)",
            "passed": False
        }
    else:
        compliance["annex_vi_eco_speed"] = {
            "message": "✅ Speed within eco-recommendations (Annex VI)",
            "passed": True
        }

    return compliance



@app.post("/api/calculate")
def calculate(req: CalcRequest):
    vt = req.vessel_type if req.vessel_type in BASE_RATES else "medium_cargo"
    params = BASE_RATES[vt]
    base_rate = params["base_rate"]
    nominal_speed = params["nominal_speed"]

    requested_speed = max(req.speed_knots, 1.0)
    eco_speed = max(requested_speed - 2.0, 4.0)
    balanced_speed = max(min(nominal_speed, requested_speed), 4.0)
    fastest_speed = min(requested_speed + 2.0, 30.0)

    scenarios = {}
    for label, speed in [("eco", eco_speed), ("balanced", balanced_speed), ("fastest", fastest_speed)]:
        fuel = compute_fuel(base_rate, nominal_speed, speed, req.distance_nm, req.weather_resistance)
        co2 = compute_emissions(fuel, req.fuel_type)
        eta = round(req.distance_nm / speed, 2) if speed > 0 else None

        scenarios[label] = {
            "speed_knots": round(speed, 2),
            "fuel_liters": round(fuel, 2),
            "co2_kg": round(co2, 2),
            "eta_hours": eta,
            "marpol_compliance": check_marpol_limits(
                vessel_type=vt,
                fuel_type=req.fuel_type,
                co2_kg=co2,
                speed_knots=speed
            )
        }

    # Baseline: nominal speed, calm weather
    baseline_fuel = compute_fuel(base_rate, nominal_speed, nominal_speed, req.distance_nm, 1.0)
    baseline_co2 = compute_emissions(baseline_fuel, req.fuel_type)

    eco_improvement = round(((baseline_co2 - scenarios["eco"]["co2_kg"]) / baseline_co2) * 100, 2) if baseline_co2 > 0 else 0.0
    badge = get_badge(eco_improvement)

    result = {
        "vessel_type": vt,
        "distance_nm": req.distance_nm,
        "requested_speed": requested_speed,
        "fuel_type": req.fuel_type,
        "weather_resistance": req.weather_resistance,
        "baseline_co2_kg": round(baseline_co2, 2),
        "eco_improvement_pct": eco_improvement,
        "eco_rating_badge": badge,
        "scenarios": scenarios
    }

    return result