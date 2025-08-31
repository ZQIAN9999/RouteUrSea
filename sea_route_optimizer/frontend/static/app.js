const API_URL = "/api/calculate";
const form = document.getElementById("calc-form");
const summary = document.getElementById("summary");
const comparisonTable = document.getElementById("comparison-table");
const historyDiv = document.getElementById("history");

const simSpeed = document.getElementById("sim-speed");
const simFuel = document.getElementById("sim-fuel");
const simWeather = document.getElementById("sim-weather");
const simRun = document.getElementById("sim-run");

const exportBtn = document.getElementById("export-json");
const clearBtn = document.getElementById("clear-history");
const useModule1Btn = document.getElementById("use-module1");

function readForm() {
  return {
    vessel_type: document.getElementById("vessel_type").value,
    speed_knots: parseFloat(document.getElementById("speed_knots").value),
    distance_nm: parseFloat(document.getElementById("distance_nm").value),
    fuel_type: document.getElementById("fuel_type").value,
    weather_resistance: parseFloat(document.getElementById("weather_res").value) || 1.0
  };
}

async function callApi(payload) {
  const res = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  return await res.json();
}

function renderSummary(resp) {
  summary.innerHTML = "";

  // Create the Baseline CO₂ card
  const s = document.createElement("div");
  s.className = "summary-card blue";

  // Create the badge element with dynamic class
  const badge = document.createElement("div");
  const badgeClass = resp.eco_rating_badge
    .replace(/[^\w\s]/g, '') // remove emojis or special chars
    .trim()
    .replace(/\s+/g, '-')
    .toLowerCase(); // e.g. "Carbon Cutter" → "carbon-cutter"
  badge.className = `badge ${badgeClass}`;
  badge.textContent = resp.eco_rating_badge;

  // Build the inner HTML
  s.innerHTML = `<h4>Baseline CO₂ (kg)</h4>
                 <p>${resp.baseline_co2_kg}</p>
                 <small>Eco improvement: <strong>${resp.eco_improvement_pct}%</strong>&nbsp;&nbsp;</small>`;
  s.appendChild(badge);
  summary.appendChild(s);

  // Create the Speed / Distance card
  const a = document.createElement("div");
  a.className = "summary-card";
  a.innerHTML = `<h4>Requested Speed / Distance</h4>
                 <p>${resp.requested_speed} knots / ${resp.distance_nm} NM</p>`;
  summary.appendChild(a);
}

