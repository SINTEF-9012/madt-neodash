#!/bin/bash

# Run each Python file in the background
python minio_api.py &
python neo4j_api.py &
python influxdb_api.py &
python analytics_api.py &
python statistics_api.py 

# Wait for all background processes to finish
wait