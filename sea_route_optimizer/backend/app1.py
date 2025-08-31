# backend/main.py
import os, json, math, heapq, logging
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from shapely.geometry import shape, Point
from shapely.ops import unary_union
import requests

# ----------------------------
# App paths and data setup
# ----------------------------
APP_ROOT = Path(__file__).parent
DATA_DIR = APP_ROOT / "data"
FRONTEND_DIR = APP_ROOT.parent / "frontend"
TEMPLATE_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

PORTS_FILE = DATA_DIR / "ports.geojson"
ISLANDS_FILE = DATA_DIR / "islands.geojson"
LAND_FILE = DATA_DIR / "land.geojson"
ROCKS_FILE = DATA_DIR / "rocks.geojson"

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# ----------------------------
# Sea grid constants
# ----------------------------
SEA_BOUNDS = {"lat_min": -15.0, "lat_max": 25.0, "lon_min": 90.0, "lon_max": 140.0}
GRID_RES = 0.2
R_MAX = int((SEA_BOUNDS["lat_max"] - SEA_BOUNDS["lat_min"]) / GRID_RES)
C_MAX = int((SEA_BOUNDS["lon_max"] - SEA_BOUNDS["lon_min"]) / GRID_RES)

# ----------------------------
# Helpers
# ----------------------------
def haversine_nm(lat1, lon1, lat2, lon2):
    R_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(min(1, math.sqrt(a)))
    km = R_km * c
    return km * 0.539957

def latlon_to_grid(lat, lon):
    r = int((lat - SEA_BOUNDS["lat_min"]) / GRID_RES)
    c = int((lon - SEA_BOUNDS["lon_min"]) / GRID_RES)
    return max(0, min(R_MAX-1, r)), max(0, min(C_MAX-1, c))

def grid_to_latlon(r, c):
    lat = SEA_BOUNDS["lat_min"] + r * GRID_RES + GRID_RES/2.0
    lon = SEA_BOUNDS["lon_min"] + c * GRID_RES + GRID_RES/2.0
    return lat, lon

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ----------------------------
# Load static data
# ----------------------------
ISLANDS = load_json(ISLANDS_FILE) or {"type":"FeatureCollection","features":[]}
LAND = load_json(LAND_FILE) or {"type":"FeatureCollection","features":[]}
ROCKS_RAW = load_json(ROCKS_FILE) or {"elements":[]}
PORTS_RAW = load_json(PORTS_FILE) or {"elements":[]}

ROCKS = [{"lat": e["lat"], "lon": e["lon"], "name": e.get("tags", {}).get("name","rock")}
         for e in ROCKS_RAW.get("elements", []) if e.get("type")=="node" and "lat" in e]

PORTS = []
if isinstance(PORTS_RAW, dict):
    if "elements" in PORTS_RAW:
        for e in PORTS_RAW.get("elements", []):
            if e.get("type") == "node":
                PORTS.append({"lat": e["lat"], "lon": e["lon"], "name": e.get("tags", {}).get("name","port")})
    elif PORTS_RAW.get("type") == "FeatureCollection":
        for feat in PORTS_RAW.get("features", []):
            geom = feat.get("geometry", {})
            if geom.get("type") == "Point":
                lon, lat = geom["coordinates"]
                PORTS.append({"lat": lat, "lon": lon, "name": feat.get("properties", {}).get("name","port")})

ALL_ISLAND_FEATURES = []
if ISLANDS.get("type") == "FeatureCollection":
    ALL_ISLAND_FEATURES += ISLANDS.get("features", [])
if LAND.get("type") == "FeatureCollection":
    ALL_ISLAND_FEATURES += LAND.get("features", [])

OBSTACLES_UNION = unary_union([shape(f["geometry"]) for f in ALL_ISLAND_FEATURES if f.get("geometry")])

