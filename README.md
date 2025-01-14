<div align="center" style="display: block;margin-left: auto;margin-right: auto;width: 50%;">
<h1 >
  <img width="400" height="100" src="banner.png" alt="plot-palette icon">
</h1>
<div style="display: flex; justify-content: center; align-items: center;">
  <h4 style="margin: 0; display: flex;">
    <a href="https://www.apache.org/licenses/LICENSE-2.0.html">
      <img src="https://img.shields.io/badge/license-Apache2.0-blue" alt="float is under the Apache 2.0 liscense" />
    </a>
    <a href="https://www.man7.org/linux/man-pages/man1/systemctl.1.html">
      <img src="https://img.shields.io/badge/Linux%20Systemctl-green" alt="Linux" />
    </a>
    <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python->=3.10-blue">
    </a>
  </h4>
</div>

  <p><b>Empowering Writers with a Universe of Ideas <br> <a href="https://huggingface.co/datasets/Hatman/plot-palette-100k"> Plot Palette DataSet HuggingFace » </a> </b> </p>
</div>

**Plot Palette** was created to fine-tune large language models for creative writing, generating diverse outputs through iterative loops and seed data. It is designed to be run on a Linux system with `systemctl` for managing services.  Included is the service structure, specific category prompts and ~100k data entries. 

## Load DataSet

```script
from datasets import load_dataset
ds = load_dataset("Hatman/plot-palette-100k")
```

## Data Fields

For each entry all fields exsist.  If the **category** is 'question_answer' then all **_1** fields will be populated, otherwise they'll be an empty string. 

- **id**: A unique identifier for each prompt-response pair.
- **category**: A category that the entry belongs to (creative_writing, poem, open_question, brainstorm, question_answer).
- **summary**: A summary of the question and answer responses 
- **question**: A question created from random Data 
- **answer**: An answer to the **question** based on the **category** field
- **question_1**: A follow-up question to the **question**, **answer** pair
- **answer_1**: An answer to **question_1**
- **question_modelId**
- **answer_modelId**
- **question_modelId_1**
- **answer_modelId_1**

### Category

These are the possible categories that the entry can belong to.

- **creative_writing**: A story generated from random data 
- **poem**: A poem whose style and subject are generated from random data
- **open_question**:  A **question** generated from random data and **answer** generated from model general knowledge 
- **brainstorm**: A brainstorm session generated from random data 
- **question_answer**: Two pairs of question/answer that are a response to an **open_question**

# Installation

### Prerequisites

- Python 3.10 or higher
- `pip` for installing Python packages
- Linux system with `systemctl` for managing services **AWS Cloud9**
- Data for generating random questions
- API for making LLM Calls

### Step-by-Step Installation Guide

1. **Clone the Repository**
    ```sh
    git clone https://github.com/hatmanstack/plot-palette.git
    cd plot-palette
    pip install -r requirements.txt
    ```

2. **Edit Service File Paths**
    Change the path in `inference.service` to point to `bash_script.sh` for your local environment.

3. **Copy and Enable the Service**
    ```sh
    sudo cp inference.service /etc/systemd/system/
    sudo systemctl enable inference.service
    sudo systemctl start inference.service
    sudo systemctl status inference.service
    ```

4. **Configure Local Paths**
    Update `start.py` and `current_inference.py` with your local environment paths and provide a write directory and seed data.

5. **Set Up Your API**
    Create a `.env` file with your token:
    ```plaintext
    TOKEN=api_token
    ```

## Configuration

Make sure to adapt the paths in the scripts and the service file to fit your local environment. Choose an API that makes sense for **you**, usage limits and licensing should be top of mind.  **main_dictionary.json** is an index of a personal dataset and is responsible for generating the intial question, if it's something you'd like access to feel free to contact me.  

## Models Used

- **mistralai/Mistral-7B-Instruct-v0.3**
- **mistralai/Mixtral-8x7B-Instruct-v0.3**
- **mistralai/Mixtral-8x7B-Instruct-v0.1**
- **CohereForAI/c4ai-command-r-plus**
- **google/gemma-1.1-7b-it**
- **meta-llama/Meta-Llama-3.1-8B-Instruct**
- **meta-llama/Meta-Llama-3.1-70B-Instruct**

## License

This project is licensed under the Apache 2.0 License. The Liscenses' for individual model outputs apply to that specific model's output. **CohereForAI/c4ai-command-r-plus** is the only model whose outputs should not be used for training other models intended for **Commercial** uses. 

<p align="center">
    This application is using HuggingFace Tokenizers provided by <a href="https://huggingface.co">HuggingFace</a> </br>
    <img src="https://github.com/HatmanStack/pixel-prompt-backend/blob/main/logo.png" alt="HuggingFace Logo">
</p>