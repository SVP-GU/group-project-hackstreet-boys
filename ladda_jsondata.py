import requests
import pandas as pd
import json

query = """
[out:json];
node["leisure"="playground"](57.5,11.7,57.85,12.1);
out body;
"""

url = "http://overpass-api.de/api/interpreter"
respones = requests.get(url, params={"data": query})
playground = respones.json()

#Filtrera bort lekplatser där access = "private"
filtered_elements = [
    el for el in playground["elements"]
    if not(el.get("tags", {}).get("access") =="private")
]

with open("lekplatser_ny.json", "w", encoding="utf-8") as f:
    json.dump(filtered_elements, f, ensure_ascii=False, indent=2)


print("Filen 'lekplatser_ny.json' har sparats.")