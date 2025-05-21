import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import json
from geopy.distance import geodesic
from sklearn.cluster import KMeans
import os

# --- Sidhuvud ---
st.set_page_config(page_title="Lekplatser i Göteborg", layout="wide")
st.title("Lekplatser i Göteborg")

with st.expander("ℹ️ Klicka här för att läsa hur kartan fungerar"):
    st.markdown("""
    **Välkommen till Lekplatskartan!**

    Den här interaktiva kartan hjälper dig att hitta roliga lekplatser i Göteborg samtidigt som den visar hur långt det är till närmaste kollektivtrafikhållplats.

    💡 **Så här gör du:**
    - Använd menyn till vänster för att hitta lekplatser nära en viss hållplats.
    - Justera avståndsradien för att visa fler eller färre lekplatser.
    - Klicka på en lekplats på kartan för att se avstånd och uppskattad gångtid.

    Legend med färgförklaringar finns längre ner på sidan.

    **Trevlig lek!**
    """)

st.markdown("**Denna karta visar lekplatser färgkodade efter avstånd till närmaste hållplats.**")

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

# --- Läs hållplatser ---
stop_df = pd.read_csv(os.path.join(current_dir, "stops.txt"))

stop_df = stop_df[
    (stop_df['stop_lat'] >= 57.5) & (stop_df['stop_lat'] <= 57.85) &
    (stop_df['stop_lon'] >= 11.7) & (stop_df['stop_lon'] <= 12.1)
]

#Ta bara en rad per hållplats-per hållplats namn (första stop ID räcker)
stop_df = stop_df.drop_duplicates(subset='stop_name', keep='first')

stop_df = stop_df.rename(columns={
    'stop_name': 'name', 'stop_lat': 'lat', 'stop_lon': 'lon'
})

stop_df['typ'] = 'hållplats'

# Kombinera
combined_df = pd.concat([lekplatser_df, stop_df[['name', 'lat', 'lon', 'typ']]], ignore_index=True)
lekplatser = combined_df[combined_df['typ'] == 'lekplats'].copy()
hållplatser = combined_df[combined_df['typ'] == 'hållplats'].copy()

# --- Beräkna avstånd till närmaste hållplats ---
def närmaste_avstånd(lat, lon, hållplatser):
    lekplats_pos = (lat, lon)
    return min(geodesic(lekplats_pos, (r['lat'], r['lon'])).meters for _, r in hållplatser.iterrows())

lekplatser['avstånd_m'] = lekplatser.apply(
    lambda row: närmaste_avstånd(row['lat'], row['lon'], hållplatser), axis=1
)

def uppskattad_gångtid(meter):
    minuter = int(round(meter/83))  # 5 km/h gånghastighet
    return f"~{minuter} min"

# --- Klustring och färger ---
X = lekplatser[['avstånd_m']].values
kmeans = KMeans(n_clusters=4, random_state=0, n_init='auto').fit(X)
lekplatser['kluster'] = kmeans.labels_
kluster_medel = lekplatser.groupby('kluster')['avstånd_m'].mean().sort_values()
färger_sorterade = ['green', 'orange', 'red', 'purple']
färgkarta = {kluster: färger_sorterade[i] for i, kluster in enumerate(kluster_medel.index)}
lekplatser['färg'] = lekplatser['kluster'].map(färgkarta)

# --- Sidopanel: filtreringsgränssnitt ---
valda_hållplatsnamn = st.sidebar.selectbox(
    "Filtrera lekplatser nära en viss hållplats:",
    options=hållplatser['name'].sort_values().unique(),
    index=None,
    placeholder="Välj en hållplats"
)
radie = st.sidebar.slider("Avståndsradie (meter)", 100, 2000, 500, step=100)

# --- Skapa karta ---
if valda_hållplatsnamn:
    vald_hållplats = hållplatser[hållplatser['name'] == valda_hållplatsnamn].iloc[0]
    vald_position = (vald_hållplats['lat'], vald_hållplats['lon'])

    lekplatser['avstånd_till_vald'] = lekplatser.apply(
        lambda row: geodesic((row['lat'], row['lon']), vald_position).meters, axis=1
    )
    lekplatser_nära = lekplatser[lekplatser['avstånd_till_vald'] <= radie].copy()

    def färg_avstånd(avstånd):
        if avstånd < 181:
            return 'green'
        elif avstånd < 344:
            return 'orange'
        elif avstånd < 596:
            return 'red'
        else:
            return 'purple'

    lekplatser_nära['färg_filtrerad'] = lekplatser_nära['avstånd_till_vald'].apply(färg_avstånd)

    karta = folium.Map(location=[vald_hållplats['lat'], vald_hållplats['lon']], zoom_start=14)

