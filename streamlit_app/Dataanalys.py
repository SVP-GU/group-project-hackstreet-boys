import pandas as pd
import json
import os
from geopy.distance import geodesic
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

# === 1. Ladda data ===
current_dir = os.path.dirname(os.path.abspath(__file__))
lekplats_path = os.path.join(current_dir, "lekplatser_ny.json")
with open(lekplats_path, "r", encoding="utf-8") as f:
    lekplatser_data = json.load(f)

lekplatser_df = pd.DataFrame([{
    'name': el.get('tags', {}).get('name', 'Okänd lekplats'),
    'lat': el['lat'],
    'lon': el['lon']
} for el in lekplatser_data])

stop_df = pd.read_csv(os.path.join(current_dir, "stops.txt"))
stop_df = stop_df[
    (stop_df['stop_lat'] >= 57.5) & (stop_df['stop_lat'] <= 57.85) &
    (stop_df['stop_lon'] >= 11.7) & (stop_df['stop_lon'] <= 12.1)
].drop_duplicates(subset='stop_name')
stop_df = stop_df.rename(columns={'stop_lat': 'lat', 'stop_lon': 'lon'})

toalett_path = os.path.join(current_dir, "toaletter.json")
with open(toalett_path, "r", encoding="utf-8") as f:
    toaletter_data = json.load(f)

toaletter_df = pd.DataFrame([{
    'lat': el['lat'],
    'lon': el['lon']
} for el in toaletter_data])

# === 2. Beräkna avstånd ===
def närmaste_avstånd(lat, lon, platser_df):
    pos = (lat, lon)
    return min(geodesic(pos, (r['lat'], r['lon'])).meters for _, r in platser_df.iterrows())

lekplatser_df['dist_hållplats'] = lekplatser_df.apply(lambda row: närmaste_avstånd(row['lat'], row['lon'], stop_df), axis=1)
lekplatser_df['dist_toalett'] = lekplatser_df.apply(lambda row: närmaste_avstånd(row['lat'], row['lon'], toaletter_df), axis=1)
lekplatser_df['dist_kombi'] = lekplatser_df['dist_hållplats'] + lekplatser_df['dist_toalett']

# === 3. Klusteranalys med olika features ===
features_dict = {
    'Hållplatser': ['dist_hållplats'],
    'Toaletter': ['dist_toalett'],
    'Kombinerat': ['dist_hållplats', 'dist_toalett']
}

for feature_name, cols in features_dict.items():
    print(f"\n==== {feature_name.upper()} ====")

    X = lekplatser_df[cols].copy()
    X_scaled = StandardScaler().fit_transform(X)

    inertias = []
    silhouettes = []
    ks = range(2, 11)

    for k in ks:
        kmeans = KMeans(n_clusters=k, n_init="auto", random_state=0)
        cluster_labels = kmeans.fit_predict(X_scaled)
        inertias.append(kmeans.inertia_)
        silhouette_avg = silhouette_score(X_scaled, cluster_labels)
        silhouettes.append(silhouette_avg)

    # === Plotting ===
    plt.figure()
    plt.plot(ks, inertias, marker='o')
    plt.title(f'Elbow-plot för {feature_name}')
    plt.xlabel('Antal kluster (k)')
    plt.ylabel('Inertia')

    plt.figure()
    plt.plot(ks, silhouettes, marker='o', color='green')
    plt.title(f'Silhouette-värden för {feature_name}')
    plt.xlabel('Antal kluster (k)')
    plt.ylabel('Silhouette score')

plt.show()