#!/bin/bash

# Run each Python file in the background
python analytics_api.py &
python statistics_api.py 

# Wait for all background processes to finish
wait