if valda_hållplatsnamn and vald_position is not None:
    # Filtrerat läge – lekplatser nära vald hållplats
    for _, rad in lekplatser_nära.iterrows():
        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=f"{rad['name']} ({int(rad['avstånd_till_vald'])} m, {uppskattad_gångtid(rad['avstånd_till_vald'])})",
            icon=folium.Icon(color=rad['färg_filtrerad'], icon='child', prefix='fa')
        ).add_to(karta)

    # Markera vald hållplats
    folium.CircleMarker(
        location=vald_position,
        radius=4,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.7,
        popup=vald_hållplats['name']
    ).add_to(karta)

else:
    # Standardläge – visa alla lekplatser
    karta = folium.Map(location=[57.7, 11.97], zoom_start=12)
    
    for _, rad in lekplatser.iterrows():
        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=f"{rad['name']} ({int(rad['avstånd_m'])} m, {uppskattad_gångtid(rad['avstånd_m'])})",
            icon=folium.Icon(color=rad['färg'], icon='child', prefix='fa')
        ).add_to(karta)

if not valda_hållplatsnamn:
    # Visa alla hållplatser (standardläge)
    for _, rad in hållplatser.iterrows():
        folium.CircleMarker(
            location=(rad['lat'], rad['lon']),
            radius=3,
            color='blue',
            opacity=0.6,
            fill=True,
            fill_color='blue',
            fill_opacity=0.4,
            popup=rad['name']
        ).add_to(karta)
else:
    # Visa endast den valda hållplatsen
    folium.CircleMarker(
        location=(vald_position),
        radius=4,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.7,
        popup=vald_hållplats['name']
    ).add_to(karta)

# --- Legend ---
# --- Maxavstånd per kluster ---
kluster_max = lekplatser.groupby('kluster')['avstånd_m'].max()
kluster_beskrivning = {
    färgkarta[kl]: f"max {int(kluster_max[kl])}m ({uppskattad_gångtid(kluster_max[kl])})" for kl in kluster_max.index
}
# --- Legend i sidopanelen ---
col1, _ = st.columns([3, 1])  # Endast en kolumn synlig, andra döljs

with col1:
    folium_static(karta)

    st.markdown(
        f"""
        <div style="
            background-color: #f0f0f0;
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #ccc;
            color: #000000;
            font-size: 15px;
            line-height: 1.5;
            margin-top: -10px;
            width: fit-content;
        ">
        🟢 Lekplats nära hållplats ({kluster_beskrivning.get('green', '')})<br>
        🟠 Lekplats medelnära hållplats ({kluster_beskrivning.get('orange', '')})<br>
        🔴 Lekplats långt från hållplats ({kluster_beskrivning.get('red', '')})<br>
        🟣 Lekplats väldigt långt från hållplats ({kluster_beskrivning.get('purple', '')})<br>
        🔵 Hållplats
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<br><br><br>", unsafe_allow_html=True)

with st.expander("ℹ️ Om denna applikation"):
    st.markdown("""
**Om denna applikation:**  
Version: 1  
Senast uppdaterad: 20 maj 2025  

**Skapare:**  
Victoria Johansson, Lina Axelson, Eleonor Borgqvist, Ebba Reis och Ella Anderzén – studenter vid Göteborgs Universitet  

**Data från:**  
GTFS-data från Västtrafik och lekplatsdata från OpenStreetMap  

**Appen använder:**  
Python, Streamlit, Folium, folium static, pandas, geopy (geodesic), os och KMeans-klustring  

**Filerna är i formatet:**  
JSON  

Har du frågor, förslag eller hittat en bugg?  
Kontakta gärna Victoria Johansson via:
[victoriaj0109@outlook.com](mailto:victoriaj0109@outlook.com)  
eller besök projektets GitHub-sida:  
[https://github.com/SVP-GU/group-project-hackstreet-boys](https://github.com/SVP-GU/group-project-hackstreet-boys)
    """, unsafe_allow_html=True)

    