#!/bin/bash

# Path to your python script
PYTHON_SCRIPT=<absolute_path_to_start.py>

VENV_PATH=<absolute_path_to_venv>

# Interval in seconds
INTERVAL=7

# Activate the virtual environment
source $VENV_PATH

# Infinite loop
while true
do
    # Run the Python script
    nohup python3 $PYTHON_SCRIPT > /dev/null 2>&1 &
    sleep $INTERVAL
done

deactivate 
