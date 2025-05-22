import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import os
from folium.plugins import MarkerCluster
from geopy.distance import geodesic

# Filväg till JSON-filen
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "lekplatser_ny.json")

# Funktion för att ladda lekplatser med cache
@st.cache_data
def load_lekplatser(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

lekplatser_data = load_lekplatser(file_path)

# Hämta unika teman och områden
teman = sorted(set(item["tema"] for item in lekplatser_data if "tema" in item))
områden = sorted(set(item["område"] for item in lekplatser_data if "område" in item))

# Streamlit widgets
selected_teman = st.multiselect("Välj tema:", teman)
selected_områden = st.multiselect("Välj område:", områden)

# Filtrera data baserat på val
filtered_data = [
    item for item in lekplatser_data
    if (not selected_teman or item["tema"] in selected_teman) and
       (not selected_områden or item["område"] in selected_områden)
]

# Funktion för att hämta lat och lon för en lekplats
@st.cache_data
def get_lat_lon(item):
    lat = item["geo"]['coordinates'][1]
    lon = item["geo"]['coordinates'][0]
    return lat, lon

# Funktion för att läsa hållplatser med cache
@st.cache_data
def load_stops(file_path):
    df = pd.read_csv(file_path)
    df = df[
        (df['stop_lat'] >= 57.5) & (df['stop_lat'] <= 57.85) &
        (df['stop_lon'] >= 11.7) & (df['stop_lon'] <= 12.1)
    ]
    df = df.drop_duplicates(subset='stop_name', keep='first')
    df = df.rename(columns={'stop_name': 'name', 'stop_lat': 'lat', 'stop_lon': 'lon'})
    df['typ'] = 'hållplats'
    return df

stop_df = load_stops(os.path.join(current_dir, "stops.txt"))

# Funktion för att läsa toaletter med cache
@st.cache_data
def load_toaletter(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

toaletter_data = load_toaletter(os.path.join(current_dir, "toaletter.json"))

# Extrahera koordinater för toaletterna och skapa DataFrame
toalett_coords = []
for item in toaletter_data:
    lat = item['geo']['coordinates'][1]
    lon = item['geo']['coordinates'][0]
    namn = item['name']
    toatyp = item.get('toalett_typ', 'okänd')
    toalett_coords.append({'name': namn, 'lat': lat, 'lon': lon, 'typ': 'toalett', 'toalett_typ': toatyp})

toalett_df = pd.DataFrame(toalett_coords)

# Funktion för att beräkna avstånd till närmaste hållplats
def närmaste_avstånd(lat, lon, stop_df):
    position = (lat, lon)
    min_dist = float('inf')
    for _, row in stop_df.iterrows():
        stop_position = (row['lat'], row['lon'])
        dist = geodesic(position, stop_position).meters
        if dist < min_dist:
            min_dist = dist
    return min_dist

# Funktion för att beräkna avstånd till närmaste toalett
def närmaste_toalett_avstånd(lat, lon, toalett_df):
    position = (lat, lon)
    min_dist = float('inf')
    for _, row in toalett_df.iterrows():
        toilet_position = (row['lat'], row['lon'])
        dist = geodesic(position, toilet_position).meters
        if dist < min_dist:
            min_dist = dist
    return min_dist

# Lägg till avstånd till närmaste hållplats och toalett i varje lekplats
for item in filtered_data:
    lat, lon = get_lat_lon(item)
    item['avstånd_m'] = närmaste_avstånd(lat, lon, stop_df)
    item['avstånd_toalett'] = närmaste_toalett_avstånd(lat, lon, toalett_df)

# Skapa en karta
if filtered_data:
    m = folium.Map(location=[57.7089, 11.9746], zoom_start=12)
    marker_cluster = MarkerCluster().add_to(m)

    for item in filtered_data:
        lat, lon = get_lat_lon(item)
        popup_text = f"Namn: {item['name']}<br>Tema: {item.get('tema', 'okänd')}<br>Område: {item.get('område', 'okänd')}<br>Avstånd till närmaste hållplats: {int(item.get('avstånd_m', 0))} m<br>Avstånd till närmaste toalett: {int(item.get('avstånd_toalett', 0))} m"
        folium.Marker([lat, lon], popup=popup_text).add_to(marker_cluster)

    folium_static(m)
else:
    st.write("Ingen lekplats matchar dina val.")
