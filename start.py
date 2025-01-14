import subprocess
import random
import os

directory = < absolute_path_of_write_folder >
stop_condition = < number_of_files_to_stop_inference >

def count_files():
    file_count = 1
    for file in os.listdir(directory):
        file_path = os.path.join(directory, file)
        if os.path.isfile(file_path):
            file_count += 1
    return file_count


def inference():
    count = count_files()
    if count < stop_condition:    
        # Random number used to Retrieve Data from main_dictionary.json or your own personal dataset
        poemNumber = str(random.randint(1, 6548))
        authorNumber = str(random.randint(1, 1583))
        dayNumber = str(random.randint(1, 9098))
        subprocess.run('sudo su -c "sync; echo 3 > /proc/sys/vm/drop_caches"; free -m;', shell=True)
        subprocess.run([ <absolute_path_to_python.exe_of_venv>, <absolute_path_to_current_inference.py> , str(count), poemNumber, authorNumber, dayNumber])
        
        
inference()