function renderComparison(resp) {
  const sc = resp.scenarios;
  let html = `<table><thead><tr><th>Scenario</th><th>Speed (kn)</th><th>Fuel (L)</th><th>CO₂ (kg)</th><th>ETA (h)</th></tr></thead><tbody>`;
  for (const k of ["eco","balanced","fastest"]) {
    const it = sc[k];
    html += `<tr>
      <td style="text-transform:capitalize">${k}</td>
      <td>${it.speed_knots}</td>
      <td>${it.fuel_liters}</td>
      <td>${it.co2_kg}</td>
      <td>${it.eta_hours}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  comparisonTable.innerHTML = html;
}

function renderMarpol(resp) {
  const container = document.getElementById("marpol-results");
  const summaryDiv = document.getElementById("marpol-summary");
  container.innerHTML = "";
  summaryDiv.innerHTML = ""; // reset

  let anyFail = false;

  for (const scenario of ["eco", "balanced", "fastest"]) {
    const data = resp.scenarios[scenario];
    const div = document.createElement("div");
    div.className = "summary-card";

    // Filter failed compliance
    const failures = Object.entries(data.marpol_compliance)
      .filter(([annex, c]) => !c.passed);

    if (failures.length > 0) anyFail = true;

    let html = `<h4>${scenario.charAt(0).toUpperCase() + scenario.slice(1)} Scenario MARPOL Compliance</h4>`;
    if (failures.length === 0) {
      html += `<p>✅ Approved — All MARPOL checks passed</p>`;
      div.style.backgroundColor = "#d4edda"; // light green
      div.style.color = "#155724";           // dark green
    } else {
      html += `<ul>`;
      failures.forEach(([annex, c]) => {
        let message = "";
        switch (annex) {
          case "annex_vi_Air_Pollution":
            message = `❌ CO₂ emissions exceed the limit (Annex VI)`;
            break;
          case "annex_v":
            message = `❌ Fails to follow garbage disposal rules (Annex V)`;
            break;
          case "annex_i":
            message = `❌ Fuel use not compliant (Annex I)`;
            break;
          case "annex_vi_eco_speed": {
            message = `❌ Speed exceeds eco-recommendation (Annex VI)`;
            break;
          }
          default:
            message = `❌ ${c.message}`;
        }

        html += `<li>${message}</li>`;
      });

      html += `</ul>`;
      div.style.backgroundColor = "#f8d7da"; // light red
      div.style.color = "#800612ff";           // dark red
    }

    div.innerHTML = html;
    container.appendChild(div);
  }

  // --- Render summary block ---
  if (anyFail) {
    summaryDiv.innerHTML = `<h4>Overall Compliance</h4><p>❌ Rejected — One or more scenarios fail MARPOL checks</p>`;
    summaryDiv.style.backgroundColor = "#f8d7da"; // red
    summaryDiv.style.color = "#721c24";
  } else {
    summaryDiv.innerHTML = `<h4>Overall Compliance</h4><p>✅ Approved — All scenarios pass MARPOL checks</p>`;
    summaryDiv.style.backgroundColor = "#d4edda"; // green
    summaryDiv.style.color = "#132e19ff";
  }
}


function saveToHistory(payload, resp) {
  const key = "routeursea_history";
  const item = {
    timestamp: new Date().toISOString(),
    input: payload,
    result: resp
  };
  const hist = JSON.parse(localStorage.getItem(key) || "[]");
  hist.unshift(item);
  localStorage.setItem(key, JSON.stringify(hist));
  renderHistory();
}

function renderHistory() {
  const key = "routeursea_history";
  const hist = JSON.parse(localStorage.getItem(key) || "[]");
  if (!hist.length) {
    historyDiv.innerHTML = "<p class='muted'>No history yet. Calculate a route to save results.</p>";
    return;
  }
  historyDiv.innerHTML = "";

  hist.slice(0, 10).forEach((h, idx) => {
    const el = document.createElement("div");
    el.className = "summary-card";

    // Check if any scenario failed in this history item
    let anyFail = false;
    for (const scenario of ["eco", "balanced", "fastest"]) {
      const data = h.result.scenarios[scenario];
      const failures = Object.values(data.marpol_compliance).filter(c => !c.passed);
      if (failures.length > 0) {
        anyFail = true;
        break;
      }
    }

    // Summary text and background color
    const statusText = anyFail ? "❌ Rejected" : "✅ Approved";
    const bgColor = anyFail ? "#f8d7da" : "#d4edda";
    const textColor = anyFail ? "#721c24" : "#155724";

    el.style.backgroundColor = bgColor;
    el.style.color = textColor;

    el.innerHTML = `
      <strong>${new Date(h.timestamp).toLocaleString()}</strong>
      <div>Vessel: ${h.input.vessel_type} • ${h.input.distance_nm} NM @ ${h.input.speed_knots} kn</div>
      <div class="muted">CO₂ (eco): ${h.result.scenarios.eco.co2_kg} kg | Baseline: ${h.result.baseline_co2_kg} kg</div>
      <div><strong>Compliance: ${statusText}</strong></div>
    `;

    historyDiv.appendChild(el);
  });
}


// Form submission
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = readForm();
  if (!payload.distance_nm || payload.distance_nm <= 0) return alert("Set a valid distance");
  const resp = await callApi(payload);
  renderSummary(resp);
  renderComparison(resp);
  renderMarpol(resp);
  saveToHistory(payload, resp);
});

// Simulator run
simRun.addEventListener("click", async () => {
  const orig = readForm();
  const payload = {
    ...orig,
    speed_knots: parseFloat(simSpeed.value),
    fuel_type: simFuel.value,
    weather_resistance: parseFloat(simWeather.value)
  };
  const resp = await callApi(payload);
  renderSummary(resp);
  renderComparison(resp);
});

// Export history
exportBtn.addEventListener("click", () => {
  const key = "routeursea_history";
  const hist = localStorage.getItem(key);
  if (!hist) return alert("No history to export");
  const blob = new Blob([hist], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "routeursea_history.json";
  a.click();
  URL.revokeObjectURL(url);
});

// Clear history
clearBtn.addEventListener("click", () => {
  if (!confirm("Clear history?")) return;
  localStorage.removeItem("routeursea_history");
  renderHistory();
});

// Load inputs from Module 1
useModule1Btn.addEventListener("click", () => {
  try {
    const m = JSON.parse(localStorage.getItem("module1_inputs") || "null");
    if (!m) return alert("No Module 1 inputs found in localStorage (key: module1_inputs)");
    document.getElementById("vessel_type").value = m.vessel_type || "medium_cargo";
    document.getElementById("speed_knots").value = m.speed_knots || 12;
    document.getElementById("distance_nm").value = m.distance_nm || 100;
    document.getElementById("fuel_type").value = m.fuel_type || "MDO";
    document.getElementById("weather_res").value = m.weather_resistance || 1.0;
    alert("Loaded inputs from Module 1 (localStorage).");
  } catch (err) {
    alert("Failed to load Module 1 inputs: " + err.message);
  }
});

// Init
renderHistory();

// Weather JavaScript
// Map Open-Meteo weather codes to icons
const weatherIcons = {
    0: "☀️",   // Clear sky
    1: "🌤️",   // Mainly clear
    2: "⛅",    // Partly cloudy
    3: "☁️",    // Overcast
    45: "🌫️",  // Fog
    48: "🌫️",  // Depositing rime fog
    51: "🌦️",  // Light drizzle
    53: "🌦️",  // Moderate drizzle
    55: "🌦️",  // Dense drizzle
    61: "🌧️",  // Slight rain
    63: "🌧️",  // Moderate rain
    65: "🌧️",  // Heavy rain
    71: "🌨️",  // Slight snow
    73: "🌨️",  // Moderate snow
    75: "❄️",  // Heavy snow
    77: "❄️",  // Snow grains
    80: "🌦️",  // Rain showers: slight
    81: "🌧️",  // Rain showers: moderate
    82: "🌧️",  // Rain showers: violent
    85: "🌨️",  // Snow showers: slight
    86: "🌨️",  // Snow showers: heavy
    95: "⛈️",  // Thunderstorm: slight or moderate
    96: "⛈️",  // Thunderstorm with slight hail
    99: "⛈️"   // Thunderstorm with heavy hail
};

document.getElementById("weather-btn").addEventListener("click", async () => {
  const sea = document.getElementById("sea_area").value.split(",");
  const lat = sea[0], lon = sea[1];
  const date = document.getElementById("forecast_date").value;

  let url = `/weather?lat=${lat}&lon=${lon}`;
  if (date) url += `&date=${date}`;

  const res = await fetch(url);
  const data = await res.json();

  const weatherDiv = document.getElementById("weather-results");
  weatherDiv.innerHTML = "";

  if (data.error) {
    weatherDiv.innerHTML = `<p class="error">${data.error}</p>`;
    return;
  }

  // Build the table
  let tableHTML = `
    <div class="weather-output">
      <h3>Weather Forecast (Lat: ${data.location.lat}, Lon: ${data.location.lon})</h3>
      <table class="weather-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Weather</th>
            <th>Temp (°C)</th>
            <th>Wind (m/s)</th>
            <th>Visibility (m)</th>
            <th>Precip (mm)</th>
            <th>Cloud (%)</th>
            <th>Wave Height (m)</th>
            <th>Wave Dir (°)</th>
            <th>Wave Period (s)</th>
          </tr>
        </thead>
        <tbody>
  `;

  for (let i = 0; i < data.hourly.length; i++) {
    const row = data.hourly[i];
    const icon = weatherIcons[row.weathercode] || "❓";

    tableHTML += `
      <tr>
        <td>${row.time}</td>
        <td>${icon}</td>
        <td>${row.temperature}</td>
        <td>${row.windspeed}</td>
        <td>${row.visibility}</td>
        <td>${row.precipitation}</td>
        <td>${row.cloudcover}</td>
        <td>${row.wave_height}</td>
        <td>${row.wave_direction}</td>
        <td>${row.wave_period}</td>
      </tr>
    `;
  }

  tableHTML += `
        </tbody>
      </table>
    </div>
  `;

  weatherDiv.innerHTML = tableHTML;
});

// Disable past dates
const today = new Date().toISOString().split("T")[0];
document.getElementById("forecast_date").setAttribute("min", today);