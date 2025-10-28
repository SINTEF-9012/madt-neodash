from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import csv
import os
import json
from kafka import KafkaConsumer, OffsetAndMetadata, TopicPartition
from threading import Thread, Event
import configparser
import time

# Load configurations from .ini files
config_kafka = configparser.ConfigParser()
config_kafka.read('kafka_config.ini')

config_influxdb = configparser.ConfigParser()
config_influxdb.read('influxdb_config.ini')


# Global variables
mapping_path = os.path.join("downloads", "topic_mapping.json")
mapping_stop_event = Event()
mapping_listener_threads = {}
last_mapping_content = ""

app = Flask(__name__)

client = InfluxDBClient(url=config_influxdb.get('influxdb','INFLUXDB_URL'), token=config_influxdb.get('influxdb','INFLUXDB_TOKEN'), org=config_influxdb.get('influxdb','INFLUXDB_ORG'))

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'  # allowed origin
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'  # Adjust as needed
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Apply the CORS function to all routes using the after_request decorator
@app.after_request
def apply_cors(response):
    return add_cors_headers(response)


def load_mapping_file():
    """Loads the mapping JSON file and returns its contents and raw string."""
    if not os.path.exists(mapping_path):
        print("[influxdb_api.py] topic_mapping.json not found.")
        return {}, ""
    with open(mapping_path, "r") as f:
        content = f.read().strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            print("[influxdb_api.py] Invalid JSON in mapping file.")
            return {}, content
    return data, content

def stop_influx_listeners():
    """Stops all running influxdb_realtime_upload threads."""
    global mapping_listener_threads
    if not mapping_listener_threads:
        return
    print("[influxdb_api.py] Stopping all active InfluxDB upload listeners...")
    for topic_uid, thread_info in mapping_listener_threads.items():
        stop_event = thread_info["stop_event"]
        stop_event.set()
    for topic_uid, thread_info in mapping_listener_threads.items():
        thread = thread_info["thread"]
        thread.join(timeout=5)
        print(f"[influxdb_api.py] Listener {topic_uid} stopped.")
    mapping_listener_threads.clear()

def start_influx_listeners(topic_uid_dict):
    """Starts influxdb_realtime_upload threads for each topic/uid pair."""
    global mapping_listener_threads
    print("[influxdb_api.py] Starting new InfluxDB listeners...")
    for topic, uid_list in topic_uid_dict.items():
        for uid in uid_list:
            stop_event = Event()
            thread = Thread(target=influxdb_realtime_upload, args=(topic, uid, stop_event))
            thread.start()
            mapping_listener_threads[(topic, uid)] = {"thread": thread, "stop_event": stop_event}
            print(f"[influxdb_api.py] Listener started for topic={topic}, uid={uid}")

def watch_topic_mapping():
    """Continuously watches the mapping file and restarts listeners when content changes."""
    global last_mapping_content
    print("[influxdb_api.py] Watching topic_mapping.json for changes...")
    while not mapping_stop_event.is_set():
        topic_uid_dict, new_content = load_mapping_file()
        if new_content and new_content != last_mapping_content:
            print("[influxdb_api.py] 🔄 topic_mapping.json content changed — reloading listeners...")
            last_mapping_content = new_content
            stop_influx_listeners()
            if topic_uid_dict:
                start_influx_listeners(topic_uid_dict)
            else:
                print("[influxdb_api.py] Mapping file empty or invalid.")
        time.sleep(5)  # Check every 5 seconds

def get_unique_filepath(directory, filename):
    base, ext = os.path.splitext(filename)
    file_path = os.path.join(directory, filename)
    counter = 1
    # Keep checking until the filename is unique
    while os.path.exists(file_path):
        new_filename = f"{base}_{counter}{ext}"
        file_path = os.path.join(directory, new_filename)
        counter += 1
    return file_path

def normalize_time(t: str) -> str:
    # Ensure 'Z' at the end for UTC; add seconds if missing
    if not t.endswith("Z"):
        if len(t.split(":")) == 2:  # only hours and minutes
            t += ":00Z"
        elif len(t.split(":")) == 3 and not t.endswith("Z"):
            t += "Z"
    return t

