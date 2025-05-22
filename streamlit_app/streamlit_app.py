import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import json
from geopy.distance import geodesic
from sklearn.cluster import KMeans
import os
from sklearn.preprocessing import StandardScaler

# --- Läs lekplatser --- med cacheing
@st.cache_data
def läs_lekplatser(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Läs hållplatser --- #Med chacheing
@st.cache_data
def läs_hållplatser(file_path):
    df = pd.read_csv(file_path)
    df = df[
        (df['stop_lat'] >= 57.5) & (df['stop_lat'] <= 57.85) &
        (df['stop_lon'] >= 11.7) & (df['stop_lon'] <= 12.1)
    ]
    df = df.drop_duplicates(subset='stop_name', keep='first')
    df = df.rename(columns={'stop_name': 'name', 'stop_lat': 'lat', 'stop_lon': 'lon'})
    df['typ'] = 'hållplats'
    return df

# --- Läs toaletter ---
@st.cache_data
def läs_toaletter(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Beräkna avstånd till närmaste hållplats ---
def närmaste_avstånd(lat, lon, hållplatser):
    lekplats_pos = (lat, lon)
    return min(geodesic(lekplats_pos, (r['lat'], r['lon'])).meters for _, r in hållplatser.iterrows())

def uppskattad_gångtid(meter):
    minuter = int(round(meter/83))  # 5 km/h gånghastighet
    return f"{minuter} min"

#Beräkna avstånd till närmast toalett
def närmaste_toalett_avstånd(lat, lon, toaletter):
    pos = (lat, lon)
    return min(geodesic(pos, (r['lat'], r['lon'])).meters for _, r in toaletter.iterrows())

# --- Sidhuvud ---
st.set_page_config(page_title="Göteborgs lekplatskarta", layout="wide")
st.title("Göteborgs lekplatskarta")

st.markdown("""
<style>
    /*  SIDOPANEL  */
    section[data-testid="stSidebar"] *{
        font-family: "Helvetica", sans-serif;
        font-size: 0.95rem;      /* lite större text            */
        line-height: 1.5;
    }
    section[data-testid="stSidebar"] h3 {            /* rubriken Klustringsmetod */
        margin-top: 0.8rem;
        font-weight: 700;
    }

    /*  FOLIUM-POPUPS (rubrik + text)  */
    .leaflet-popup-content {
        font-family: "Helvetica", sans-serif;
        font-size: 14px;
        line-height: 1.4;
    }
    .leaflet-popup-content strong{
        font-size: 15px;
        font-weight: 600;
    }

    /*  LEGEND-RUTA  */
    .lekplats-legend{
        background:#ffffffcc;       /* vit, lätt transparent   */
        padding:12px 16px;
        border-radius:12px;
        border:1px solid #ddd;
        box-shadow:0 0 6px rgba(0,0,0,0.15);
        font-family:"Helvetica",sans-serif;
        font-size:15px;
        line-height:1.4;
    }
</style>
""", unsafe_allow_html=True)

with st.expander("ℹ️ Klicka här för att läsa hur kartan fungerar"):
    st.markdown("""
    **Välkommen till lekplatskartan!**

    Den här interaktiva kartan visar stadens lekplatser och hur långt det är att gå till närmaste kollektivtrafikhållplats (och/eller toalett).

    **💡Såhär gör du:**
    1. **Filtrera** (valfritt)  
       Öppna sidopanelen och välj en hållplats för att se lekplatser inom vald radie runt just den hållplatsen.
    2. **Ställ in radien**  
       Dra reglaget **Avståndsradie** (meter) för att visa fler eller färre lekplatser.
    3. **Välj klustringsmetod**  
       • *Hållplatsavstånd:* Färger baseras på avstånd till närmaste hållplats.  
       • *Toalettavstånd:* Färger baseras på avstånd till närmaste toalett.  
       • *Både hållplats + toalett:* Kombinerar båda kriterierna.  
    4. **Utforska kartan**  
       • Klicka på en lekplats-ikon för exakta avstånd och uppskattad gångtid till närmsta hållplats.  
       • Blå cirklar markerar hållplatser; grå WC-ikoner markerar toaletter när de är relevanta.

    **🔔 OBS!**
    Popup-informationen och färgkodningen visar **alltid avståndet till den hållplats som ligger närmast varje lekplats,** även om du har filtrerat på en specifik hållplats. Med andra ord speglar siffrorna den faktiska närmaste kollektivtrafikanslutningen, inte nödvändigtvis den hållplats du valde i filtret.

    **Trevlig lek!**
    """)

current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, "lekplatser_ny.json")
lekplatser_data = läs_lekplatser(file_path)

lekplatser_df = pd.DataFrame([{
    'name': el.get('tags', {}).get('name', 'Okänd lekplats'),
    'lat': el['lat'],
    'lon': el['lon'],
    'typ': 'lekplats'
} for el in lekplatser_data])

file_path = os.path.join(current_dir, "stops.txt")
stops_df = läs_hållplatser(file_path)

file_path = os.path.join(current_dir, "toaletter.json")
toaletter_data = läs_toaletter(file_path)

toaletter_df = pd.DataFrame([{
    'lat': el['lat'],
    'lon': el['lon'],
} for el in toaletter_data])

# Kombinera
combined_df = pd.concat([lekplatser_df, stops_df[['name', 'lat', 'lon', 'typ']]], ignore_index=True)
lekplatser = combined_df[combined_df['typ'] == 'lekplats'].copy()
hållplatser = combined_df[combined_df['typ'] == 'hållplats'].copy()

lekplatser['avstånd_m'] = lekplatser.apply(
    lambda row: närmaste_avstånd(row['lat'], row['lon'], hållplatser), axis=1
)

lekplatser['avstånd_toalett'] = lekplatser.apply(
    lambda row: närmaste_toalett_avstånd(row['lat'], row['lon'], toaletter_df), axis=1
)

st.sidebar.markdown("### Klustringsmetod")
klustringsval = st.sidebar.radio(
    "Välj vad lekplatserna ska grupperas utifrån:",
    options=["Hållplatsavstånd", "Toalettavstånd", "Både hållplats + toalett"],
    index=0
)

# --- Visa filtreringsgränssnitt ENDAST för hållplatsavstånd ---
if klustringsval == "Hållplatsavstånd":
    valda_hållplatsnamn = st.sidebar.selectbox(
        "Filtrera lekplatser nära en viss hållplats:",
        options=hållplatser['name'].sort_values().unique(),
        index=None,
        placeholder="Välj en hållplats"
    )
    radie = st.sidebar.slider(
        "Avståndsradie (meter)",
        min_value=100, max_value=2000, value=500, step=100
    )
else:
    # Ingen filtrering
    valda_hållplatsnamn = None
    radie = None

#Dynamisk rubrik ovanför kartan
rubrik_text = {
    "Hållplatsavstånd": "**Denna karta visar lekplatser färgkodade efter avstånd till närmaste hållplats.**",
    "Toalettavstånd": "**Denna karta visar lekplatser färgkodade efter avstånd till närmaste toalett.**",
    "Både hållplats + toalett": "**Denna karta visar lekplatser färgkodade efter kombinerad tillgång till hållplats och toalett.**",
}
st.markdown(rubrik_text[klustringsval])

# --- Klustring och färger ---
# Välj variabler beroende på klustringsval
if klustringsval == "Hållplatsavstånd":
    X = lekplatser[['avstånd_m']].dropna().values
elif klustringsval == "Toalettavstånd":
    X = lekplatser[['avstånd_toalett']].dropna().values
else:  # Både
    X = lekplatser[['avstånd_m', 'avstånd_toalett']].dropna().values

# Skala
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Klustring
n_clusters = 4 if klustringsval == "Hållplatsavstånd" else 5
kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init='auto').fit(X_scaled)