# ----------------------------
# Mock AIS
# ----------------------------
def get_ships_near_area(lat_min, lat_max, lon_min, lon_max):
    return [
  {"lat": 1.30, "lon": 103.85, "name": "Vessel-001"},
  {"lat": 14.60, "lon": 120.98, "name": "Vessel-002"},
  {"lat": 3.10, "lon": 101.42, "name": "Vessel-003"},
  {"lat": 6.80, "lon": 101.26, "name": "Vessel-004"},
  {"lat": 10.75, "lon": 106.71, "name": "Vessel-005"},
  {"lat": -6.10, "lon": 106.81, "name": "Vessel-006"},
  {"lat": 7.90, "lon": 98.35, "name": "Vessel-007"},
  {"lat": 1.12, "lon": 104.12, "name": "Vessel-008"},
  {"lat": 5.42, "lon": 100.32, "name": "Vessel-009"},
  {"lat": 13.70, "lon": 109.22, "name": "Vessel-010"},
  {"lat": 15.30, "lon": 119.75, "name": "Vessel-011"},
  {"lat": 8.35, "lon": 124.28, "name": "Vessel-012"},
  {"lat": 4.55, "lon": 118.12, "name": "Vessel-013"},
  {"lat": 9.45, "lon": 123.25, "name": "Vessel-014"},
  {"lat": 12.25, "lon": 122.55, "name": "Vessel-015"},
  {"lat": -1.20, "lon": 104.35, "name": "Vessel-016"},
  {"lat": -4.85, "lon": 113.28, "name": "Vessel-017"},
  {"lat": -6.25, "lon": 110.25, "name": "Vessel-018"},
  {"lat": 2.85, "lon": 112.45, "name": "Vessel-019"},
  {"lat": 7.12, "lon": 117.65, "name": "Vessel-020"},
  {"lat": 11.05, "lon": 125.12, "name": "Vessel-021"},
  {"lat": 14.45, "lon": 121.85, "name": "Vessel-022"},
  {"lat": 1.55, "lon": 102.45, "name": "Vessel-023"},
  {"lat": 2.15, "lon": 101.85, "name": "Vessel-024"},
  {"lat": 5.22, "lon": 95.28, "name": "Vessel-025"},
  {"lat": 5.75, "lon": 97.12, "name": "Vessel-026"},
  {"lat": 0.75, "lon": 105.45, "name": "Vessel-027"},
  {"lat": 2.95, "lon": 108.32, "name": "Vessel-028"},
  {"lat": -0.85, "lon": 109.45, "name": "Vessel-029"},
  {"lat": -3.25, "lon": 114.12, "name": "Vessel-030"},
  {"lat": 6.55, "lon": 96.28, "name": "Vessel-031"},
  {"lat": 7.85, "lon": 94.82, "name": "Vessel-032"},
  {"lat": 9.15, "lon": 94.25, "name": "Vessel-033"},
  {"lat": 11.65, "lon": 110.25, "name": "Vessel-034"},
  {"lat": 9.25, "lon": 112.55, "name": "Vessel-035"},
  {"lat": 10.35, "lon": 115.35, "name": "Vessel-036"},
  {"lat": 12.35, "lon": 118.25, "name": "Vessel-037"},
  {"lat": 13.15, "lon": 119.45, "name": "Vessel-038"},
  {"lat": 14.95, "lon": 120.15, "name": "Vessel-039"},
  {"lat": 15.55, "lon": 121.25, "name": "Vessel-040"},
  {"lat": 16.05, "lon": 122.75, "name": "Vessel-041"},
  {"lat": 18.25, "lon": 120.45, "name": "Vessel-042"},
  {"lat": 4.15, "lon": 122.15, "name": "Vessel-043"},
  {"lat": 5.85, "lon": 121.45, "name": "Vessel-044"},
  {"lat": 7.25, "lon": 120.15, "name": "Vessel-045"},
  {"lat": 8.85, "lon": 118.85, "name": "Vessel-046"},
  {"lat": 9.75, "lon": 117.55, "name": "Vessel-047"},
  {"lat": 11.15, "lon": 116.35, "name": "Vessel-048"},
  {"lat": -2.15, "lon": 106.15, "name": "Vessel-049"},
  {"lat": -4.45, "lon": 107.25, "name": "Vessel-050"},
  {"lat": -5.25, "lon": 109.15, "name": "Vessel-051"},
  {"lat": -2.85, "lon": 112.35, "name": "Vessel-052"},
  {"lat": -1.15, "lon": 113.85, "name": "Vessel-053"},
  {"lat": 0.25, "lon": 115.45, "name": "Vessel-054"},
  {"lat": 1.35, "lon": 117.25, "name": "Vessel-055"},
  {"lat": 2.25, "lon": 119.05, "name": "Vessel-056"},
  {"lat": 3.35, "lon": 120.45, "name": "Vessel-057"},
  {"lat": 4.25, "lon": 121.95, "name": "Vessel-058"},
  {"lat": 6.15, "lon": 123.25, "name": "Vessel-059"},
  {"lat": 7.25, "lon": 124.75, "name": "Vessel-060"},
  {"lat": 8.25, "lon": 126.15, "name": "Vessel-061"},
  {"lat": 9.15, "lon": 127.25, "name": "Vessel-062"},
  {"lat": 10.05, "lon": 128.35, "name": "Vessel-063"},
  {"lat": 11.25, "lon": 129.15, "name": "Vessel-064"},
  {"lat": 12.25, "lon": 130.45, "name": "Vessel-065"},
  {"lat": 13.25, "lon": 131.25, "name": "Vessel-066"},
  {"lat": -0.55, "lon": 119.45, "name": "Vessel-067"},
  {"lat": -1.75, "lon": 120.35, "name": "Vessel-068"},
  {"lat": -3.25, "lon": 121.85, "name": "Vessel-069"},
  {"lat": -4.15, "lon": 123.45, "name": "Vessel-070"},
  {"lat": -5.25, "lon": 124.75, "name": "Vessel-071"},
  {"lat": -6.35, "lon": 125.85, "name": "Vessel-072"},
  {"lat": -7.25, "lon": 126.35, "name": "Vessel-073"},
  {"lat": -8.15, "lon": 127.25, "name": "Vessel-074"},
  {"lat": -9.25, "lon": 128.35, "name": "Vessel-075"},
  {"lat": -3.45, "lon": 108.25, "name": "Vessel-076"},
  {"lat": -2.15, "lon": 107.15, "name": "Vessel-077"},
  {"lat": -1.25, "lon": 106.05, "name": "Vessel-078"},
  {"lat": 0.55, "lon": 105.15, "name": "Vessel-079"},
  {"lat": 1.25, "lon": 104.35, "name": "Vessel-080"},
  {"lat": 2.15, "lon": 103.45, "name": "Vessel-081"},
  {"lat": 3.25, "lon": 102.35, "name": "Vessel-082"},
  {"lat": 4.25, "lon": 101.25, "name": "Vessel-083"},
  {"lat": 5.35, "lon": 100.15, "name": "Vessel-084"},
  {"lat": 6.25, "lon": 99.25, "name": "Vessel-085"},
  {"lat": 7.15, "lon": 98.35, "name": "Vessel-086"},
  {"lat": 8.25, "lon": 97.45, "name": "Vessel-087"},
  {"lat": 9.35, "lon": 96.55, "name": "Vessel-088"},
  {"lat": 10.15, "lon": 95.65, "name": "Vessel-089"},
  {"lat": 11.25, "lon": 94.75, "name": "Vessel-090"},
  {"lat": 12.35, "lon": 93.85, "name": "Vessel-091"},
  {"lat": 13.45, "lon": 92.95, "name": "Vessel-092"},
  {"lat": 14.25, "lon": 92.15, "name": "Vessel-093"},
  {"lat": 15.35, "lon": 91.25, "name": "Vessel-094"},
  {"lat": 16.25, "lon": 90.35, "name": "Vessel-095"},
  {"lat": 17.15, "lon": 89.45, "name": "Vessel-096"},
  {"lat": 18.05, "lon": 88.55, "name": "Vessel-097"},
  {"lat": 19.15, "lon": 87.65, "name": "Vessel-098"},
  {"lat": 20.25, "lon": 86.75, "name": "Vessel-099"},
  {"lat": 21.15, "lon": 85.85, "name": "Vessel-100"}
]


