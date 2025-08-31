# backend/app.py
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
from flask_cors import CORS
from pathlib import Path
import os, json, math, heapq, logging
from shapely.geometry import shape, Point
from shapely.ops import unary_union

# ---------- App root / data paths ----------
APP_ROOT = Path(__file__).parent
DATA_DIR = APP_ROOT / "data"
TEMPLATE_DIR = APP_ROOT.parent / "frontend" / "templates"
STATIC_DIR = APP_ROOT.parent / "frontend" / "static"

PORTS_FILE = DATA_DIR / "ports.geojson"
ISLANDS_FILE = DATA_DIR / "islands.geojson"
LAND_FILE = DATA_DIR / "land.geojson"
ROCKS_FILE = DATA_DIR / "rocks.geojson"

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
CORS(app)
logging.basicConfig(level=logging.INFO)

# ---------- Constants ----------
SEA_BOUNDS = {"lat_min": -15.0, "lat_max": 25.0, "lon_min": 90.0, "lon_max": 140.0}
GRID_RES = 0.2   # 每格大约20km，速度大幅提升
R_MAX = int((SEA_BOUNDS["lat_max"] - SEA_BOUNDS["lat_min"]) / GRID_RES)
C_MAX = int((SEA_BOUNDS["lon_max"] - SEA_BOUNDS["lon_min"]) / GRID_RES)

# ---------- Helpers ----------
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

# ---------- Load static data ----------
ISLANDS = load_json(ISLANDS_FILE) or {"type":"FeatureCollection","features":[]}
LAND = load_json(LAND_FILE) or {"type":"FeatureCollection","features":[]}
ROCKS_RAW = load_json(ROCKS_FILE) or {"elements":[]}
PORTS_RAW = load_json(PORTS_FILE) or {"elements":[]}

ROCKS = []
for e in ROCKS_RAW.get("elements", []):
    if e.get("type") == "node" and "lat" in e and "lon" in e:
        ROCKS.append({"lat": e["lat"], "lon": e["lon"], "name": e.get("tags", {}).get("name","rock")})

PORTS = []
if isinstance(PORTS_RAW, dict) and "elements" in PORTS_RAW:
    for e in PORTS_RAW.get("elements", []):
        if e.get("type") == "node":
            PORTS.append({"lat": e["lat"], "lon": e["lon"], "name": e.get("tags", {}).get("name","port")})
elif isinstance(PORTS_RAW, dict) and PORTS_RAW.get("type") == "FeatureCollection":
    for feat in PORTS_RAW.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") == "Point":
            lon, lat = geom["coordinates"]
            PORTS.append({"lat": lat, "lon": lon, "name": feat.get("properties", {}).get("name","port")})

# unify obstacles
ALL_ISLAND_FEATURES = []
if ISLANDS.get("type") == "FeatureCollection":
    ALL_ISLAND_FEATURES += ISLANDS.get("features", [])
if LAND.get("type") == "FeatureCollection":
    ALL_ISLAND_FEATURES += LAND.get("features", [])

OBSTACLES_UNION = unary_union([shape(f["geometry"]) for f in ALL_ISLAND_FEATURES if f.get("geometry")])

# ---------- Mock AIS ----------
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



# ---------- Fast grid A* ----------
def build_weight_grid(rmin, rmax, cmin, cmax, dynamic_ships=None, buffer_cells=1):
    Rn = rmax - rmin + 1
    Cn = cmax - cmin + 1
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
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]: # 4邻居更快
        nr, nc = r + dr, c + dc
        if 0 <= nr < Rn and 0 <= nc < Cn:
            yield (nr, nc)

