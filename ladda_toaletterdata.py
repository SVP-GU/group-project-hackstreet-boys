import requests
import pandas as pd
import json

query = """
[out:json];
node["amenity"="toilets"](57.5,11.7,57.85,12.1);
out body;
"""

url = "http://overpass-api.de/api/interpreter"
response = requests.get(url, params={"data": query})
toilets = response.json()

with open("toaletter.json", "w", encoding="utf-8") as f:
    json.dump(toilets["elements"], f, ensure_ascii=False, indent=2)

print("Filen 'toaletter.json' har sparats.")