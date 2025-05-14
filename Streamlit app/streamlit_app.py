import streamlit as st
import pandas as pd
import folium
from folium import Marker, CircleMarker
from streamlit_folium import folium_static
from haversine import haversine
from PIL import Image

# Streamlit-sida
st.set_page_config(layout="wide")
st.title("Lekplatser i Göteborg")
st.markdown("Visualisering av lekplatser och deras närhet till kollektivtrafik.")

# Bild i sidopanel
with st.sidebar:
    image = Image.open("lekplats.jpg")
    st.image(image, use_column_width=True)

# Selectbox för att välja visningsläge
läge = st.sidebar.selectbox(
    "Välj visningsläge",
    options=["Visa alla lekplatser", "Filtrera efter hållplats"]
)

# Läs in data
lekplatser = pd.read_csv("data/lekplatser_klar.csv")
hållplatser = pd.read_csv("data/hallplatser_klar.csv")

# Layout
col1, col2 = st.columns([2, 1])

# --- Visa alla lekplatser ---
if läge == "Visa alla lekplatser":
    karta = folium.Map(location=[57.7, 11.97], zoom_start=12)

    # Lägg till lekplatser
    for _, rad in lekplatser.iterrows():
        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=f"{rad['name']} ({int(rad['avstånd_m'])} m)",
            icon=folium.Icon(color=rad['färg'], icon='child', prefix='fa')
        ).add_to(karta)

    # Lägg till hållplatser
    for _, rad in hållplatser.iterrows():
        folium.CircleMarker(
            location=(rad['lat'], rad['lon']),
            radius=3,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.4,
            popup=rad['name']
        ).add_to(karta)

    # Visa karta
    with col1:
        folium_static(karta)

    with col2:
        st.markdown("### Förklaring")
        st.markdown("Kartan visar alla lekplatser och deras avstånd till närmaste hållplats.")
        st.markdown("- **Grön** ikon = nära hållplats")
        st.markdown("- **Orange** ikon = längre bort")
        st.markdown("Blå cirklar = hållplatser")

# --- Filtreringsläge ---
else:
    valda_hållplatsnamn = st.sidebar.selectbox(
        "Välj hållplats",
        options=hållplatser['name'].sort_values().unique(),
        index=None,
        placeholder="Välj en hållplats"
    )

    radie = st.sidebar.slider("Avstånd till lekplats (meter)", 100, 2000, 500, step=100)

    if valda_hållplatsnamn:
        vald_hållplats = hållplatser[hållplatser['name'] == valda_hållplatsnamn].iloc[0]
        lat, lon = vald_hållplats['lat'], vald_hållplats['lon']

        lekplatser['avstånd_m'] = lekplatser.apply(
            lambda row: haversine((lat, lon), (row['lat'], row['lon'])) * 1000, axis=1
        )

        filtrerade_lekplatser = lekplatser[lekplatser['avstånd_m'] <= radie]

        karta = folium.Map(location=[lat, lon], zoom_start=14)

        for _, rad in filtrerade_lekplatser.iterrows():
            folium.Marker(
                location=(rad['lat'], rad['lon']),
                popup=f"{rad['name']} ({int(rad['avstånd_m'])} m)",
                icon=folium.Icon(color='green', icon='child', prefix='fa')
            ).add_to(karta)

        folium.CircleMarker(
            location=(lat, lon),
            radius=6,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.6,
            popup=vald_hållplats['name']
        ).add_to(karta)

        with col1:
            folium_static(karta)

        with col2:
            st.markdown(f"### Lekplatser inom {radie} m från {valda_hållplatsnamn}")
            st.write(filtrerade_lekplatser[['name', 'avstånd_m']].rename(columns={
                'name': 'Lekplats', 'avstånd_m': 'Avstånd (m)'
            }).sort_values('Avstånd (m)'))

    else:
        st.warning("Välj en hållplats för att se filtrerade lekplatser.")