# ----------------------------
# Fast grid A*
# ----------------------------
def build_weight_grid(rmin, rmax, cmin, cmax, dynamic_ships=None, buffer_cells=1):
    Rn, Cn = rmax-rmin+1, cmax-cmin+1
    grid = [[1.0 for _ in range(Cn)] for _ in range(Rn)]
    for r in range(Rn):
        for c in range(Cn):
            lat, lon = grid_to_latlon(r+rmin, c+cmin)
            pt = Point(lon, lat)
            if OBSTACLES_UNION.contains(pt):
                grid[r][c] = 1e9
    for rock in ROCKS:
        rr, cc = latlon_to_grid(rock["lat"], rock["lon"])
        if rmin <= rr <= rmax and cmin <= cc <= cmax:
            grid[rr-rmin][cc-cmin] = 1e9
    if dynamic_ships:
        for s in dynamic_ships:
            rr, cc = latlon_to_grid(s["lat"], s["lon"])
            if rmin <= rr <= rmax and cmin <= cc <= cmax:
                grid[rr-rmin][cc-cmin] = max(grid[rr-rmin][cc-cmin], 50.0)
    return grid, Rn, Cn

def neighbors_sub(cell, Rn, Cn):
    r, c = cell
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        if 0<=nr<Rn and 0<=nc<Cn:
            yield (nr,nc)

