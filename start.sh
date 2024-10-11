#!/bin/bash
source activate base
conda env list
conda activate madt_environment
conda list

yarn run dev &
cd connection
python3 minio_api.py &
python3 neo4j_api.py &
python3 influxdb_api.py

