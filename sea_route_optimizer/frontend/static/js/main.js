// frontend/static/js/main.js
const map = L.map('map').setView([5, 110], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18}).addTo(map);

const originSelect=document.getElementById('origin');
const destSelect=document.getElementById('destination');
const statusDiv=document.getElementById('status');

let baselineLayers = []; // background geojson layers
let dynamicLayers = [];  // route + obstacle layers we clear on each compute

function clearDynamic(){
  for(const l of dynamicLayers){ map.removeLayer(l); }
  dynamicLayers = [];
}

async function loadGeoJSON(url, options = {}, keepLayer = true){
  try{
    const res = await fetch(url);
    if(!res.ok) return null;
    const data = await res.json();
    const layer = L.geoJSON(data, options).addTo(map);
    if(keepLayer) baselineLayers.push(layer);
    return data;
  }catch(e){
    console.warn("loadGeoJSON failed", url, e);
    return null;
  }
}

async function loadPorts(){
  statusDiv.innerText = "Loading ports...";
  try {
    const res = await fetch('/api/ports');
    if(!res.ok) throw new Error("ports fetch failed");
    const ports = await res.json();
    window._ports = ports;
    originSelect.innerHTML = ""; destSelect.innerHTML = "";
    for(const p of ports){
      originSelect.add(new Option(p.name,p.name));
      destSelect.add(new Option(p.name,p.name));
    }
    // draw port markers
    const fc = { type:"FeatureCollection", features: ports.map(p=>({type:"Feature", properties:{name:p.name}, geometry:{type:"Point", coordinates:[p.lon,p.lat]}}))};
    const layer = L.geoJSON(fc, {
      pointToLayer: (f,latlng) => L.circleMarker(latlng, { radius:4, color:"#0a66ff", fillOpacity:0.9 }),
      onEachFeature: (f,layer)=>layer.bindPopup(f.properties.name)
    }).addTo(map);
    baselineLayers.push(layer);
    statusDiv.innerText = "Ports loaded";
    console.log("Loaded ports:", ports.length);
  } catch(err) {
    console.error(err);
    statusDiv.innerText = "Failed to load ports";
  }
}

function drawRoute(coords, opts){
  const latlngs = coords.map(p => [p.lat, p.lon]);
  const poly = L.polyline(latlngs, opts).addTo(map);
  dynamicLayers.push(poly);
  return poly;
}

function drawObstacles(obstacles){
  // islands
  if(obstacles && obstacles.islands){
    const islandsLayer = L.geoJSON({type:"FeatureCollection", features: obstacles.islands}, {
      style: { color:"#2e8b57", fillColor:"#2e8b57", fillOpacity:0.35, weight:1 },
      onEachFeature: (f, layer) => { if(f.properties?.name) layer.bindPopup(f.properties.name); }
    }).addTo(map);
    dynamicLayers.push(islandsLayer);
  }
  // rocks (with permanent label)
  if(obstacles && obstacles.rocks){
    const rocksLayer = L.geoJSON({type:"FeatureCollection", features: obstacles.rocks}, {
      pointToLayer: (f,latlng) => L.circleMarker(latlng, { radius:6, color:"red", fillColor:"red", fillOpacity:0.95, weight:1 }),
      onEachFeature: (f, layer) => {
        const name = f.properties?.name || "rock";
        layer.bindPopup(name);
        // show permanent label
        layer.bindTooltip(name, { permanent:true, direction:"right", className:"rock-label" });
      }
    }).addTo(map);
    dynamicLayers.push(rocksLayer);
  }
  // ships
  if(obstacles && obstacles.ships){
    const shipsLayer = L.geoJSON({type:"FeatureCollection", features: obstacles.ships}, {
      pointToLayer: (f,latlng) => L.circleMarker(latlng, { radius:5, color:"orange", fillOpacity:0.9 }),
      onEachFeature: (f, layer) => { if(f.properties?.name) layer.bindPopup(f.properties.name); }
    }).addTo(map);
    dynamicLayers.push(shipsLayer);
  }
}

