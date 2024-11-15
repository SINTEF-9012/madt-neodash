from flask import Flask, request, jsonify
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import csv
import os

app = Flask(__name__)

# InfluxDB settings
# INFLUXDB_URL = 'http://sindit-influx-db:8086'
INFLUXDB_URL = 'http://madt4bc-minio-influx:8086'
INFLUXDB_TOKEN = 'sindit_influxdb_admin_token'
INFLUXDB_ORG = 'sindit'

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://0.0.0.0:3000'  # allowed origin
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

    # Initialize InfluxDB client
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
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
    result = query_api.query(org=INFLUXDB_ORG, query=query)

    # Define the CSV file path
    file_path = './outputs'

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
    client.close()

    print("[influxdb_api.py] InfluxDB query request processed for asset with id " + bucket_id)

    return jsonify(output)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False, port=4999)