def weighted_a_star_sub(start_latlon, end_latlon, grid, rmin, cmin, Rn, Cn):
    s_r, s_c = latlon_to_grid(*start_latlon)
    e_r, e_c = latlon_to_grid(*end_latlon)
    s, e = (s_r-rmin, s_c-cmin), (e_r-rmin, e_c-cmin)
    if not (0<=s[0]<Rn and 0<=s[1]<Cn and 0<=e[0]<Rn and 0<=e[1]<Cn):
        return None
    if grid[s[0]][s[1]]>=1e9: grid[s[0]][s[1]]=1.0
    if grid[e[0]][e[1]]>=1e9: grid[e[0]][e[1]]=1.0

    open_set = [(0.0, s)]
    g_score = {s:0.0}
    came_from = {}

    def heuristic(a,b):
        lat1, lon1 = grid_to_latlon(a[0]+rmin,a[1]+cmin)
        lat2, lon2 = grid_to_latlon(b[0]+rmin,b[1]+cmin)
        return haversine_nm(lat1, lon1, lat2, lon2)

    while open_set:
        _, current = heapq.heappop(open_set)
        if current==e:
            path=[current]
            while current in came_from:
                current=came_from[current]
                path.append(current)
            path.reverse()
            return [grid_to_latlon(p[0]+rmin,p[1]+cmin) for p in path]
        for neigh in neighbors_sub(current,Rn,Cn):
            w = grid[neigh[0]][neigh[1]]
            if w>=1e9: continue
            tentative_g = g_score[current]+heuristic(current, neigh)*w
            if tentative_g < g_score.get(neigh,float("inf")):
                came_from[neigh] = current
                g_score[neigh] = tentative_g
                heapq.heappush(open_set,(tentative_g+heuristic(neigh,e),neigh))
    return None

# ----------------------------
# FastAPI App
# ----------------------------
app = FastAPI(title="RouteUrSea - Integrated Backend")

# Mount static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ----------------------------
# Web pages routing
# ----------------------------
@app.get("/")
def serve_home():
    return FileResponse(STATIC_DIR / "home.html")

@app.get("/emissions")
def serve_emissions():
    return FileResponse(STATIC_DIR / "emissions.html")

@app.get("/route")
def serve_route_selection():
    return FileResponse(TEMPLATE_DIR / "route_selection.html")

# ----------------------------
# API - Ports
# ----------------------------
@app.get("/api/ports")
def api_ports():
    return JSONResponse(PORTS)

# ----------------------------
# API - Optimize Route
# ----------------------------
class RouteRequest(BaseModel):
    origin: str
    destination: str

