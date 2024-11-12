import requests, json
bucket_name = "pcap-ferro"
params = {
    'bucket_name': bucket_name,
}
url = "http://localhost:5000/minio_list_objects"
response = requests.get(url, params=params)
with open('example.json', 'w') as json_file:
        json.dump(response.json(), json_file, indent=4)