// 在 map 上标注起点和终点（使用 Pin Point 图标）
function markPortsOnMap(origin, destination){
  if(!window._ports) return;
  const originPort = window._ports.find(p=>p.name === origin);
  const destPort = window._ports.find(p=>p.name === destination);

  // Leaflet 自带 pin 图标可以用 DivIcon 自定义
  function makePin(color, label){
    return L.divIcon({
      className: "custom-pin",
      html: `
        <div class="pin" style="background:${color}"></div>
        <div class="pin-label">${label}</div>
      `,
      iconSize: [30, 42], // pin 大小
      iconAnchor: [15, 42], // 底部尖尖对准经纬度
      popupAnchor: [0, -40]
    });
  }

  if(originPort){
    const m = L.marker([originPort.lat, originPort.lon], {
      icon: makePin("#0066ff", originPort.name) // 蓝色 pin
    }).addTo(map);
    dynamicLayers.push(m);
  }
  if(destPort){
    const m = L.marker([destPort.lat, destPort.lon], {
      icon: makePin("#0066ff", destPort.name) // 绿色 pin
    }).addTo(map);
    dynamicLayers.push(m);
  }
}


async function computeRoute(){
  const origin = originSelect.value, destination = destSelect.value;
  if(!origin || !destination){ alert("Select both ports"); return; }
  statusDiv.innerText = "Computing...";
  console.log("Compute request", { origin, destination });
  try{
    const res = await fetch('/api/optimize-route', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ origin, destination })
    });
    const data = await res.json();
    console.log("Server response", res.status, data);
    if(res.status !== 200){
      statusDiv.innerText = data.error || "Server error";
      return;
    }
    clearDynamic();
    // draw obstacles
    drawObstacles(data.obstacles);
    // draw routes
    if(data.main_route && data.main_route.length){
      drawRoute(data.main_route, { color:"#0066ff", weight:4, opacity:0.95 });
      map.fitBounds(data.main_route.map(p => [p.lat, p.lon]), { padding: [20,20] });
    } else {
      console.warn("No main_route returned");
    }
    if(data.alt_route && data.alt_route.length){
      drawRoute(data.alt_route, { color:"#ff7f50", weight:3, dashArray:"8,6" });
    }
    statusDiv.innerText = "Routes displayed";
  } catch(err){
    console.error("computeRoute error", err);
    statusDiv.innerText = "Error computing route";
  }
}

document.getElementById('compute').addEventListener('click', computeRoute);

// initialize
loadPorts();
// optionally pre-load background geojson files if present in /data
loadGeoJSON('/data/land.geojson', { style:{ color:"#444", weight:1, fillColor:"#ccc", fillOpacity:0.33 } }, true);
loadGeoJSON('/data/islands.geojson', { style:{ color:"#228B22", fillColor:"#32CD32", fillOpacity:0.5 } }, true);
// If rocks.geojson is Overpass format (elements) loading as GeoJSON may fail — we already request rocks via /api/optimize-route obstacles


function addLegendCard(){
  const card = L.control({position:'bottomright'});
  card.onAdd = function(){
    const div = L.DomUtil.create('div','legend-card');
    div.innerHTML = `
      <h4>Legend</h4>
      <div><span class="legend-color" style="background:#0066ff"></span>Main Route</div>
      <div><span class="legend-color" style="background:#ff7f50"></span>Alternative Route</div>
      <div><span class="legend-color" style="background:#32CD32"></span>Islands</div>
      <div><span class="legend-color" style="background:red"></span>Hazards</div>
      <div><span class="legend-color" style="background:#ffa500"></span>Ships</div>
      <div><span class="legend-color" style="background:#0066ff"></span>Origin Port (Pin)</div>
      <div><span class="legend-color" style="background:#0066ff"></span>Destination Port (Pin)</div>
    `;
    return div;
  };
  card.addTo(map);
}

addLegendCard();