@app.post("/api/optimize-route")
def api_optimize(req: RouteRequest):
    origin = next((p for p in PORTS if req.origin.lower() in p["name"].lower()), None)
    dest = next((p for p in PORTS if req.destination.lower() in p["name"].lower()), None)
    if not origin or not dest:
        raise HTTPException(status_code=400, detail="Port not found")

    ships = get_ships_near_area(**SEA_BOUNDS)

    lat_min = min(origin["lat"], dest["lat"])-3
    lat_max = max(origin["lat"], dest["lat"])+3
    lon_min = min(origin["lon"], dest["lon"])-3
    lon_max = max(origin["lon"], dest["lon"])+3
    rmin, cmin = latlon_to_grid(lat_min, lon_min)
    rmax, cmax = latlon_to_grid(lat_max, lon_max)

    grid, Rn, Cn = build_weight_grid(rmin,rmax,cmin,cmax,dynamic_ships=ships)

    path_main = weighted_a_star_sub((origin["lat"], origin["lon"]),
                                    (dest["lat"], dest["lon"]),
                                    grid, rmin, cmin, Rn, Cn)
    if not path_main:
        raise HTTPException(status_code=500, detail="No feasible route")

    alt_grid = [row[:] for row in grid]
    for lat, lon in path_main[len(path_main)//3:2*len(path_main)//3]:
        rr, cc = latlon_to_grid(lat, lon)
        if rmin<=rr<=rmax and cmin<=cc<=cmax:
            alt_grid[rr-rmin][cc-cmin] = max(alt_grid[rr-rmin][cc-cmin], 200.0)

    path_alt = weighted_a_star_sub((origin["lat"], origin["lon"]),
                                   (dest["lat"], dest["lon"]),
                                   alt_grid, rmin, cmin, Rn, Cn)

    rocks_features = [{"type":"Feature","properties":{"name":r["name"]},
                       "geometry":{"type":"Point","coordinates":[r["lon"],r["lat"]]}} for r in ROCKS]

    ships_features = [{"type":"Feature","properties":{"name":s["name"]},
                       "geometry":{"type":"Point","coordinates":[s["lon"],s["lat"]]}} for s in ships]

    return {
        "main_route":[{"lat": round(p[0],6), "lon": round(p[1],6)} for p in path_main],
        "alt_route":[{"lat": round(p[0],6), "lon": round(p[1],6)} for p in path_alt] if path_alt else [],
        "obstacles":{
            "islands": ALL_ISLAND_FEATURES,
            "rocks": rocks_features,
            "ships": ships_features
        }
    }

# ----------------------------
# API - Weather
# ----------------------------
@app.get("/weather")
def get_weather(lat: float, lon: float):
    forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,windspeed_10m,weathercode,visibility,precipitation,cloudcover&timezone=auto"
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wave_direction,wave_period&timezone=auto"

    forecast_res = requests.get(forecast_url).json()
    marine_res = requests.get(marine_url).json()

    merged_data = []
    if "hourly" in forecast_res and "hourly" in marine_res:
        times = forecast_res["hourly"]["time"]
        for i, t in enumerate(times):
            merged_data.append({
                "time": t,
                "temperature": forecast_res["hourly"]["temperature_2m"][i],
                "windspeed": forecast_res["hourly"]["windspeed_10m"][i],
                "weathercode": forecast_res["hourly"]["weathercode"][i],
                "visibility": forecast_res["hourly"]["visibility"][i],
                "precipitation": forecast_res["hourly"]["precipitation"][i],
                "cloudcover": forecast_res["hourly"]["cloudcover"][i],
                "wave_height": marine_res["hourly"]["wave_height"][i],
                "wave_direction": marine_res["hourly"]["wave_direction"][i],
                "wave_period": marine_res["hourly"]["wave_period"][i],
            })
    return {"location":{"lat":lat,"lon":lon},"hourly":merged_data}

# ----------------------------
# API - Emissions calculation
# ----------------------------
class CalcRequest(BaseModel):
    vessel_type: str
    speed_knots: float
    distance_nm: float
    fuel_type: str
    weather_resistance: Optional[float] = 1.0

BASE_RATES = {"small_coastal":{"base_rate":0.25,"nominal_speed":10.0},
              "medium_cargo":{"base_rate":0.9,"nominal_speed":12.0},
              "large_container":{"base_rate":2.8,"nominal_speed":18.0}}

EMISSION_FACTORS = {"HFO":3.114,"MDO":3.206,"LNG":2.75}
ECO_BADGES = {"carbon_cutter":20.0,"low_emission_rider":10.0}

def compute_fuel(base_rate, nominal_speed, actual_speed, distance_nm, weather_resistance):
    speed_factor = max(actual_speed/nominal_speed,0.5) if nominal_speed>0 else 1.0
    return base_rate*distance_nm*speed_factor*weather_resistance

def compute_emissions(fuel_liters, fuel_type):
    ef = EMISSION_FACTORS.get(fuel_type, EMISSION_FACTORS["HFO"])
    return fuel_liters*ef

def get_badge(improvement_pct):
    if improvement_pct >= ECO_BADGES["carbon_cutter"]:
        return "🌱 Carbon Cutter"
    elif improvement_pct >= ECO_BADGES["low_emission_rider"]:
        return "💨 Low Emission Rider"
    else:
        return "🚢 Standard Mode"

def check_marpol_limits(vessel_type: str, fuel_type: str, co2_kg: float, speed_knots: float):
    compliance = {}
    if (vessel_type=="small_coastal" and co2_kg>2500) or \
       (vessel_type=="medium_cargo" and co2_kg>6000) or \
       (vessel_type=="large_container" and co2_kg>20000):
        compliance["annex_vi_Air_Pollution"]={"message":"❌ Exceeds emission threshold (Annex VI)","passed":False}
    else:
        compliance["annex_vi_Air_Pollution"]={"message":"✅ Within emission limits (Annex VI)","passed":True}

    if vessel_type=="small_coastal" and fuel_type=="HFO":
        compliance["annex_i"]={"message":"⚠️ HFO restricted for small coastal vessels (Annex I)","passed":False}
    else:
        compliance["annex_i"]={"message":"✅ Fuel use compliant (Annex I)","passed":True}

    if (vessel_type=="small_coastal" and speed_knots>9) or \
       (vessel_type=="medium_cargo" and speed_knots>12) or \
       (vessel_type=="large_container" and speed_knots>18):
        compliance["annex_vi_eco_speed"]={"message":"⚠️ Above eco-speed, may increase emissions (Annex VI)","passed":False}
    else:
        compliance["annex_vi_eco_speed"]={"message":"✅ Speed within eco-recommendations (Annex VI)","passed":True}
    return compliance

@app.post("/api/calculate")
def calculate(req: CalcRequest):
    vt = req.vessel_type if req.vessel_type in BASE_RATES else "medium_cargo"
    params = BASE_RATES[vt]
    base_rate, nominal_speed = params["base_rate"], params["nominal_speed"]

    requested_speed = max(req.speed_knots,1.0)
    eco_speed = max(requested_speed-2.0,4.0)
    balanced_speed = max(min(nominal_speed,requested_speed),4.0)
    fastest_speed = min(requested_speed+2.0,30.0)

    scenarios = {}
    for label, speed in [("eco",eco_speed),("balanced",balanced_speed),("fastest",fastest_speed)]:
        fuel = compute_fuel(base_rate,nominal_speed,speed,req.distance_nm,req.weather_resistance)
        co2 = compute_emissions(fuel, req.fuel_type)
        eta = round(req.distance_nm/speed,2) if speed>0 else None
        scenarios[label] = {"speed_knots":round(speed,2),"fuel_liters":round(fuel,2),
                            "co2_kg":round(co2,2),"eta_hours":eta,
                            "marpol_compliance":check_marpol_limits(vessel_type=vt,fuel_type=req.fuel_type,co2_kg=co2,speed_knots=speed)}
    baseline_fuel = compute_fuel(base_rate,nominal_speed,nominal_speed,req.distance_nm,1.0)
    baseline_co2 = compute_emissions(baseline_fuel, req.fuel_type)
    eco_improvement = round(((baseline_co2-scenarios["eco"]["co2_kg"])/baseline_co2)*100,2) if baseline_co2>0 else 0.0
    badge = get_badge(eco_improvement)

    return {"vessel_type":vt,"distance_nm":req.distance_nm,"requested_speed":requested_speed,
            "fuel_type":req.fuel_type,"weather_resistance":req.weather_resistance,
            "baseline_co2_kg":round(baseline_co2,2),"eco_improvement_pct":eco_improvement,
            "eco_rating_badge":badge,"scenarios":scenarios}

