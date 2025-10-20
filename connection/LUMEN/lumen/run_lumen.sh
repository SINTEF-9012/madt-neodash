#!/bin/bash

# Run each Python file in the background
python -u minio_api.py &
python -u neo4j_api.py &
python -u influxdb_api.py &
python -u analytics_api.py # &
# python statistics_api.py

# Wait for all background processes to finish
wait