@echo off

REM Activate the Anaconda environment
CALL conda activate basic_poetry

REM Start Python scripts in the background
START /B python minio_api.py
START /B python neo4j_api.py
START /B python analytics_api.py
START /B python influxdb_api.py
START /B python statistics_api.py

REM There is no direct batch command for 'wait', but you can simulate a pause if necessary
ECHO Scripts are running in the background. Close this window to terminate all.
PAUSE
