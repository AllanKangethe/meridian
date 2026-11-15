// What the user is currently filtering by
const filters = { type: null, lat: null, lon: null };
let search = "";

function eventsUrl() {
    const params = new URLSearchParams();

    if (filters.type) params.set("type", filters.type);
    if (filters.lat != null) {
        params.set("lat", filters.lat);
        params.set("lon", filters.lon);
        params.set("radius_km", 500);
        
    }
    return `/events?${params}`;
}

const chips = document.querySelectorAll(".chips .chip");

chips.forEach((chip) => {
    chip.addEventListener("click", () => {
        chips.forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");

        const type = chip.dataset.type;
        filters.type = type === "all" ? null : type;
        loadEvents();
    });
});


// Load events from the server and display them on the map and in the list
async function loadEvents() {
    const status = document.getElementById("search-status");
    try {
        const res = await fetch(eventsUrl());

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
    maxBounds: [[-85, -Infinity], [85, Infinity]],
    maxBoundsViscosity: 1.0,
    worldCopyJump: true,
}).setView([20, 0], 2);

map.attributionControl.setPrefix(false);


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


const capitalize = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : "";

// Lists events in the sidebar
function renderEvent(e) 
{
        
    const li = document.createElement("li");
    li.className = "result";
    li.addEventListener("click", () => {
        map.flyTo([e.lat, e.lon], 8);
    });

    const level = severity(e);


    const badge = document.createElement("img");
    badge.src= `images/badges/${e.event_type}/${e.event_type}-${level}.png`
    badge.className = "event-badge";
    badge.style.backgroundColor = `var(--badge-${level})`;


    const title = document.createElement("p");
    title.className = "result-title";
    if (e.event_type === "earthquake") {
        title.textContent = `M ${e.magnitude?.toFixed(1) ?? "?"} Earthquake`;
    } else {
        const size = e.magnitude != null ? `${Math.round(e.magnitude)} ` : "";
        const unit = e.magnitude_unit ? `${capitalize(e.magnitude_unit)} ` : "";
        title.textContent = `${size}${unit}${capitalize(e.event_type)}`;
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

    // Empty search: back to the whole world
    if (!query) {
        filters.lat = null;
        filters.lon = null;
        map.setView([20, 0], 2);
        await loadEvents();
        return;
    }
    

    const status = document.getElementById("search-status");
    const list = document.getElementById("results");
    list.textContent = "";
    
    // 1. Place name -> coordinates
    status.textContent = `Finding ${query}...`;
    try {
        const geoUrl = `https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=en&q=${encodeURIComponent(query)}`;
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
        filters.lat = lat;
        filters.lon = lon;
        map.flyTo([lat, lon], 6);
        await loadEvents();
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
        L.circle([z.lat, z.lon], { radius: z.radius_km * 1000, color: "#a10aa7", weight: 1, fillOpacity: 0.1 })
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