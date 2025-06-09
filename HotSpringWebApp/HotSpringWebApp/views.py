# -*- coding: utf-8 -*-
"""
Hot Spring Explorer – views.py
✓ robust CSV parsing
✓ heat-map + MarkerCluster
✓ KML / KMZ / GeoJSON download
✓ relative imports for nested pkg
✓ /health endpoint for Render
"""

from datetime import datetime
from flask import render_template, request, url_for, send_from_directory
from . import app                       # ← relative import (inside inner package)
import pandas as pd, folium, os, re, json, zipfile, simplekml
from folium.plugins import MarkerCluster, HeatMap
from folium.elements import Element


# ─────── health probe ──────────────────────────────────────────────────
@app.route("/health")
def health():
    """Lightweight endpoint for Render health-check – always 200."""
    return "", 200


# ─────── CSV → DataFrame (unchanged) ───────────────────────────────────
_num = re.compile(r"[-+]?\d*\.?\d+")


def _num_or_none(s):
    m = _num.search(str(s)) if pd.notna(s) else None
    return float(m.group()) if m else None


def load_data():
    csv = os.path.join(app.root_path, "data.csv")
    df = pd.read_csv(csv, header=None, skiprows=2)
    df.columns = [
        "state", "d1", "lat", "d2", "lon", "d3", "spring",
        "d4", "d5", "temp_f", "d6", "tc_raw", "d8", "code_pp",
        "d10", "code_492", "d12", "circ", "ph", "d14", "d15",
        "loc", "d16", "d17", "usgs", "d18"
    ]
    df = df[["lat", "lon", "spring", "temp_f", "ph", "loc", "usgs"]]
    for col in ("lat", "lon"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["temp_f"] = df["temp_f"].apply(_num_or_none)
    df["ph"] = df["ph"].apply(_num_or_none)
    df.dropna(subset=["lat", "lon", "spring"], inplace=True)
    df["temp_c"] = (df["temp_f"] - 32) * 5 / 9
    return df


# ─────── download routes (unchanged) ───────────────────────────────────
@app.route("/download/kml")
def download_kml():
    df = load_data()
    kml = simplekml.Kml()
    for _, r in df.iterrows():
        desc = []
        if pd.notna(r["temp_f"]):
            desc.append(f"Temp {r['temp_f']:.0f} °F / {r['temp_c']:.0f} °C")
        if pd.notna(r["ph"]):
            desc.append(f"pH {r['ph']}")
        if pd.notna(r["usgs"]):
            desc.append(f"USGS {r['usgs']}")
        if pd.notna(r["loc"]):
            desc.append(f"Nearby {r['loc']}")
        kml.newpoint(r["spring"], coords=[(r["lon"], r["lat"])],
                     description=" | ".join(desc))
    outp = os.path.join(app.root_path, "static", "hot_springs.kml")
    kml.save(outp)
    return send_from_directory(os.path.join(app.root_path, "static"),
                               "hot_springs.kml", as_attachment=True)


@app.route("/download/kmz")
def download_kmz():
    df = load_data()
    kml = simplekml.Kml()
    for _, r in df.iterrows():
        kml.newpoint(r["spring"], coords=[(r["lon"], r["lat"])])
    tmp = os.path.join(app.root_path, "static", "temp.kml")
    kmz = os.path.join(app.root_path, "static", "hot_springs.kmz")
    kml.save(tmp)
    with zipfile.ZipFile(kmz, "w") as z:
        z.write(tmp, arcname="doc.kml")
    os.remove(tmp)
    return send_from_directory(os.path.join(app.root_path, "static"),
                               "hot_springs.kmz", as_attachment=True)


@app.route("/download/geojson")
def download_geojson():
    df = load_data()
    feats = []
    for _, r in df.iterrows():
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "spring_name": r["spring"],
                "temp_f": r["temp_f"],
                "ph": r["ph"],
                "location": r["loc"],
                "usgs_quad": r["usgs"]
            }
        })
    path = os.path.join(app.root_path, "static", "hot_springs.geojson")
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    return send_from_directory(os.path.join(app.root_path, "static"),
                               "hot_springs.geojson", as_attachment=True)


# ─────── main map view (unchanged) ─────────────────────────────────────
@app.route("/")
def home():
    df = load_data()
    tmin, tmax = df["temp_f"].dropna().agg(["min", "max"])
    pmin, pmax = df["ph"].dropna().agg(["min", "max"])

    # sliders
    min_t = float(request.args.get("min_temp", tmin or 0))
    max_t = float(request.args.get("max_temp", tmax or 0))
    min_p = float(request.args.get("min_ph", pmin or 0))
    max_p = float(request.args.get("max_ph", pmax or 0))
    if tmax != tmin:
        df = df[(df["temp_f"].isna()) | df["temp_f"].between(min_t, max_t)]
    df = df[(df["ph"].isna()) | df["ph"].between(min_p, max_p)]

    # map
    center = [df["lat"].mean(), df["lon"].mean()] if len(df) else [37.09, -95.71]
    m = folium.Map(location=center, zoom_start=5, tiles="OpenStreetMap")

    # heat-map
    if tmax != tmin:
        heat = [[r.lat, r.lon, (r.temp_f - tmin) / (tmax - tmin)]
                for r in df.itertuples() if pd.notna(r.temp_f)]
    else:
        heat = [[r.lat, r.lon] for r in df.itertuples()]
    if heat:
        HeatMap(heat, radius=20, blur=15, min_opacity=0.3).add_to(m)

    # markers
    cluster = MarkerCluster().add_to(m)
    for _, r in df.iterrows():
        if pd.isna(r["temp_f"]): col = "gray"
        elif r["temp_f"] < 100:  col = "blue"
        elif r["temp_f"] < 140:  col = "orange"
        else:                    col = "red"

        temp_txt = (f"{r['temp_f']:.0f} °F / {r['temp_c']:.0f} °C"
                    if pd.notna(r["temp_f"]) else "n/a")
        tooltip = f"{r['spring']} – {temp_txt.split('/')[0]}"
        popup = (f"<b>{r['spring']}</b><br>"
                 f"Temp: {temp_txt}<br>"
                 f"{('pH: ' + str(r['ph']) + '<br>') if pd.notna(r['ph']) else ''}"
                 f"{('USGS Quad: ' + r['usgs'] + '<br>') if pd.notna(r['usgs']) else ''}"
                 f"{('Nearby: ' + r['loc']) if pd.notna(r['loc']) else ''}")

        folium.Marker(
            [r["lat"], r["lon"]],
            tooltip=tooltip,
            popup=folium.Popup(popup, max_width=300),
            icon=folium.Icon(color=col, icon="info-sign")
        ).add_to(cluster)

    # local plug-ins
    root = m.get_root()
    root.header.add_child(Element(
        '<link rel="stylesheet" href="/static/libs/leaflet/MarkerCluster.Default.css">'))
    root.html.add_child(Element(
        '<script src="/static/libs/leaflet/leaflet.markercluster.js"></script>'))
    root.html.add_child(Element(
        '<script src="/static/libs/leaflet/leaflet-heat.js"></script>'))

    m.save(os.path.join(app.root_path, "static", "map.html"))
    map_url = url_for("static", filename="map.html",
                      v=int(datetime.now().timestamp()))

    return render_template(
        "index.html",
        title="Hot Springs Map",
        year=datetime.now().year,
        min_temp=min_t or 0, max_temp=max_t or 0,
        min_ph=min_p or 0,   max_ph=max_p or 0,
        rows=len(df),
        map_url=map_url
    )