def weighted_a_star_sub(start_latlon, end_latlon, grid, rmin, cmin, Rn, Cn):
    s_r, s_c = latlon_to_grid(*start_latlon)
    e_r, e_c = latlon_to_grid(*end_latlon)
    s = (s_r - rmin, s_c - cmin)
    e = (e_r - rmin, e_c - cmin)
    if not (0 <= s[0] < Rn and 0 <= s[1] < Cn and 0 <= e[0] < Rn and 0 <= e[1] < Cn):
        return None
    if grid[s[0]][s[1]] >= 1e9: grid[s[0]][s[1]] = 1.0
    if grid[e[0]][e[1]] >= 1e9: grid[e[0]][e[1]] = 1.0

    open_set = [(0.0, s)]
    g_score = {s: 0.0}
    came_from = {}

    def heuristic(a, b):
        lat1, lon1 = grid_to_latlon(a[0]+rmin, a[1]+cmin)
        lat2, lon2 = grid_to_latlon(b[0]+rmin, b[1]+cmin)
        return haversine_nm(lat1, lon1, lat2, lon2)

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == e:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return [grid_to_latlon(p[0]+rmin, p[1]+cmin) for p in path]

        for neigh in neighbors_sub(current, Rn, Cn):
            w = grid[neigh[0]][neigh[1]]
            if w >= 1e9:
                continue
            tentative_g = g_score[current] + heuristic(current, neigh)*w
            if tentative_g < g_score.get(neigh, float("inf")):
                came_from[neigh] = current
                g_score[neigh] = tentative_g
                f = tentative_g + heuristic(neigh, e)
                heapq.heappush(open_set, (f, neigh))
    return None

# ---------- API ----------
@app.route("/api/ports")
def api_ports():
    return jsonify(PORTS)

@app.route("/api/optimize-route", methods=["POST"])
def api_optimize():
    payload = request.get_json() or {}
    origin = next((p for p in PORTS if payload.get("origin","").lower() in p["name"].lower()), None)
    dest = next((p for p in PORTS if payload.get("destination","").lower() in p["name"].lower()), None)
    if not origin or not dest:
        return jsonify({"error":"port not found"}), 400

    ships = get_ships_near_area(**SEA_BOUNDS)

    # 构造局部网格
    lat_min = min(origin["lat"], dest["lat"]) - 3
    lat_max = max(origin["lat"], dest["lat"]) + 3
    lon_min = min(origin["lon"], dest["lon"]) - 3
    lon_max = max(origin["lon"], dest["lon"]) + 3
    rmin, cmin = latlon_to_grid(lat_min, lon_min)
    rmax, cmax = latlon_to_grid(lat_max, lon_max)

    grid, Rn, Cn = build_weight_grid(rmin, rmax, cmin, cmax, dynamic_ships=ships)

    # 主路线
    path_main = weighted_a_star_sub(
        (origin["lat"], origin["lon"]),
        (dest["lat"], dest["lon"]),
        grid, rmin, cmin, Rn, Cn
    )
    if not path_main:
        return jsonify({"error":"No feasible route"}), 500

    # 构造备选路线：在主路径上加“虚拟障碍”
    alt_grid = [row[:] for row in grid]  # 深拷贝
    for (lat, lon) in path_main[len(path_main)//3 : 2*len(path_main)//3]:
        rr, cc = latlon_to_grid(lat, lon)
        if rmin <= rr <= rmax and cmin <= cc <= cmax:
            alt_grid[rr-rmin][cc-cmin] = max(alt_grid[rr-rmin][cc-cmin], 200.0)  # 增加代价

    path_alt = weighted_a_star_sub(
        (origin["lat"], origin["lon"]),
        (dest["lat"], dest["lon"]),
        alt_grid, rmin, cmin, Rn, Cn
    )

    # 转换障碍物
    rocks_features = [
        {"type":"Feature","properties":{"name":r["name"]},
         "geometry":{"type":"Point","coordinates":[r["lon"],r["lat"]]}}
        for r in ROCKS
    ]
    ships_features = [
        {"type":"Feature","properties":{"name":s["name"]},
         "geometry":{"type":"Point","coordinates":[s["lon"],s["lat"]]}}
        for s in ships
    ]

    return jsonify({
        "main_route": [{"lat": round(p[0],6), "lon": round(p[1],6)} for p in path_main],
        "alt_route": (
            [{"lat": round(p[0],6), "lon": round(p[1],6)} for p in path_alt]
            if path_alt else []
        ),
        "obstacles": {
            "islands": ALL_ISLAND_FEATURES,
            "rocks": rocks_features,
            "ships": ships_features
        }
    })


@app.route("/data/<path:filename>")
def serve_data(filename):
    file_path = DATA_DIR / filename
    if not file_path.exists():
        abort(404)
    return send_from_directory(DATA_DIR, filename)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    logging.info("Starting backend on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
