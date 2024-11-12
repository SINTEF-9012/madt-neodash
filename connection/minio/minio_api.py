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
    download_dir = "./temp"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"[minio_api.py] Received request to locally download MinIO data for latest file in bucket: ", bucket_name, " and save on path: ", download_dir)
    download_last_object(bucket_name=bucket_name, file_path=download_dir) 
    return jsonify({'status': 200})

@app.route('/minio_update_database', methods=['GET'])
def minio_update_database():
    bucket_name = request.args.get('asset_id')
    bucket_name = bucket_name.lower() # Bucket names are always low cased
    topic = request.args.get('topic')
    if topic == None or topic == "":
        print(f"[minio_api.py] Error: topic not found. Update endpoint of asset with topic name.")
        return jsonify({'status': 500})
    print(f"[minio_api.py] Received request to update bucket: ", bucket_name, " with latest message from kafka topic: ", topic)
    try:
        # Kafka consumer setup
        consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[config.get('kafka', 'bootstrap_servers')],
                security_protocol=config.get('kafka', 'security_protocol'),
                sasl_mechanism=config.get('kafka', 'sasl_mechanism'),
                sasl_plain_username=config.get('kafka', 'sasl_plain_username'),
                sasl_plain_password=config.get('kafka', 'sasl_plain_password'),
                auto_offset_reset=config.get('kafka', 'auto_offset_reset'),  # Start reading at the earliest message
                enable_auto_commit=True,        # Automatically commit offsets
                value_deserializer=lambda x: x.decode('utf-8')  # Deserialize messages to string
        )
        """
        # Assuming you want to do something with the messages
        for message in consumer:
            print(f'Received message: {message.value} from partition: {message.partition}, offset: {message.offset}')
            break  # TODO modify this based on your use case
        return jsonify({'status': 200})
        """
        # Process messages
        messages = [msg.value for msg in consumer]
        if not messages:
            print(f"[minio_api.py] No messages in broker. Returning.")
            return jsonify({'status': 200})

        # Save the last message to a temporary file and upload it
        last_message = messages[-1]
        with tempfile.NamedTemporaryFile(delete=False, mode='w+') as tmp:
            tmp.write(last_message)
            tmp_path = tmp.name
        
        # Upload to MinIO
        uploaded = upload_object(asset_id, 'last_message.txt', tmp_path)
        os.unlink(tmp_path)  # Clean up the temporary file
        if uploaded:
            print(f"[minio_api.py] Object uploaded successfully.")
            return jsonify({'status': 200})
        else:
            print(f"[minio_api.py] Object could not be uploaded.")
            return jsonify({'status': 500})
    except Exception as e:
        return jsonify({'status': 500})

#@app.route('/test')
#def test():
#    print("Test route accessed")
#    return "Server is running"

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
