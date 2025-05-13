import streamlit as st
import folium
from streamlit_folium import folium_static, st_folium
import pandas as pd
import json
from geopy.distance import geodesic
from sklearn.cluster import KMeans
import os

# --- Sidhuvud ---
st.set_page_config(page_title="Lekplatser i Göteborg", layout="wide")
st.title("🏞️ Lekplatser i Göteborg")
st.markdown("Denna karta visar lekplatser färgkodade efter avstånd till närmaste hållplats.")

# --- Läs lekplatser ---
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "lekplatser.json")

with open(file_path, "r", encoding="utf-8") as f:
    lekplatser_data = json.load(f)

lekplatser_df = pd.DataFrame([{
    'name': el.get('tags', {}).get('name', 'Okänd lekplats'),
    'lat': el['lat'],
    'lon': el['lon'],
    'typ': 'lekplats'
} for el in lekplatser_data])

# --- Läs hållplatser ---
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "stops.txt")

stop_df = pd.read_csv(file_path)

stop_df = stop_df[
    (stop_df['stop_lat'] >= 57.5) & (stop_df['stop_lat'] <= 57.85) &
    (stop_df['stop_lon'] >= 11.7) & (stop_df['stop_lon'] <= 12.1)
]
stop_df = stop_df.groupby('stop_name').agg({
    'stop_lat': 'mean',
    'stop_lon': 'mean'
}).reset_index()
stop_df = stop_df.rename(columns={'stop_name': 'name', 'stop_lat': 'lat', 'stop_lon': 'lon'})
stop_df['typ'] = 'hållplats'

# Kombinera
combined_df = pd.concat([lekplatser_df, stop_df[['name', 'lat', 'lon', 'typ']]], ignore_index=True)
lekplatser = combined_df[combined_df['typ'] == 'lekplats'].copy()
hållplatser = combined_df[combined_df['typ'] == 'hållplats'].copy()

# --- Funktion för avstånd ---
def närmaste_avstånd(lat, lon, hållplatser):
    lekplats_pos = (lat, lon)
    return min(geodesic(lekplats_pos, (r['lat'], r['lon'])).meters for _, r in hållplatser.iterrows())

lekplatser['avstånd_m'] = lekplatser.apply(
    lambda row: närmaste_avstånd(row['lat'], row['lon'], hållplatser), axis=1
)

# --- Kluster och färger ---
X = lekplatser[['avstånd_m']].values
kmeans = KMeans(n_clusters=4, random_state=0, n_init='auto').fit(X)
lekplatser['kluster'] = kmeans.labels_
kluster_medel = lekplatser.groupby('kluster')['avstånd_m'].mean().sort_values()
färger_sorterade = ['green', 'orange', 'red', 'purple']
färgkarta = {kluster: färger_sorterade[i] for i, kluster in enumerate(kluster_medel.index)}
lekplatser['färg'] = lekplatser['kluster'].map(färgkarta)

# --- Filtreringsgränssnitt i sidopanelen --- 

# Dropdown för att välja en hållplats 
valda_hållplatsnamn = st.sidebar.selectbox(
    label="",
    options=hållplatser['name'].sort_values().unique(),
    index=None,
    placeholder="Välj en hållplats"
)

# Ställ in radie
radie = st.sidebar.slider("Avstånd till lekplats (meter)", 100, 2000, 500, step=100)

# Om en hållplats valts, visa filtrerad karta
if valda_hållplatsnamn:
    vald_hållplats = hållplatser[hållplatser['name'] == valda_hållplatsnamn].iloc[0]
    vald_position = (vald_hållplats['lat'], vald_hållplats['lon'])

    # Beräkna avstånd från varje lekplats till vald hållplats
    lekplatser['avstånd_till_vald'] = lekplatser.apply(
        lambda row: geodesic((row['lat'], row['lon']), vald_position).meters, axis=1
    )
    lekplatser_nära = lekplatser[lekplatser['avstånd_till_vald'] <= radie].copy()

    # Färg baserat på avstånd till den valda hållplatsen
    def färg_avstånd(avstånd):
        if avstånd < 300:
            return 'green'
        elif avstånd < 700:
            return 'orange'
        else:
            return 'red'

    lekplatser_nära['färg_filtrerad'] = lekplatser_nära['avstånd_till_vald'].apply(färg_avstånd)

    # Skapa karta centrerad kring vald hållplats
    karta = folium.Map(location=[vald_hållplats['lat'], vald_hållplats['lon']], zoom_start=14)

    # Lägg till filtrerade lekplatser med färg efter avstånd till *valda hållplatsen*
    for _, rad in lekplatser_nära.iterrows():
        folium.CircleMarker(
            location=(rad['lat'], rad['lon']),
            radius=5,
            color=rad['färg_filtrerad'],
            fill=True,
            fill_color=rad['färg_filtrerad'],
            fill_opacity=0.7,
            popup=f"{rad['name']} ({int(rad['avstånd_till_vald'])} m)"
        ).add_to(karta)

    # Lägg till marker för vald hållplats
    folium.CircleMarker(
    location=vald_position,
    radius=2,
    color='blue',
    fill=True,
    fill_color='blue',
    fill_opacity=0.5,
    popup=vald_hållplats['name']
).add_to(karta)

# Om ingen hållplats valts, visa originalkartan
else:
    karta = folium.Map(location=[57.7, 11.97], zoom_start=12)

    # Alla lekplatser med klusterfärger
    for _, rad in lekplatser.iterrows():
        folium.CircleMarker(
            location=(rad['lat'], rad['lon']),
            radius=5,
            color=rad['färg'],
            fill=True,
            fill_color=rad['färg'],
            fill_opacity=0.7,
            popup=f"{rad['name']} ({int(rad['avstånd_m'])} m)"
        ).add_to(karta)

    # Alla hållplatser
    for _, rad in hållplatser.iterrows():
        folium.CircleMarker(
            location=(rad['lat'], rad['lon']),
            radius=2,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.5,
            popup=rad['name']
        ).add_to(karta)

# --- Visa karta i Streamlit ---
folium_static(karta)