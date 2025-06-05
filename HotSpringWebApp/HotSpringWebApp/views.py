# -*- coding: utf-8 -*-
"""
HotSpringWebApp – final drop-in
• Robust °F extraction
• Heat-map + MarkerCluster (local assets)
• Tooltip shows Temp or “n/a”
"""

from datetime import datetime
from flask import render_template, request, url_for, send_from_directory
from HotSpringWebApp import app
import pandas as pd, folium, os, re, json, zipfile, simplekml
from folium.plugins import MarkerCluster, HeatMap
from folium.elements import Element

# ---------------------------------------------------------------------#
# 1  CSV → DataFrame                                                   #
# ---------------------------------------------------------------------#
_num_re = re.compile(r'[-+]?\d*\.?\d+')

def _first_number(val):
    """Return the first numeric substring in val, or None."""
    if pd.isna(val):
        return None
    m = _num_re.search(str(val))
    return float(m.group()) if m else None

def load_data():
    csv = os.path.join(app.root_path, 'data.csv')
    df = pd.read_csv(csv, header=None, skiprows=2)

    df.columns = [
        'state','d1','lat','d2','lon','d3','spring',
        'd4','d5','temp_f','d6','tc_raw','d8','code_pp',
        'd10','code_492','d12','circ','ph','d14','d15',
        'loc','d16','d17','usgs','d18'
    ]
    df = df[['lat','lon','spring','temp_f','ph','loc','usgs']]

    df['lat']    = pd.to_numeric(df['lat'], errors='coerce')
    df['lon']    = pd.to_numeric(df['lon'], errors='coerce')
    df['temp_f'] = df['temp_f'].apply(_first_number)
    df['ph']     = df['ph'].apply(_first_number)

    df.dropna(subset=['lat','lon','spring'], inplace=True)
    df['temp_c'] = (df['temp_f'] - 32) * 5/9
    return df


# ---------------------------------------------------------------------#
# 2  Download routes                                                   #
# ---------------------------------------------------------------------#
@app.route('/download/kml', endpoint='download_kml')
def download_kml():
    df  = load_data()
    kml = simplekml.Kml()
    for _, r in df.iterrows():
        desc = []
        if pd.notna(r['temp_f']):
            desc.append(f'Temp {r["temp_f"]:.0f} °F / {r["temp_c"]:.0f} °C')
        if pd.notna(r['ph']):
            desc.append(f'pH {r["ph"]}')
        if pd.notna(r['usgs']):
            desc.append(f'USGS {r["usgs"]}')
        if pd.notna(r['loc']):
            desc.append(f'Nearby {r["loc"]}')

        kml.newpoint(name=r['spring'],
                     coords=[(r['lon'], r['lat'])],
                     description=' | '.join(desc))

    outp = os.path.join(app.root_path, 'static', 'hot_springs.kml')
    kml.save(outp)
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               path='hot_springs.kml', as_attachment=True)


@app.route('/download/kmz', endpoint='download_kmz')
def download_kmz():
    df  = load_data()
    kml = simplekml.Kml()
    for _, r in df.iterrows():
        kml.newpoint(name=r['spring'],
                     coords=[(r['lon'], r['lat'])],
                     description=r['spring'])

    tmp = os.path.join(app.root_path, 'static', 'temp.kml')
    kmz = os.path.join(app.root_path, 'static', 'hot_springs.kmz')
    kml.save(tmp)
    with zipfile.ZipFile(kmz, 'w') as z:
        z.write(tmp, arcname='doc.kml')
    os.remove(tmp)

    return send_from_directory(os.path.join(app.root_path, 'static'),
                               path='hot_springs.kmz', as_attachment=True)


