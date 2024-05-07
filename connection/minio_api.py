from flask import Flask, request, jsonify
from minio_access import download_last_object, get_url_last_object, list_objects


app = Flask(__name__)

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'  # allowed origin
    response.headers['Access-Control-Allow-Methods'] = 'GET'  # Adjust as needed
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Apply the CORS function to all routes using the after_request decorator
@app.after_request
def apply_cors(response):
    return add_cors_headers(response)

@app.route('/minio_get_last_url', methods=['GET'])
def minio_get_last_url():
    endpoint = request.args.get('endpoint')
    print("[minio_api.py] Received request to fetch latest object from bucket: "+ endpoint)
    url = get_url_last_object(bucket_name=endpoint) 
    return jsonify({'url': url})

@app.route('/minio_local_download', methods=['GET'])
def minio_local_download():
    endpoint = request.args.get('endpoint')
    download_path = "./temp/sample.pcap" # Obs: Hard-coded path
    print(f"[minio_api.py] Received request to locally download MinIO data for latest file in bucket: ", endpoint, " and save on path: ",download_path)
    download_last_object(bucket_name='endpoint', file_path=download_path) 
    return jsonify({'status': 200})

# - - - - -  - - - - -   - - - - -  Add more customized functions here: - - - - -   - - - - -   - - - - - 
@app.route('/minio_list_objects', methods=['GET'])
def minio_list_objects():
    bucket_name = request.args.get('bucket_name')  
    objects = list_objects(bucket_name=bucket_name)
    object_list = list(objects)
    object_list = [object.object_name for object in object_list]
    print(object_list)
    return jsonify({'objects': object_list})

if __name__ == '__main__':
    app.run(host="localhost", port=5000)