# Om du har droppat rader, uppdatera även lekplatser (detta behövs bara om du använder X_scaled direkt med annan df)
lekplatser = lekplatser.dropna(subset=['avstånd_m', 'avstånd_toalett']).copy()
lekplatser['kluster'] = kmeans.labels_

# --- Sortera kluster baserat på medelavstånd till hållplats eller annan logik ---
if klustringsval == "Hållplatsavstånd":
    kluster_medel = lekplatser.groupby('kluster')['avstånd_m'].mean().sort_values()
elif klustringsval == "Toalettavstånd":
    kluster_medel = lekplatser.groupby('kluster')['avstånd_toalett'].mean().sort_values()
else:
    # Kombinera avstånd till både hållplats och toalett
    lekplatser['combo'] = lekplatser['avstånd_m'] + lekplatser['avstånd_toalett']
    kluster_medel = lekplatser.groupby('kluster')['combo'].mean().sort_values()

# --- Tilldela färger dynamiskt ---
tillgängliga_färger = ['green', 'orange', 'red', 'purple', 'black']
färger_sorterade = tillgängliga_färger[:n_clusters]
färgkarta = {kluster: färger_sorterade[i] for i, kluster in enumerate(kluster_medel.index)}
lekplatser['färg'] = lekplatser['kluster'].map(färgkarta)

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
        if klustringsval == "Hållplatsavstånd":
            popup_text = f"<strong>{rad['name']}</strong><br> {int(rad['avstånd_m'])} m till närmaste hållplats<br>{uppskattad_gångtid(rad['avstånd_m'])}"
        elif klustringsval == "Toalettavstånd":
            popup_text = f"<strong>{rad['name']}</strong><br> {int(rad['avstånd_toalett'])} m till toalett<br>{uppskattad_gångtid(rad['avstånd_toalett'])}"
        else:
            popup_text = (
                f"<strong>{rad['name']}</strong><br>"
                f"{int(rad['avstånd_m'])} m till närmaste hållplats {uppskattad_gångtid(rad['avstånd_m'])}<br>"
                f"{int(rad['avstånd_toalett'])} m till toalett {uppskattad_gångtid(rad['avstånd_toalett'])}"
            )

        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=popup_text,
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
        if klustringsval == "Hållplatsavstånd":
            popup_text = f"<strong>{rad['name']}</strong><br> {int(rad['avstånd_m'])} m till närmaste hållplats<br> {uppskattad_gångtid(rad['avstånd_m'])}"
        elif klustringsval == "Toalettavstånd":
            popup_text = f"<strong>{rad['name']}</strong><br> {int(rad['avstånd_toalett'])} m till toalett<br> {uppskattad_gångtid(rad['avstånd_toalett'])}"
        else:
            popup_text = (
                f"<strong>{rad['name']}</strong><br>"
                f"{int(rad['avstånd_m'])} m till närmaste hållplats {uppskattad_gångtid(rad['avstånd_m'])}<br>"
                f"{int(rad['avstånd_toalett'])} m till toalett {uppskattad_gångtid(rad['avstånd_toalett'])}"
            )

        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=popup_text,
            icon=folium.Icon(color=rad['färg'], icon='child', prefix='fa')
        ).add_to(karta)

