import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import json
from geopy.distance import geodesic
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import os

# --- Sidhuvud ---
st.set_page_config(page_title="Lekplatser i Göteborg", layout="wide")
st.title("🏞️ Lekplatser i Göteborg")
st.markdown("Denna karta visar lekplatser färgkodade efter avstånd till närmaste hållplats.")

# --- Läs lekplatser ---
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "lekplatser_ny.json")
with open(file_path, "r", encoding="utf-8") as f:
    lekplatser_data = json.load(f)

lekplatser_df = pd.DataFrame([{
    'name': el.get('tags', {}).get('name', 'Okänd lekplats'),
    'lat': el['lat'],
    'lon': el['lon'],
    'typ': 'lekplats'
} for el in lekplatser_data])

# --- Läs alla hållplatser ---
stops_path = os.path.join(current_dir, "stops.txt")
stop_df = pd.read_csv(stops_path, usecols=["stop_id","stop_lat","stop_lon"])

# Filtrera inom bounding box
bbox_s, bbox_w, bbox_n, bbox_e = 57.6, 11.9, 57.8, 12.1
stop_df = stop_df[
    (stop_df['stop_lat'] >= bbox_s) & (stop_df['stop_lat'] <= bbox_n) &
    (stop_df['stop_lon'] >= bbox_w) & (stop_df['stop_lon'] <= bbox_e)
]
# Förbered lista med koordinater för varje stop_id
stops_coords = list(zip(stop_df['stop_lat'], stop_df['stop_lon']))

# Sätt typ och behåll stop_id som namn för visning
stop_df = stop_df.rename(columns={
    'stop_id': 'name', 'stop_lat': 'lat', 'stop_lon': 'lon'
})
stop_df['typ'] = 'hållplats'

# --- Kombinera lekplatser och hållplatser ---
combined_df = pd.concat([lekplatser_df, stop_df[['name', 'lat', 'lon', 'typ']]], ignore_index=True)
lekplatser = combined_df[combined_df['typ'] == 'lekplats'].copy()
hållplatser = combined_df[combined_df['typ'] == 'hållplats'].copy()

# --- Beräkna avstånd till närmaste hållplats ---
def närmaste_avstånd(lat, lon, coords):
    return min(geodesic((lat, lon), pt).meters for pt in coords)

lekplatser['avstånd_m'] = lekplatser.apply(
    lambda r: närmaste_avstånd(r['lat'], r['lon'], stops_coords), axis=1
)

# --- Klustring med samma KMeans-inställningar ---
# Skala förberedelse (neutral i 1D, men bra om fler features tillkommer)
X = lekplatser[['avstånd_m']].values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

kmeans = KMeans(n_clusters=4, random_state=0, n_init='auto')
lekplatser['kluster'] = kmeans.fit_predict(X_scaled)

# Skapa färgkarta baserat på medelavstånd per kluster
kluster_medel = lekplatser.groupby('kluster')['avstånd_m'].mean().sort_values()
färger_sorterade = ['green', 'orange', 'red', 'purple']
färgkarta = {kl: färger_sorterade[i] for i, kl in enumerate(kluster_medel.index)}
lekplatser['färg'] = lekplatser['kluster'].map(färgkarta)

# --- Sidopanel: filtreringsgränssnitt ---
valda_hållplatsnamn = st.sidebar.selectbox(
    "Filtrera lekplatser nära en viss hållplats:",
    options=hållplatser['name'].sort_values().unique(),
    placeholder="Välj en hållplats"
)
radie = st.sidebar.slider("Avståndsradie (meter)", 100, 2000, 500, step=100)

# --- Skapa karta ---
if valda_hållplatsnamn:
    vald = hållplatser[hållplatser['name'] == valda_hållplatsnamn].iloc[0]
    pos = (vald['lat'], vald['lon'])
    lekplatser['avstånd_till_vald'] = lekplatser.apply(
        lambda r: geodesic((r['lat'], r['lon']), pos).meters, axis=1
    )
    nära = lekplatser[lekplatser['avstånd_till_vald'] <= radie].copy()
    def färg_avstånd(a):
        return 'green' if a < 300 else 'orange' if a < 700 else 'red'
    nära['färg_filtrerad'] = nära['avstånd_till_vald'].apply(färg_avstånd)
    karta = folium.Map(location=pos, zoom_start=14)
    for _, r in nära.iterrows():
        folium.Marker(location=(r['lat'], r['lon']),
                      popup=f"{r['name']} ({int(r['avstånd_till_vald'])} m)",
                      icon=folium.Icon(color=r['färg_filtrerad'], icon='child', prefix='fa')
        ).add_to(karta)
    folium.CircleMarker(location=pos, radius=4, color='blue', fill=True,
                        fill_color='blue', fill_opacity=0.7,
                        popup=vald['name']).add_to(karta)
else:
    karta = folium.Map(location=[57.7, 11.97], zoom_start=12)
    for _, r in lekplatser.iterrows():
        folium.Marker(location=(r['lat'], r['lon']),
                      popup=f"{r['name']} ({int(r['avstånd_m'])} m)",
                      icon=folium.Icon(color=r['färg'], icon='child', prefix='fa')
        ).add_to(karta)

# Visa hållplatser
for _, r in hållplatser.iterrows():
    folium.CircleMarker(location=(r['lat'], r['lon']), radius=3, color='blue',
                        fill=True, fill_color='blue', fill_opacity=0.4,
                        popup=r['name']).add_to(karta)

# --- Rendera karta med legend ---
col1, _ = st.columns([3, 1])
with col1:
    folium_static(karta)
    st.markdown(
        f"""
        <div style="background:#f0f0f0;padding:10px;border-radius:10px;border:1px solid #ccc;">
        🟢 Nära hållplats<br>
        🟠 Medelnära hållplats<br>
        🔴 Långt från hållplats<br>
        🟣 Mycket långt från hållplats<br>
        🔵 Hållplats
        </div>
        """, unsafe_allow_html=True
    )