@app.route('/influxdb_download_data', methods=['GET'])
def influxdb_download_data():
    bucket_id = request.args.get('endpoint')
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    # Check if bucket is valid:
    buckets_api = client.buckets_api()
    bucket_list = buckets_api.find_buckets().buckets
    bucket_names = [bucket.name for bucket in bucket_list]
    if bucket_id not in bucket_names:
        print(f"[influxdb_api.py] Bucket {bucket_id} not found.")
        return jsonify({
            'error': 'InfluxDB API error',
        }), 500 
    
    print("[influxdb_api.py] InfluxDB processes query from asset with uid " + bucket_id)
    query_api = client.query_api()

    # TODO Convert date format to compatible one (Obs: UTC, if not UTC -> adjust!)
    converted_start_time = normalize_time(start_time) #f"{start_time}:00Z"
    converted_end_time = normalize_time(end_time) #f"{end_time}:00Z"

    # Complete Flux query
    query = f"""
    from(bucket: "{bucket_id}")
    |> range(start: {converted_start_time}, stop: {converted_end_time})
    """
    print(query)

    try:
        # Execute the query
        result = query_api.query(org=config_influxdb.get("influxdb", "INFLUXDB_ORG"), query=query)
        # Define the CSV file path
        file_path = './downloads'
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        filename = "influxdb_outputs.csv"
        file_path = get_unique_filepath(file_path, filename)
        #file_path = os.path.join(file_path, "influxdb_outputs.csv")
        # Open a file to write and save locally
        with open(file_path, mode='w', newline='') as file:
            fieldnames = ['timestamp', 'measurement', 'field', 'value']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            # Write the header
            writer.writeheader()
            # Process and write data to CSV
            for table in result:
                for record in table.records:
                    writer.writerow({
                        "timestamp": record.get_time(),
                        "measurement": record.get_measurement(),
                        "field": record.get_field(),
                        "value": record.get_value(),
                    })
        # Process the results
        output = []
        for table in result:
            for record in table.records:
                output.append({
                    "timestamp": record.get_time(),
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
            })
        # Close the client
        # client.close()
        print("[influxdb_api.py] InfluxDB query request processed for asset with id " + bucket_id)
        return jsonify({
            'file_path': file_path,
            'filename' : os.path.basename(file_path),
            'output': output})
    except Exception as e:
        print(f"[influxdb_api.py] Unexpected error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/influxdb_add_bucket', methods=['POST'])
def influxdb_add_bucket():
    # Extract JSON data from the request body
    data = request.get_json()
    # Retrieve the bucket name from the JSON payload
    bucket_id = data.get('bucket') if data else None
    if not bucket_id:
        return jsonify({"error": "Bucket ID is missing in the request."}), 400
    print("[influxdb_api.py] InfluxDB requested to add bucket with ID " + bucket_id)
    # Get the Buckets API
    buckets_api = client.buckets_api()
    retention_rules = []  # Define retention rules (default: indefinitely)
    try:
        bucket = buckets_api.create_bucket(
            bucket_name=bucket_id, 
            org_id=config_influxdb.get('influxdb', 'INFLUXDB_ORG'),
            retention_rules=retention_rules
        )
    except Exception as e:
        print(f"[influxdb_api.py] Error creating bucket {bucket_id}: {e}")
        return jsonify({"error": str(e)}), 500
    print(f"[influxdb_api.py] Bucket {bucket.name} created with ID: {bucket.id}")
    return jsonify({'status': 200})

# Alternatively to /influxdb_add_bucket above, use the following GET method: 
@app.route('/influxdb_create_bucket', methods=['GET'])
def influxdb_create_bucket():
    # Get the Buckets API
    bucket_id = request.args.get('bucket_id')
    print("[influxdb_api.py] InfluxDB requested to add bucket with ID " + bucket_id)
    buckets_api = client.buckets_api()
    retention_rules = []  # Define retention rules, default: indefinitely
    bucket = buckets_api.create_bucket(bucket_name=bucket_id, org_id=config_influxdb.get('influxdb','INFLUXDB_ORG'), retention_rules=retention_rules)
    # Close the client
    # client.close()
    print(f"[influxdb_api.py] Bucket {bucket.name} created with ID: {bucket.id}")
    return jsonify({'status': 200})


def check_and_create_bucket(bucket_id):
    buckets_api = client.buckets_api()
    bucket_list = buckets_api.find_buckets().buckets
    bucket_names = [bucket.name for bucket in bucket_list]
    if bucket_id not in bucket_names:
        print(f"[influxdb_api.py] Bucket {bucket_id} not found, creating new bucket.")
        buckets_api.create_bucket(bucket_name=bucket_id, org_id=config_influxdb.get('influxdb', 'INFLUXDB_ORG'))

def dynamic_data_parser(data, point, parent_key=''):
    for key, value in data.items():
        compound_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            dynamic_data_parser(value, point, compound_key)
        elif isinstance(value, list):
            if all(isinstance(item, (str, int, float, bool)) for item in value):
                processed_items = []
                for item in value:
                    if type(item) is int:  # convert only if type is exactly int
                        processed_items.append(float(item))
                    else:
                        processed_items.append(item)
                # Join the items into a comma-separated string.
                point.field(compound_key, ','.join(map(str, processed_items)))
            else:
                # If list contains complex items, store the JSON string.
                point.field(compound_key, json.dumps(value))
        else:
            # Convert ints (where type is exactly int) to float.
            if type(value) is int:
                value = float(value)
            # Decide whether to add the value as a tag or a field.
            if isinstance(value, str) and len(value) < 50:
                point.tag(compound_key, value)
            elif isinstance(value, (float, bool)):
                point.field(compound_key, value)
            elif isinstance(value, str):
                point.field(compound_key, value)
            else:
                point.field(compound_key, str(value))

def metricbeat_data_parser(data_dict, point):
    """
    Parses one line of Metricbeat output and returns a Point for InfluxDB.
    """
    timestamp = data_dict.get("@timestamp")
    # Set timestamp if available
    if timestamp:
        point.time(datetime.fromisoformat(timestamp.replace("Z", "+00:00")))
    # Flatten and populate point with tags/fields
    dynamic_data_parser(data_dict, point)

def ocpp_data_parser(data_dict, point):
    """
    Parses an OCPP flowmeter JSON line into an InfluxDB Point.
    """
    # Extract and validate timestamp
    ts_str = data_dict.get("Timestamp")
    if ts_str:
        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    else:
        raise ValueError("[influxdb_api.py] Missing Timestamp in OCPP data")
    point.time(timestamp)
    # Add identifying tags
    point.tag("flow_id", data_dict.get("flow_id", "unknown"))
    point.tag("src_ip", data_dict.get("src_ip", "unknown"))
    point.tag("dst_ip", data_dict.get("dst_ip", "unknown"))
    point.tag("label", data_dict.get("label", "unknown"))
    # Add all numeric fields as InfluxDB fields
    for key, value in data_dict.items():
        if key in {"flow_id", "Timestamp", "src_ip", "dst_ip", "label"}:
            continue  # already handled
        if isinstance(value, (int, float)):
            point.field(key, float(value))  # int → float for InfluxDB

def cic_data_parser(data_dict, point):
    """
    Parses one line of CICFlowMeter JSON and returns an InfluxDB Point.
    """
    # Ensure timestamp is available
    ts_str = data_dict.get("Timestamp")
    if not ts_str:
        raise ValueError("[influxdb_api.py] Missing Timestamp in CICFlowMeter data")
    timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

    # Start building point
    point.time(timestamp)

    # Add tags
    point.tag("flow_id", data_dict.get("Flow ID", "unknown"))
    point.tag("src_ip", data_dict.get("Src IP", "unknown"))
    point.tag("dst_ip", data_dict.get("Dst IP", "unknown"))
    point.tag("src_port", str(data_dict.get("Src Port", "0")))
    point.tag("dst_port", str(data_dict.get("Dst Port", "0")))
    point.tag("label", data_dict.get("Label", "unknown"))

    # Add fields (numeric values only)
    for key, value in data_dict.items():
        if key in {"Flow ID", "Src IP", "Dst IP", "Src Port", "Dst Port", "Timestamp", "Label"}:
            continue  # already handled
        if isinstance(value, (int, float)):
            point.field(key, float(value))  # convert int to float
        elif isinstance(value, str) and len(value) < 50:
            point.tag(key, value)  # optional: treat short strings as tags
        else:
            point.field(key, str(value))  # fallback

def ocpplog_data_parser(data_dict, point):
    """
    Parse one log-activity JSON line and return an InfluxDB Point.
    """
    # ---------- Timestamp ----------------------------------------------------
    ts_str = data_dict.get("timestamp")
    if not ts_str:
        raise ValueError("[influxdb_api.py] Missing 'timestamp' in log entry")
    # Permit both “…Z” and plain micro-second ISO strings
    timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    
    # Start building point
    point.time(timestamp)

    # Tags for fast filtering
    point.tag("src_ip", data_dict.get("src_ip", "unknown"))
    point.tag("dst_ip", data_dict.get("dst_ip", "unknown"))

    # Message handling 
    msg = data_dict.get("msg")

    # 1) Simple string, e.g. "ping"
    if isinstance(msg, str):
        point.tag("msg_type", msg.lower())  # e.g. ping
        point.field("message", msg)

    # 2) Any list-based message → store whole list as JSON string
    elif isinstance(msg, list):
        point.tag("msg_type", "list")
        point.field("message", json.dumps(msg))

    # 3) Fallback for anything else
    else:
        point.tag("msg_type", "unknown")
        point.field("message", json.dumps(msg))


def influxdb_upload_message(message, uid, topic):
    # print(f'[influxdb_api.py] Writing message from topic to InfluxDB ...')
    # If bucket not already present for UID, create in InfluxDB
    check_and_create_bucket(uid) 
    # Parse message:
    try:
        # Try to parse as JSON
        data_dict = json.loads(message)
    except json.JSONDecodeError as e:
        data_dict = {
            "message": message,
        }
    point = Point(topic)
    if "metricbeat" in topic:
        # print("[influxdb_api.py] Writing metricbeat message ...")
        metricbeat_data_parser(data_dict, point) # Use timestamp within metricbeat
    elif "ocppflowmeter" in topic:
        # print("[influxdb_api.py] Writing ocppflowmeter message ...")
        ocpp_data_parser(data_dict, point) # Use timestamp within flow
    elif "cicflowmeter" in topic:
        # print("[influxdb_api.py] Writing cicflowmeter message ...")
        cic_data_parser(data_dict, point) # Use timestamp within flow
    elif "logs" in topic:
        # print("[influxdb_api.py] Writing ocpplog message ...")
        ocpplog_data_parser(data_dict, point) # Use timestamp within flow
    else:
        # print(f"[influxdb_api.py] Writing message to topic: {topic} ...")
        dynamic_data_parser(data_dict, point)
        point.time(datetime.now(), WritePrecision.NS) # Add a timestamp, using system time:
    # Write:
    write_api = client.write_api()
    write_api.write(bucket=uid, record=point)
    write_api.close()

def influxdb_realtime_upload(topic, uid, stop_event):
    print(f'[influxdb_api.py] Listening on topic {topic} ...')
    consumer = KafkaConsumer( topic, 
        bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')], 
        security_protocol=config_kafka.get('kafka', 'security_protocol'),
        sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
        sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
        sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        auto_offset_reset=config_kafka.get('kafka', 'auto_offset_reset'), 
        enable_auto_commit=True,       
        value_deserializer=lambda x: x.decode('utf-8')  
    )
    try:
        while not stop_event.is_set():
            records = consumer.poll(timeout_ms=1000)
            for tp, batch in records.items():
                for message in batch:
                    influxdb_upload_message(message.value, uid, topic)
        #for message in consumer:
            # print(f'[influxdb_api.py] Uploading new message to bucket {uid} ...')
            # print(f'Received message: {message.value}')
            # influxdb_upload_message(message.value, uid, topic)
    except Exception as e:
        print(f'[influxdb_api.py] Error encountered for realtime upload to bucket {uid}. Error: {e}')
    finally:
        consumer.close()
        print(f'[influxdb_api.py] Consumer closed for topic {topic}.')

@app.route('/ping', methods=['GET'])
def ping():
    ready = client.ping()
    print("Ping route called", flush=True)
    return str(ready)

if __name__ == '__main__':
    time.sleep(30)  # Give time for mapping creation
    topic_uid_dict, last_mapping_content = load_mapping_file()
    if topic_uid_dict:
        start_influx_listeners(topic_uid_dict)
    else:
        print("[influxdb_api.py] No initial mapping found or file empty.")
    watcher_thread = Thread(target=watch_topic_mapping, daemon=True)
    watcher_thread.start()
    app.run(host="0.0.0.0", debug=True, port=4999, use_reloader=False)