if klustringsval != "Toalettavstånd":
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

# Visa toaletter om relevant
# Visa toaletter inom vald radie om relevant
if valda_hållplatsnamn and ("Toalett" in klustringsval or "både" in klustringsval.lower()):
    # Beräkna avstånd från toaletter till vald hållplats
    toaletter_df['avstånd_till_vald'] = toaletter_df.apply(
        lambda row: geodesic((row['lat'], row['lon']), vald_position).meters, axis=1
    )
    toaletter_nära = toaletter_df[toaletter_df['avstånd_till_vald'] <= radie].copy()

    for _, rad in toaletter_nära.iterrows():
        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=f"Toalett ({int(rad['avstånd_till_vald'])} m från hållplats)",
            icon=folium.Icon(color='gray', icon='restroom', prefix='fa')
        ).add_to(karta)
else:
    # Visa alla toaletter om ingen hållplats vald men toalett ingår i klustringsval
    if "Toalett" in klustringsval or "både" in klustringsval.lower():
        for _, rad in toaletter_df.iterrows():
            folium.Marker(
                location=(rad['lat'], rad['lon']),
                popup="Toalett",
                icon=folium.Icon(color='gray', icon='restroom', prefix='fa')
            ).add_to(karta)

# --- Dynamisk legend ---
if klustringsval == "Hållplatsavstånd":
    kluster_max = lekplatser.groupby('kluster')['avstånd_m'].max()
    beskrivningstyp = "till hållplats"
    kluster_beskrivning = {
    färgkarta[kl]: f"max {uppskattad_gångtid(kluster_max[kl])} {beskrivningstyp}" for kl in kluster_max.index
}
elif klustringsval == "Toalettavstånd":
    kluster_max = lekplatser.groupby('kluster')['avstånd_toalett'].max()
    beskrivningstyp = "till toalett"
    kluster_beskrivning = {
    färgkarta[kl]: f"max {uppskattad_gångtid(kluster_max[kl])} {beskrivningstyp}" for kl in kluster_max.index
}
else:
    # Kombinationen hållplats + toalett
    beskrivningstyp = "kombinerad tillgång till hållplats och toalett"
    kvalitetsnivåer = {
        0: "Enkel att nå, bekvämt belägen",
        1: "Tillgänlig men ej optimal",
        2: "Promenadavstånd",
        3: "Ligger en bit bort",
        4: "Avlägsen"
    }
    kluster_beskrivning = {
        färgkarta[kl]: kvalitetsnivåer.get(i, "") for i, kl in enumerate(kluster_medel.index)
    }

