from flask import Flask, request, jsonify
from minio_access import download_last_object, get_url_last_object, list_objects, upload_object
import os
from kafka import KafkaConsumer
import configparser
import tempfile


app = Flask(__name__)

# Load configurations from .ini file
config = configparser.ConfigParser()
config.read('kafka_config.ini')

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://0.0.0.0:3000'  # allowed origin
    response.headers['Access-Control-Allow-Methods'] = 'GET'  # Adjust as needed
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Apply the CORS function to all routes using the after_request decorator
@app.after_request
def apply_cors(response):
    return add_cors_headers(response)

@app.route('/minio_get_last_url', methods=['GET'])
def minio_get_last_url():
    bucket_name = request.args.get('endpoint')
    bucket_name = bucket_name.lower() # Bucket names are always low cased
    print("[minio_api.py] Received request to fetch latest object from bucket: " + bucket_name)
    url = get_url_last_object(bucket_name = bucket_name) 
    return jsonify({'url': url})

@app.route('/minio_local_download', methods=['GET'])
def minio_local_download():
    bucket_name = request.args.get('endpoint')
    bucket_name = bucket_name.lower() # Bucket names are always low cased
    # Create temp dir if not present from before:
    download_dir = "./downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"[minio_api.py] Received request to locally download MinIO data for latest file in bucket: ", bucket_name, " and save on path: ", download_dir)
    download_last_object(bucket_name=bucket_name, file_path=download_dir) 
    return jsonify({'status': 200})

@app.route('/minio_upload_file', methods=['POST'])
def minio_upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 400})
    file = request.files['file']
    asset_id = request.form.get('asset_id')
    asset_id = asset_id.lower() # Bucket names are always low cased
    print(f"[minio_api.py] Received request to load file {file.filename} to bucket {asset_id}")
    # Process the file as needed (e.g., save to database or storage)
    download_dir = "./downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    # Save the file locally
    file_path = os.path.join(download_dir, file.filename)
    file.save(file_path)
    try:
        # Upload file to MinIO
        upload_object(asset_id, file.filename, file_path)
    except Exception as e:
        return jsonify({'status': 500, 'error': 'Failed to upload to MinIO', 'details': str(e)}), 500
    finally:
        # Clean up the temporary file after upload
        if os.path.exists(file_path):
            os.remove(file_path)
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
    app.run(host="0.0.0.0", port=5000)
