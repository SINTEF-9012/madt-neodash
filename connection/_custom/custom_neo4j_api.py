import requests, json
query = "MATCH (a:ASSET)-[r:ControlledBy]->(b:ASSET) RETURN a.name as ControlledAsset, b.name as ControlAsset"
params = {
    'query': query,
}
url = "http://localhost:5001/neo4j_get_data"
response = requests.get(url, params=params)
with open('example.json', 'w') as json_file:
        json.dump(response.json(), json_file, indent=4)