legend_html = "<div class='lekplats-legend'>"#"<div style='background-color:#f0f0f0;padding:10px;border-radius:10px;border:1px solid #ccc;font-size:15px; color: black;'>"
for färg in färger_sorterade:
    text = kluster_beskrivning.get(färg, "")
for färg in färger_sorterade:
    text = kluster_beskrivning.get(färg, "")
    emoji = {
        'green': "<img src='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png' width='20px'>",
        'orange': "<img src='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png' width='20px'>",
        'red': "<img src='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png' width='20px'>",
        'purple': "<img src='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-violet.png' width='20px'>",
        'black': "<img src='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-black.png' width='20px'>"
    }.get(färg, "")
   
    legend_html += f"{emoji} Lekplats ({text})<br>"
legend_html += "🔵 Hållplats<br>"
if klustringsval in ["Toalettavstånd", "Både hållplats + toalett"]:
    legend_html += "🚻 Toalett<br>"
legend_html += "</div>"

col1, _ = st.columns([3, 1])
with col1:
    folium_static(karta)
    st.markdown(legend_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

with st.expander("Om HackStreet Boys"):
    st.markdown("""
**Om applikationen**  
Version: 1.0  
Senast uppdaterad: 22 maj 2025  


**Utvecklare**  
Victoria Johansson, Lina Axelson, Eleonor Borgqvist, Ebba Reis, Ella Anderzén och Jonna Wadman 
Studenter vid Göteborgs universitet  

**Datakällor**  
- GTFS-data från Västtrafik (via KoDa-dataset från Trafiklab)  
- Lekplatsdata från OpenStreetMap (OSM)  

**Teknisk information**  
- Kartan visar endast lekplatser och hållplatser inom området:  
  **lat:** 57.5–57.85, **lon:** 11.7–12.1  
- Gångtid beräknas med en genomsnittlig hastighet på **5 km/h**

**Kontakt & feedback**  
Har du frågor, förslag, hittat en bugg eller vill veta mer?  
Kontakta: [victoriaj0109@outlook.com](mailto:victoriaj0109@outlook.com)  
GitHub: [group-project-hackstreet-boys](https://github.com/SVP-GU/group-project-hackstreet-boys)
    """, unsafe_allow_html=True)