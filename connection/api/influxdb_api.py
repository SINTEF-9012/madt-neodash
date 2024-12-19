from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import csv
import os
import json
from kafka import KafkaConsumer, OffsetAndMetadata, TopicPartition
from threading import Thread
import configparser
import time

# Load configurations from .ini files
config_kafka = configparser.ConfigParser()
config_kafka.read('kafka_config.ini')

config_influxdb = configparser.ConfigParser()
config_influxdb.read('influxdb_config.ini')

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

@app.route('/influxdb_download_data', methods=['GET'])
def influxdb_download_data():
    bucket_id = request.args.get('endpoint')
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    print("[influxdb_api.py] InfluxDB processes query from asset with uid " + bucket_id)
    query_api = client.query_api()

    # TODO Convert date format to compatible one (Obs: UTC, if not UTC -> adjust!)
    converted_start_time = start_time + ":00Z"
    converted_end_time = end_time + ":00Z"

    # Complete Flux query
    query = f"""
    from(bucket: "{bucket_id}")
    |> range(start: {converted_start_time}, stop: {converted_end_time})
    """
    print(query)

    # Execute the query
    result = query_api.query(org=config_influxdb.get("influxdb", "INFLUXDB_ORG"), query=query)

    # Define the CSV file path
    file_path = './downloads'

    if not os.path.exists(file_path):
        os.makedirs(file_path)

    file_path = os.path.join(file_path, "influxdb_outputs.csv")

    # Open a file to write and save locally
    with open(file_path, mode='w', newline='') as file:
        fieldnames = ['time', 'measurement', 'field', 'value']
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        # Write the header
        writer.writeheader()

        # Process and write data to CSV
        for table in result:
            for record in table.records:
                writer.writerow({
                    "time": record.get_time(),
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                })

    # Process the results
    output = []
    for table in result:
        for record in table.records:
            output.append({
                "time": record.get_time(),
                "measurement": record.get_measurement(),
                "field": record.get_field(),
                "value": record.get_value(),
           })

    # Close the client
    # client.close()
    print("[influxdb_api.py] InfluxDB query request processed for asset with id " + bucket_id)
    return jsonify(output)

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
        compound_key = f"{parent_key}.{key}" if parent_key else key  # Create a compound key for nested data
        if isinstance(value, dict):
            # Recursive call to handle nested dictionary
            dynamic_data_parser(value, point, compound_key)
        elif isinstance(value, list):
            # Convert list to string or handle as a list of values
            if all(isinstance(item, (str, int, float)) for item in value):  # Simple list
                point.field(compound_key, ','.join(map(str, value)))
            else:
                # For more complex data structures, you might need custom handling
                continue
        else:
            # Assign as a field or a tag based on your criteria
            if isinstance(value, str) and len(value) < 50:  # Example tag criteria
                point.tag(compound_key, value)
            elif isinstance(value, (int, float, str)):  # General field handling
                point.field(compound_key, value)

def influxdb_upload_message(message, uid, topic):
    check_and_create_bucket(uid)
    data_dict = json.loads(message)
    point = Point(topic)
    dynamic_data_parser(data_dict, point)
    # Optionally add a timestamp, here using system time
    point.time(datetime.now(), WritePrecision.NS)
    write_api = client.write_api()
    write_api.write(bucket=uid, record=point)
    write_api.close()


def influxdb_realtime_upload(topic, uid):
    print(f'[influxdb_api.py] Listening on topic {topic} ...')
    consumer = KafkaConsumer( topic,
        bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')], # REALTIME: Add topic too
        security_protocol=config_kafka.get('kafka', 'security_protocol'),
        sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
        sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
        sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        auto_offset_reset=config_kafka.get('kafka', 'auto_offset_reset'),  # Start reading at the earliest message
        enable_auto_commit=True,        # REALTIME SET True else False
        value_deserializer=lambda x: x.decode('utf-8')  # Deserialize messages to string
    )
    #consumer.assign([TopicPartition(topic, 0)])                    # REALTIME --> Comment out this part
    #consumer.seek_to_end(TopicPartition(topic, 0))                 # REALTIME --> Comment out this part
    #last_offset = consumer.position(TopicPartition(topic, 0)) - 1  # REALTIME --> Comment out this part
    #if last_offset >= 0:                                           # REALTIME --> Comment out this part
    #    consumer.seek(TopicPartition(topic, 0), last_offset)       # REALTIME --> Comment out this part
    # ...
    #else:
    #    print(f'No messages found in topic {topic}.')  # REALTIME --> Comment out this part
    try:
        for message in consumer:
            # print(f'[influxdb_api.py] Uploading new message to bucket {uid} ...')
            # print(f'Received message: {message.value}')
            influxdb_upload_message(message.value, uid, topic)
    except Exception as e:
        print(f'[influxdb_api.py] Error encountered for realtime upload to bucket {uid}. Error: {e}')
    finally:
        consumer.close()
        print(f'[influxdb_api.py] Consumer closed for topic {topic}.')



if __name__ == '__main__':
    topic_uid_dict = json.loads(config_kafka['kafka']['topic_mapping'])
    for topic, uid_list in topic_uid_dict.items():
        for uid in uid_list:
            listener_thread = Thread(target=influxdb_realtime_upload, args=(topic,uid,))
            print(f'[influxdb_api.py] New listener starting for topic {topic}...')
            listener_thread.start()
    app.run(host="0.0.0.0", debug=False, port=4999)

