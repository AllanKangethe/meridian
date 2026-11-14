
// Load events from the server and display them on the map and in the list
async function loadEvents() {
    const status = document.getElementById("search-status");
    try {
        const res = await fetch("/events");
        if (!res.ok) {
            status.textContent = `Couldn't load events (${res.status})`;
            return;
        }
        showEvents(await res.json());
    } catch (err) {
        status.textContent = "Couldn't reach the server";
    }
}

// Loads most recent events on page load (limit = 100)
loadEvents();

// Initialize the map
const map = L.map("map", {
    minZoom: 2,
    maxBounds: [[-85, -180], [85, 180]],
    maxBoundsViscosity: 1.0,
}).setView([20, 0], 2);

// Add OpenStreetMap tile layer
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
}).addTo(map);


// Create a layer group for markers
const markers = L.layerGroup().addTo(map);

const SEVERITY_COLORS = { low: "#4ade80", moderate: "#fbbf24", high: "#f87171" };

// [moderate starts at, high starts at] for each unit
const THRESHOLDS = {
    quake:   [4.5, 6],      // Richter-style: Mb, Ml, Mw, Mwb, Mwc, Mwr, Mi
    acres:   [1000, 10000], // wildfire size
    kts:     [64, 96],      // 64 = hurricane, 96 = major hurricane (Cat 3+)
    "nm^2":  [100, 1000],   // iceberg area
};

function severity(e) {
    if (e.magnitude == null) return "low"; 

    let unit = (e.magnitude_unit ?? "").toLowerCase();
    let value = e.magnitude;

    if (unit === "hectare") {        // convert to acres, then use acres cutoffs
        value *= 2.471;
        unit = "acres";
    }

    // USGS rows have no unit; all earthquake scales share one range
    const [mid, high] = THRESHOLDS[unit] ?? THRESHOLDS.quake;

    return value >= high ? "high" : value >= mid ? "moderate" : "low";
}

// Returns the radius of a marker based on its magnitude and severity level
function markerRadius(e, level) {
    if (e.event_type === "earthquake") 
        return 3 + (e.magnitude ?? 0) * 1.5;
    return { low: 5, moderate: 8, high: 12 }[level];   // fixed sizes for other units
}


// Draws events on the map as circle markers
function drawEvents(events) {
    markers.clearLayers();
    for (const e of events) {
        const level = severity(e);
        L.circleMarker([e.lat, e.lon], {
            radius: markerRadius(e, level),
            color: SEVERITY_COLORS[level],
            weight: 1,
            fillOpacity: 0.6,
        })
        .bindPopup(e.title)
        .addTo(markers);
    }
}

// Show events
function showEvents(events) {
    drawEvents(events);

    const list = document.getElementById("results");
    list.textContent = "";
    for (const e of events) {
        list.appendChild(renderEvent(e));
    }
    document.getElementById("search-status").textContent = `Showing Events (${events.length})`;
}

// Load events from the server and display them on the map and in the list
fetch("/events").then(res => res.json()).then(showEvents);

// Lists events in the sidebar
function renderEvent(e) 
{
        
    const li = document.createElement("li");
    li.className = "result";

    const level = severity(e);


    const badge = document.createElement("img");
    badge.src= `images/badges/${e.event_type}/${e.event_type}-${level}.png`
    badge.style = ` height: 30px; padding: 15px; background-color: var(--badge-${level}); border-radius: 20px;`

    const title = document.createElement("p");
    title.className = "result-title";
    if (e.event_type === "earthquake") {
        title.textContent = `M ${e.magnitude?.toFixed(1)} Earthquake`;
    }
    else
    {
        title.textContent = `${e.magnitude?.toFixed(0)}
            ${e.magnitude_unit.charAt(0).toUpperCase() + e.magnitude_unit.slice(1)} 
            ${e.event_type.charAt(0).toUpperCase() + e.event_type.slice(1)}`;
    }

    const sub = document.createElement("p");
    sub.className = "result-sub";
    const place = e.title.split(" - ")[1] ?? e.title;
    sub.textContent = `${place} · ${new Date(e.occurred_at).toLocaleString()}`;

    const text = document.createElement("div");
    text.append(title, sub);
    li.append(badge, text);
    return li;
}

    
    
    
    
    
document.getElementById("search-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = event.target.q.value.trim();
    const status = document.getElementById("search-status");
    const list = document.getElementById("results");
    list.textContent = "";
    
    // 1. Place name -> coordinates
    status.textContent = `Finding ${query}...`;
    try {
        const geoUrl = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
        const geoRes = await fetch(geoUrl);
        if (!geoRes.ok) {
            status.textContent = "Location search is unavailable right now";
            return;
        }
        const places = await geoRes.json();
        if (places.length === 0) {
            status.textContent = `Couldn't find "${query}"`;
            return;
        }
        const { lat, lon } = places[0];

        console.log(places[0]);

        const res = await fetch(`/events?lat=${lat}&lon=${lon}&radius_km=500`);
        if (!res.ok) {
            status.textContent = `Error loading events (${res.status})`;
            return;
        }
        map.flyTo([lat, lon], 6);
        showEvents(await res.json());
    } catch (err) {
        status.textContent = "Search failed, check your connection and try again";
    }

});

const zoneLayer = L.layerGroup().addTo(map);

async function loadZones() {
    const res = await fetch("/watch-zones");
    if (!res.ok) return;
    const zones = await res.json();

    const list = document.getElementById("zone-list");
    list.textContent = "";
    zoneLayer.clearLayers();

    for (const z of zones) {
        L.circle([z.lat, z.lon], { radius: z.radius_km * 1000, color: "#72e9c5", weight: 1, fillOpacity: 0.1 })
            .addTo(zoneLayer);

        const li = document.createElement("li");
        li.textContent = `${z.name} · ${z.radius_km} km · M${z.min_magnitude}+ `;
        const del = document.createElement("button");
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
            const r = await fetch(`/watch-zones/${z.id}`, { method: "DELETE" });
            if (r.ok) loadZones();
        });
        li.appendChild(del);
        list.appendChild(li);
    }
}

document.getElementById("zone-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("zone-status");
    const data = Object.fromEntries(new FormData(event.target));
    const body = {
        name: data.name,
        lat: Number(data.lat),
        lon: Number(data.lon),
        radius_km: Number(data.radius_km),
        min_magnitude: Number(data.min_magnitude || 0),
    };

    try {
        const res = await fetch("/watch-zones", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (res.status === 201) {
            status.textContent = "Zone created";
            event.target.reset();
            loadZones();
        } else if (res.status === 422) {
            const err = await res.json();
            status.textContent = err.detail.map(d => `${d.loc.at(-1)}: ${d.msg}`).join(", ");
        } else {
            status.textContent = `Error (${res.status})`;
        }
    } catch {
        status.textContent = "Couldn't reach the server";
    }
});

loadZones();

const zonePanel = document.getElementById("zone-panel");

function setZonePanel(open) {
    zonePanel.classList.toggle("open", open);
    zonePanel.setAttribute("aria-hidden", String(!open));
}

document.getElementById("open-zones").addEventListener("click", () => setZonePanel(true));
document.getElementById("close-zones").addEventListener("click", () => setZonePanel(false));
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setZonePanel(false);
});

map.on("click", (e) => {
    const form = document.getElementById("zone-form");
    form.lat.value = e.latlng.lat.toFixed(4);
    form.lon.value = e.latlng.lng.toFixed(4);
    setZonePanel(true);
});