@app.route('/download/geojson', endpoint='download_geojson')
def download_geojson():
    df  = load_data()
    feats = []
    for _, r in df.iterrows():
        feats.append({
            'type': 'Feature',
            'geometry': {'type': 'Point',
                         'coordinates': [r['lon'], r['lat']]},
            'properties': {
                'spring_name': r['spring'],
                'temp_f': r['temp_f'],
                'ph': r['ph'],
                'location': r['loc'],
                'usgs_quad': r['usgs']
            }
        })
    outp = os.path.join(app.root_path, 'static', 'hot_springs.geojson')
    with open(outp, 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': feats}, f)

    return send_from_directory(os.path.join(app.root_path, 'static'),
                               path='hot_springs.geojson', as_attachment=True)


# ---------------------------------------------------------------------#
# 3  Main map view                                                     #
# ---------------------------------------------------------------------#
@app.route('/')
def home():
    df = load_data()
    tmin = df['temp_f'].dropna().min()
    tmax = df['temp_f'].dropna().max()
    pmin = df['ph']    .dropna().min()
    pmax = df['ph']    .dropna().max()

    # -------- sliders -------------------------------------------------
    if request.args:
        min_t = float(request.args.get('min_temp', tmin or 0))
        max_t = float(request.args.get('max_temp', tmax or 0))
        min_p = float(request.args.get('min_ph',   pmin or 0))
        max_p = float(request.args.get('max_ph',   pmax or 0))
        df = df[(df['temp_f'].isna()) | df['temp_f'].between(min_t, max_t)]
        df = df[(df['ph']    .isna()) | df['ph']    .between(min_p,  max_p)]
    else:
        min_t, max_t, min_p, max_p = tmin, tmax, pmin, pmax

    # -------- base map ------------------------------------------------
    centre = [df['lat'].mean(), df['lon'].mean()] if len(df) else [37.09, -95.71]
    m = folium.Map(location=centre, zoom_start=5, tiles='OpenStreetMap')

    # -------- heat-map (normalised weights) ---------------------------
    if tmax and tmin and tmax != tmin:
        heat_data = [[r.lat, r.lon, (r.temp_f - tmin)/(tmax - tmin)]
                     for r in df.itertuples() if pd.notna(r.temp_f)]
    else:  # fallback: unweighted
        heat_data = [[r.lat, r.lon] for r in df.itertuples()]

    if heat_data:
        HeatMap(heat_data, radius=20, blur=15, min_opacity=0.3).add_to(m)

    # -------- clustered markers --------------------------------------
    cluster = MarkerCluster().add_to(m)
    for _, r in df.iterrows():
        if pd.isna(r['temp_f']): col = 'gray'
        elif r['temp_f'] < 100:  col = 'blue'
        elif r['temp_f'] < 140:  col = 'orange'
        else:                    col = 'red'

        temp_txt = (f"{r['temp_f']:.0f} °F / {r['temp_c']:.0f} °C"
                    if pd.notna(r['temp_f']) else 'n/a')
        tooltip = f"{r['spring']} – {temp_txt.split('/')[0]}"

        popup = (f"<b>{r['spring']}</b><br>"
                 f"Temp: {temp_txt}<br>"
                 f"{'pH: ' + str(r['ph']) + '<br>' if pd.notna(r['ph']) else ''}"
                 f"{'USGS Quad: ' + r['usgs'] + '<br>' if pd.notna(r['usgs']) else ''}"
                 f"{'Nearby: ' + r['loc'] if pd.notna(r['loc']) else ''}")

        folium.Marker(
            [r['lat'], r['lon']],
            tooltip=tooltip,
            popup=folium.Popup(popup, max_width=300),
            icon=folium.Icon(color=col, icon='info-sign')
        ).add_to(cluster)

    # -------- inject local plug-ins *after* Leaflet -------------------
    root = m.get_root()
    root.header.add_child(Element(
        '<link rel="stylesheet" '
        'href="/static/libs/leaflet/MarkerCluster.Default.css">'))

    root.html.add_child(Element(
        '<script src="/static/libs/leaflet/leaflet.markercluster.js"></script>'))
    root.html.add_child(Element(
        '<script src="/static/libs/leaflet/leaflet-heat.js"></script>'))

    # -------- save + render ------------------------------------------
    m.save(os.path.join(app.root_path, 'static', 'map.html'))
    map_url = url_for('static', filename='map.html',
                      v=int(datetime.now().timestamp()))

    return render_template(
        'index.html',
        title='Hot Springs Map',
        year=datetime.now().year,
        min_temp=min_t or 0, max_temp=max_t or 0,
        min_ph=min_p or 0,   max_ph=max_p or 0,
        rows=len(df),
        map_url=map_url
    )
