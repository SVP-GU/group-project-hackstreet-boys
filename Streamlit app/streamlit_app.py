import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import json
from geopy.distance import geodesic
from sklearn.cluster import KMeans
import os

# --- Sidhuvud ---
st.set_page_config(page_title="Göteborgs lekplatskarta", layout="wide")
st.title("Göteborgs lekplatskarta")

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

# --- Läs toaletter ---
with open(os.path.join(current_dir, "toaletter.json"), "r", encoding="utf-8") as f:
    toaletter_data = json.load(f)

toaletter_df = pd.DataFrame([{
    'lat': el['lat'],
    'lon': el['lon'],
} for el in toaletter_data])

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

#Beräkna avstånd till närmast toalett
def närmaste_toalett_avstånd(lat, lon, toaletter):
    pos = (lat, lon)
    return min(geodesic(pos, (r['lat'], r['lon'])).meters for _, r in toaletter.iterrows())

lekplatser['avstånd_toalett'] = lekplatser.apply(
    lambda row: närmaste_toalett_avstånd(row['lat'], row['lon'], toaletter_df), axis=1
)

# --- Sidopanel: filtreringsgränssnitt ---
valda_hållplatsnamn = st.sidebar.selectbox(
    "Filtrera lekplatser nära en viss hållplats:",
    options=hållplatser['name'].sort_values().unique(),
    index=None,
    placeholder="Välj en hållplats"
)
radie = st.sidebar.slider("Avståndsradie (meter)", 100, 2000, 500, step=100)

st.sidebar.markdown("### Klustringsmetod")
klustringsval = st.sidebar.radio(
    "Välj vad lekplatserna ska klustras utifrån:",
    options=["Hållplatsavstånd", "Toalettavstånd", "Både hållplats + toalett"],
    index=0
)

# --- Klustring och färger ---

from sklearn.preprocessing import StandardScaler

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
            popup_text = f"{rad['name']}<br> {int(rad['avstånd_m'])} m till hållplats<br>{uppskattad_gångtid(rad['avstånd_m'])}"
        elif klustringsval == "Toalettavstånd":
            popup_text = f"{rad['name']}<br> {int(rad['avstånd_toalett'])} m till toalett<br>{uppskattad_gångtid(rad['avstånd_toalett'])}"
        else:
            popup_text = (
                f"{rad['name']}<br>"
                f"{int(rad['avstånd_m'])} m till hållplats {uppskattad_gångtid(rad['avstånd_m'])}<br>"
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
            popup_text = f"{rad['name']}<br> {int(rad['avstånd_m'])} m till hållplats<br> {uppskattad_gångtid(rad['avstånd_m'])}"
        elif klustringsval == "Toalettavstånd":
            popup_text = f"{rad['name']}<br> {int(rad['avstånd_toalett'])} m till toalett<br> {uppskattad_gångtid(rad['avstånd_toalett'])}"
        else:
            popup_text = (
                f"{rad['name']}<br>"
                f"{int(rad['avstånd_m'])} m till hållplats {uppskattad_gångtid(rad['avstånd_m'])}<br>"
                f"{int(rad['avstånd_toalett'])} m till toalett {uppskattad_gångtid(rad['avstånd_toalett'])}"
            )

        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup=popup_text,
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

# Visa toaletter om relevant
if "Toalett" in klustringsval or "både" in klustringsval.lower():
    for _, rad in toaletter_df.iterrows():
        folium.Marker(
            location=(rad['lat'], rad['lon']),
            popup="Toalett",
            icon=folium.Icon(color='cadetblue', icon='restroom', prefix='fa')
        ).add_to(karta)

# --- Dynamisk legend ---
if klustringsval == "Hållplatsavstånd":
    kluster_max = lekplatser.groupby('kluster')['avstånd_m'].max()
    beskrivningstyp = "till hållplats"
    kluster_beskrivning = {
    färgkarta[kl]: f"max {int(kluster_max[kl])}m ({uppskattad_gångtid(kluster_max[kl])}) {beskrivningstyp}" for kl in kluster_max.index
}
elif klustringsval == "Toalettavstånd":
    kluster_max = lekplatser.groupby('kluster')['avstånd_toalett'].max()
    beskrivningstyp = "till toalett"
    kluster_beskrivning = {
    färgkarta[kl]: f"max {int(kluster_max[kl])}m ({uppskattad_gångtid(kluster_max[kl])}) {beskrivningstyp}" for kl in kluster_max.index
}
else:
    # Kombinationen hållplats + toalett
    beskrivningstyp = "kombinerad tillgång till hållplats och toalett"
    kvalitetsnivåer = {
        0: "Mycket nära både hållplats och toalett",
        1: "Nära båda",
        2: "Medelnära båda",
        3: "Längre bort till minst en",
        4: "Långt till båda"
    }
    kluster_beskrivning = {
        färgkarta[kl]: kvalitetsnivåer.get(i, "") for i, kl in enumerate(kluster_medel.index)
    }

legend_html = "<div style='background-color:#f0f0f0;padding:10px;border-radius:10px;border:1px solid #ccc;font-size:15px; color: black;'>"
for färg in färger_sorterade:
    text = kluster_beskrivning.get(färg, "")
    emoji = {
        'green': "🟢", 'orange': "🟠", 'red': "🔴", 'purple': "🟣", 'black': "⚫"
    }.get(färg, "⬤")
    legend_html += f"{emoji} Lekplats ({text})<br>"
legend_html += "🔵 Hållplats<br>"
if klustringsval in ["Toalettavstånd", "Både hållplats + toalett"]:
    legend_html += "🟦 Toalett<br>"
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
Senast uppdaterad: 21 maj 2025  

**Utvecklare**  
Victoria Johansson, Lina Axelson, Eleonor Borgqvist, Ebba Reis och Ella Anderzén  
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
