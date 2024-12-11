from flask import Flask, request, jsonify
from openai import OpenAI
from autogen import ConversableAgent, GroupChat, GroupChatManager
from autogen.coding import LocalCommandLineCodeExecutor, DockerCommandLineCodeExecutor
import tempfile
import configparser
import io
import sys
import os
import urllib.request
import magic
import shutil

config = configparser.ConfigParser(allow_no_value = True)
config.read('openaiapi.ini')
openai_api_key = config.get('openai', 'OPENAI_API_KEY')

openai_llm_config = {
    "config_list": [{"model": "gpt-4o-mini", "api_key": openai_api_key, "api_rate_limit": 10.0, "tags": ["gpt4omini", "openai"]}],
    "temperature": 0.1,
    "max_tokens": 2500
}

ollama_llm_config = {"config_list": [
  {
    "model": "gemma2:2b",
    "base_url": "http://madt4bc-ollama:11434/v1",
    "api_key": "ollama",
  },
] }

app = Flask(__name__)

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'  # allowed origin
    response.headers['Access-Control-Allow-Methods'] = 'GET'  # Adjust as needed
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Apply the CORS function to all routes using the after_request decorator
@app.after_request
def apply_cors(response):
    return add_cors_headers(response)

@app.route('/analytics_generate_and_run_code', methods=['GET'])
def analytics_generate_and_run_code():
    task = request.args.get('task')
    url = request.args.get('url')
    # Static (has URL provided for download) vs Realtime (assumes always CSV format):
    if url:
        llm_work_dir = "./temp"
        # Download the file:
        local_filename, headers = urllib.request.urlretrieve(url)
        print("[analytics_api.py] The temporary file path is:", local_filename)
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(local_filename)
        print("[analytics_api.py] The file format is:", file_type)
        # Move the file to new directory (otherwise might not be available outside function)
        if not os.path.exists(llm_work_dir):
            os.makedirs(llm_work_dir)
        final_path = os.path.join(llm_work_dir, os.path.basename(local_filename))
        shutil.move(local_filename, final_path)
        print("[analytics_api.py] Final path of file to be analyzed:", final_path)
        local_filename = os.path.basename(local_filename)
    else:
        llm_work_dir = "./downloads"
        local_filename = "influxdb_outputs.csv"
        file_type = "CSV"
        final_path = "{llm_work_dir}/{local_filename}"
        print("[analytics_api.py] Final path of file to be analyzed:", final_path)

    # Human proxy to initiate the chat:
    human_proxy = ConversableAgent(
        "HumanTask",
        llm_config=False,  # no LLM used for human proxy
        human_input_mode="ALWAYS",  # always ask for human input
    )

    code_generator = ConversableAgent("CodeGenerator",
        llm_config=ollama_llm_config,
        system_message = '''
            You are a Python programming master who generates pure Python code, no explanations. \
            You will get a task, and a path to a file of a specific type. \
            Generate one function called solve_task(file_path) that solves the task.  \
            The results MUST be formatted as a dictionary following one of three alternatives:   \
            1) If results can be shown in a bar graph (e.g. mapping unique items to quantitative values), use format {key (str) : val (int/float), ...}.  \
            2) If results can be shown in a chord chart (e.g. mapping unique items to each other item in the set by quantitative values), use format {key_0 : [0, val_1, ..., val_k],  key_1 : [val_0, 0, ..., val_k], ... key_k : [val_0, val_1, ..., 0]}, where key_N (str) and val_N (int/float).  \
            3) If none of the two alternatives above are valid, use format {"answer": val (str/float/int)}.  \
            The dictionary MUST be printed at the end e.g. print(result_dict), NOT RETURNED. Also include one line of code to call solve_task function directly. NEVER use the __main__ segment. \
            Additional note 1: dpkt is available.  \
            Additional note 2: Simple questions that do not require further analysis should be answered using the third alternative.
        ''',
        code_execution_config=False,  
        human_input_mode="NEVER",  
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower(),
    )

    # Create an evaluator:
    output_evaluator = ConversableAgent("OutputEvaluator",
        llm_config=ollama_llm_config,
        system_message = '''
            You have the role of an output evaluator. \
            Given an output, you check whether the output is valid and check whether it satisfies one of the following dictionary formats: \
            1) If results can be shown in a bar graph (e.g. mapping unique items to quantitative values), use format {key (str) : val (int/float), ...}.  \
            2) If results can be shown in a chord chart (e.g. mapping unique items to each other item in the set by quantitative values), use format {key_0 : [0, val_1, ..., val_k],  key_1 : [val_0, 0, ..., val_k], ... key_k : [val_0, val_1, ..., 0]}, where key_N (str) and val_N (int/float).  \
            3) If none of the two alternatives above are valid, use format {"answer": val (str/float/int)}.  \
            If the output fulfilles one of the above, you return TERMINATE. If the output is an error or it does not fulfill requirements, explain the problem in a short sentence.
        ''',
        code_execution_config=False, 
        human_input_mode="NEVER",  
    )

    # Create a local command line code executor.
    local_executor = LocalCommandLineCodeExecutor(
    timeout=10,  # Timeout for each code execution in seconds.
    work_dir=llm_work_dir,  
    )

    # Create an agent with code executor configuration.
    code_executor = ConversableAgent("CodeExecutor",
        llm_config=False, 
        code_execution_config={"executor": local_executor}, 
        human_input_mode="NEVER",  
    )

    code_generator.description = "Generates new Python code given a task or suggestion."
    code_executor.description = "Executes generated Python code and provides the output of the execution."
    output_evaluator.description = "Evaluates execution output and provides suggestions or terminates if satisfied."

    group_chat = GroupChat(agents=[code_generator, code_executor, output_evaluator], messages=[],)

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=ollama_llm_config,
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower()
    )
    chat_result = human_proxy.initiate_chat(
        group_chat_manager,
        message=f" Task to solve: {task} Context: you have a file called {local_filename} of type {file_type} in the current directory. ",
        summary_method="reflection_with_llm",
    )
    # Extract code and result:
    code = ""
    result = ""
    for message in group_chat.messages:
        if message['name'] == "CodeGenerator":
            code = message["content"]
        elif message['name'] == "CodeExecutor":
            result = message['content'].split("Code output:")[1].strip().replace('\n', '')
    response_content = {'code': code, 'result': result}
    # Return the output as JSON:
    return jsonify(response_content)  

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002)
