from flask import Flask, request, jsonify
from minio_access import url_object, download_object, list_objects


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

@app.route('/minio_get_url', methods=['GET'])
def get_minio_url():
    file_name = request.args.get('file_name')  
    print("Received request to obtain URL by accessing minio for node:", file_name)
    url = url_object(bucket_name='pcap-ferro', object_name=file_name) # Obs: Hard-coded bucket name
    return jsonify({'url': url})

@app.route('/minio_download', methods=['GET'])
def minio_download():
    file_name = request.args.get('file_name')
    download_path = "./temp/sample.pcap" # Obs: Hard-coded path
    print(f"Received request to download minio data for node {file_name}, and save on path: {download_path}")
    download_object(bucket_name='pcap-ferro', object_name=file_name, file_path=download_path, ) # Obs: Hard-coded bucket name
    # Return status
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
