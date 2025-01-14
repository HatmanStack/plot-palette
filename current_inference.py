import requests
import json
import re
import os
import time
import sys
import random
import datetime
import time
from transformers import AutoTokenizer
from huggingface_hub import login
from dotenv import load_dotenv
import Chat_Templates as chat

load_dotenv()
API_KEY = os.getenv(<huggingface token>)
login(API_KEY)

initialModel = 'mistralai/Mistral-7B-Instruct-v0.3'
secondaryModel = 'CohereForAI/c4ai-command-r-plus'
tertiaryModel = 'google/gemma-1.1-7b-it'
ancillaryModel = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
adjacentModel = "meta-llama/Meta-Llama-3.1-70B-Instruct"
models = [initialModel, adjacentModel, secondaryModel, tertiaryModel, ancillaryModel]

writeFolder = <absolute_path_of_write_folder>
currentCategory = <category>


## Dictionary to Map the Data For Random Inference ##
with open(<path to main_dict>, 'r') as f:
    main_dict = json.load(f)

if len(sys.argv) > 1:
    count = sys.argv[1]
    poemNumber = sys.argv[2]
    authorNumber = sys.argv[3]
    dayNumber = sys.argv[4]

## Data Used to Seed the Models ##

with open(<path to data>[main_dict], 'r') as f:
    poem = json.load(f)
with open(<path to data>[main_dict], 'r') as f:
    author = json.load(f)
with open(<path to data>[main_dict], 'r') as f:
    day = json.load(f)

def query(payload, queryNumber, modelId, attempt=1):
    try:
        print(modelId)
        tokenizer = AutoTokenizer.from_pretrained(modelId)
        input = tokenizer.apply_chat_template(chat.open_question_chat_setup(payload, queryNumber, modelId), tokenize=False)
        
        # API Call Goes Here
        response = <api call><text input>

        # Boilerplate to handle model busy
        if response.status_code != 200:
            print(response.json().get("error_type"), response.status_code)
            print(f'Attempt: {attempt}')
            if attempt >= 6:
                return "NotAvailable"
            modelId = models[attempt % len(models)]
            time.sleep(3)
            return query(payload, queryNumber, modelId, attempt + 1)
            
        response_json = response.json()
        if not response_json or not response_json[0].get("generated_text"):
            print("No Text")
            time.sleep(2)
            if attempt >= 6:
                return "NotAvailable"
            return query(payload, queryNumber, modelId, attempt + 1)
        
        response_json[0]["modelId"] = modelId
        return response_json
    except Exception as e:
        print("An error occurred:", str(e))
        print(f'Attempt: {attempt}')
        if attempt >= 6:
            return "NotAvailable"
        modelId = models[attempt % len(models)]
        time.sleep(3)
        return query(payload, queryNumber, modelId, attempt + 1)

# This Generates One Category (creative_writing, poem, brainstorm, open_question, question_answer) at a time
# Alter to accomodate 
def run_inference():
    print(f'Count : {count}')
    modelIdCreator = find_model()
    modelIdAnswer = random.choice(models)
    
    json_log = {
        "datakeys": {"day": dayNumber, "poem": poemNumber, "author": authorNumber},
        "category": currentCategory
    }
    
    # Generate question
    response = query(sources(), 1, modelIdCreator)
    json_log["generate_question"] = response[0]["generated_text"] if response != "NotAvailable" else "NotAvailable"
    if json_log["generate_question"] != 'NotAvailable':
        json_log["generate_question_modelId"] = response[0]["modelId"]
    
    # Check for invalid response
    if re.search(r"\n\n\n\n", json_log["generate_question"]) or response == "NotAvailable":
        response = "NotAvailable"
    else:
        # Generate answer
        response = query(json_log["generate_question"], 2, modelIdAnswer)
    
    json_log["generate_answer"] = response[0]["generated_text"] if response != "NotAvailable" else "NotAvailable"
    if json_log["generate_answer"] != "NotAvailable":
        json_log["generate_answer_modelId"] = response[0]["modelId"]
    
    # Save results to file
    timestamp = datetime.datetime.timestamp(datetime.datetime.now())
    with open(os.path.join(writeFolder, f'{timestamp}.json'), 'w', encoding='utf-8') as file:
        json.dump(json_log, file, indent=4)
    
# These functions are data dependent they'll differ for you data set
def sources():
    holder = []
    try:
        if len(day['notes'])!= 0:
            holder.append(day['notes'])
        if poem['analysis'] != 'NotAvailable':
            holder.append(poem['analysis'])
        if author['biography'] != 'NotAvailable':
            holder.append(author['biography'])
        cleaned_holder = []
        for i in holder:
            cleaned_holder.append(clean_text(str(i)))
    except Exception as e:
        print(f"An error occurred: {e}")
        for i in holder:
            cleaned_holder.append(clean_text(str(i)))
        return cleaned_holder
    return cleaned_holder

def clean_text(text):
    pattern = r'<.*?>'
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
    return cleaned_text
    
def get_poem():
    poem = 'NotAvailable'
    poem_from_dayNumber = 0
    while poem == 'NotAvailable':
        poem_from_dayNumber = str(random.randint(1, 9098))
        with open('/home/ec2-user/environment/public/flatten/' + main_dict['day'][poem_from_dayNumber], 'r') as f:
            poem_from_day = json.load(f)
        poem = poem_from_day['poem'][0]
    return poem, poem_from_dayNumber

# Model Switch
def find_model():
    model = models[0]  
    if (int(count) + 1) % 5 == 0:
        model = models[4]
    elif (int(count) + 1) % 4 == 0:
        model = models[3]
    elif (int(count) + 1) % 3 == 0:
        model = models[2]
    elif (int(count) + 1) % 2 == 0:
        model = models[1]
    return model
    
run_inference()

