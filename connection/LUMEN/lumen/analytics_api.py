from flask import Flask, request, jsonify
from openai import OpenAI
from autogen import ConversableAgent, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor, DockerCommandLineCodeExecutor
import tempfile
import configparser
import io
import sys
import os
import urllib.request
import magic
import shutil
import requests
import json
import csv
import time
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from datetime import datetime

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
    "model": "gemma2",
    "base_url": "http://llm:11434/v1",
    "api_key": "ollama",
  },
] }

# Decide if there is human interaction or not
DEBUG_MODE = True

class TimeseriesInput(BaseModel):
    bucket: Annotated[str, Field(description="The bucket ID in InfluxDB.")]
    start_time: Annotated[str, Field(description="The start time (use ISO 8601 datetime-local format: YYYY-MM-DDTHH:mm).")]
    end_time: Annotated[str, Field(description="The end time (use ISO 8601 datetime-local format: YYYY-MM-DDTHH:mm).")]

class StaticInput(BaseModel):
    bucket: Annotated[str, Field(description="The bucket ID in MinIO.")]


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
    llm_work_dir = "./downloads"

    def query_neo4j(query: str) -> str:
        try:
            api_url = "http://localhost:5001/neo4j_run_query"  # Update this if the API runs on a different host
            payload = {"query": query}
            headers = {"Content-Type": "application/json"}
            response = requests.post(api_url, data=json.dumps(payload), headers=headers)
            # Handle response
            if response.status_code == 200:
                return response.text  # Or response.json() if you want to return structured data
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return repr(e)

    graph_operator = ConversableAgent(
        "GraphOperator",
        llm_config=False,  # Turn off LLM for this agent.
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER",
        is_termination_msg=lambda msg: (msg["content"]) and ("terminate" in msg["content"].lower())
    )

    graph_explorer = ConversableAgent(
        "GraphExplorer",
        system_message = "Your name is GraphOperator. You can access a Neo4j Graph Database, and you can answer questions by querying the database. For this, generate Cypher queries and use a registered tool to execute the query and retrive the knowledge you need.\
        The graph has the following schema:\
        ASSET node has the properties: name, layer, ip, description and uid.\
        DATASOURCE node has properties: name, type (type of data), format (data format), bucket, endpoint and uid. Use: DATASOURCE-[:DataSourceOf]->ASSET.\
        STATICDATA node has properties: name, type (type of data), format (data format), bucket, file_name, add_date, and uid. Use: STATICDATA-[:DataOf]->[ASSET].\
        Note on relations: ASSET can have the following relations to another ASSET: DistributesTo, ConnectTo, Manages, and Secures.",
        llm_config = openai_llm_config,
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER"
    )

    register_function(
        query_neo4j,
        caller = graph_explorer,
        executor = graph_operator,
        description = "Query or modify the neo4j graph database. The input is a CYPHER query, and the output is a list of records returned from the query."
    )

    nested_chats = [
        {
            "recipient": graph_explorer,
            "max_turns": 2,
            "summary_method": "last_msg"
        }
    ]

    graph_operator.register_nested_chats(
        nested_chats, 
        trigger = lambda sender: sender not in [graph_explorer]
    )

    # Create nested chat agent for FileExporter:

    def getFilepathTimeseries(input: Annotated[TimeseriesInput, "Return file path from data saved locally from InfluxDB."]) -> str:
        response = requests.get(
            "http://localhost:4999/influxdb_download_data",
            params={
                "endpoint": input.bucket,
                "start": input.start_time,
                "end": input.end_time
            }
        )
        # Check the response status and content
        if response.ok:
            json_response = response.json()
            file_path = json_response['file_path']
            # output = json_response['output']
            return file_path
        else:
            print("Error:", response.status_code, response.text)
            return ""

    def getFilepathStatic(input: Annotated[StaticInput, "Return file path from data saved locally from MinIO."]) -> str:
        response = requests.get(
            "http://localhost:5000/minio_lumen_download",
            params={
                'endpoint': input.bucket
            }
        )
        if response.ok:
            json_response = response.json()
            print(json_response)
            file_path = json_response["file_path"]
            return file_path
        else:
            print(f"API call failed with status code: {response.status_code}")
            return ""
        
    filepath_driver = ConversableAgent(
        "FilePathDriver",
        llm_config=False,  # Turn off LLM for this agent.
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER",
        is_termination_msg=lambda msg: (msg["content"]) and ("terminate" in msg["content"].lower())
    )

    filepath_exporter = ConversableAgent(
        "FilePathExporter",
        system_message = "Your name is FilePathDriver. You return the file path for relevant data files, given a task and a bucket ID."
        "You can obtain both MinIO and InfluxDB file paths through two registered functions that return the file path after saving the file contained in these databases."
        "Decide whether it is the MinIO database (static objects) or the InfluxDB (time-series data) function that should be called and create the necessary function argument(s).",
        llm_config = openai_llm_config,
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER"
    )

    register_function(
        getFilepathTimeseries,
        caller = filepath_exporter,
        executor = filepath_driver,
        description = "Returns the file path of data saved from InfluxDB (time-series) given a bucket ID and a time selection."
    )

    register_function(
        getFilepathStatic,
        caller = filepath_exporter,
        executor = filepath_driver,
        description = "Returns the file path of object saved from MinIO (static) given a bucket ID."
    )

    nested_chats = [
        {
            "recipient": filepath_exporter,
            "max_turns": 2,
            "summary_method": "last_msg"
        }
    ]

    filepath_driver.register_nested_chats(
        nested_chats, 
        trigger = lambda sender: sender not in [filepath_exporter]
    )

    # Human proxy to initiate the chat:
    human_proxy = ConversableAgent(
        "HumanTask",
        llm_config=False,  # no LLM used for human proxy
        code_execution_config=False,
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  # always ask for human input
    )

    task_planner = ConversableAgent(
        "TaskPlanner",
        system_message = "Your name is TaskPlanner. You are an expert task planner that make plans for a group of agents. It is fine if not all agents are involved."
        "Given a task, you break down it into sub-tasks, each of which should be performed by one of your 'partner' agents, but only if the agent is relevant to the task."
        "You will be introduced to your 'partner' agents. "
        "Context: The agents either analyze or update data inside a digital twin based on a knowledge graph containing asset and data nodes (that link to MinIO and InfluxDB). The asset nodes have properties like name, description, ip etc. The data nodes have properties such as bucket, format, name etc.",
        llm_config = openai_llm_config,
        code_execution_config=False,  # Turn off code execution for this agent.
        human_input_mode = "ALWAYS"  if DEBUG_MODE else "NEVER"
    )

    code_generator = ConversableAgent("CodeGenerator",
        llm_config=openai_llm_config,
        system_message = '''
            Your name is CodeGenerator. You generate pure Python code, with no explanations. \
            You will get a task, and a path to a file (of a specific type). \
            Generate one function called solve_task(file_path) that tries to solve the entire or at least part of the task. \
            At the end, include one line of code to call solve_task function. Do not use the __main__ segment! \
            At the end, always print the result. \
            Assume these dependencies/packages are already installed: numpy, scapy, pandas, matplotlib, dpkt.  \
        ''',
        code_execution_config=False,  
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower(),
    )

    # Create an evaluator:
    output_evaluator = ConversableAgent("OutputEvaluator",
        llm_config=openai_llm_config,
        system_message = "Your name is OutputEvaluator. Given a task and an output, you check whether the output answers the task and then respond by following one of the two alternatives:\
                    1. If the output is valid, respond by repeating the output then end your response with TERMINATE. \
                    2. If the output contains an error or it does not make sense, only explain the problem in a human-like manner. \
                    Note: For the first alternative, do not add any details.",
        code_execution_config=False, 
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
    )

    # Create a local command line code executor.
    local_executor = LocalCommandLineCodeExecutor(
    timeout=60,  # Timeout for each code execution in seconds.
    work_dir=llm_work_dir,  
    )

    # Create an agent with code executor configuration.
    code_executor = ConversableAgent("CodeExecutor",
        llm_config=False, 
        code_execution_config={"executor": local_executor}, 
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
    )

    task_planner.description = "Provides a plan/sub-tasks for all agents, given a task. This agent should be the first to engage."
    graph_operator.description = "Has access to knowledge graph. Generates CYPHER queries and executes them. Can search for bucket IDs. "
    filepath_driver.description = "Provides the file path to relevant data files after saving them locally, given a task and a bucket ID."
    code_generator.description = "Generates Python code, given a task."
    code_executor.description = "Executes generated Python code and prints the execution output, given a task and a file path."
    output_evaluator.description = "Evaluates final output from an agent and terminates if satisfied (aka: task is solved)."

    group_chat = GroupChat(agents=[task_planner, graph_operator, filepath_driver, code_generator, code_executor, output_evaluator], messages=[], send_introductions = True)

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=openai_llm_config,
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower(),
    )

    current_date = datetime.now()
    
    # Time execution: 
    start_time = time.time() 
    chat_result = human_proxy.initiate_chat(
        group_chat_manager,
        message=f" Task: {task}. Current date: {current_date}",
        summary_method="reflection_with_llm",
    )
    end_time = time.time()
    exec_time = end_time - start_time
    # print(f"Execution Time: {execution_time:.4f} seconds")

    # Extract result:
    result = ""
    kg = False
    all_agents = []
    msg_count = 0
    generator_loops = 0
    explorer_loops = 0
    for message in group_chat.messages:
        msg_count = msg_count + 1
        all_agents.append(message['name'])
        if message['name'] == "OutputEvaluator":
            result = message['content']
        elif message['name'] == "GraphOperator":
            kg = True
        elif message['name'] == "CodeGenerator":
            generator_loops = generator_loops + 1
        elif message['name'] == "GraphOperator":
            explorer_loops = explorer_loops + 1
    # Remove TERMINATE from answer before returning and saving:
    result = result.replace("TERMINATE", "")
    response_content = {'result': result}
    active_agents = set(all_agents)
    generator_loops = generator_loops if generator_loops >= 2 else 0 # If code generator is only used once --> no loops
    explorer_loops = explorer_loops if explorer_loops >= 2 else 0 # If code generator is only used once --> no loops

    ### LUMEN EXPERIMENTS: task - final answer - KG (YES/NO) - ACTIVE AGENTS - NUMBER ACTIVE AGENTS - EXEC TIME - USER INTERVENTION NUMBER - LOOPS COUNT for GENERATOR/EXPLORER - TOTAL NUM MESSAGES EXCHANGED
    print("[analytics_api.py] Record:")
    print([task, result, kg, active_agents, len(active_agents), exec_time, len(chat_result.human_input), explorer_loops, generator_loops, msg_count])
    record_task_result(task, result, kg, active_agents, len(active_agents), exec_time, len(chat_result.human_input), explorer_loops, generator_loops, msg_count)

    # Return the output as JSON:
    return jsonify(response_content)  

def record_task_result(task, answer, kg, active_agents, num_active_agents, exec_time, interventions, explorer_loops, generator_loops, num_messages):
    filename = './downloads/lumen_report.csv'
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # Automatically creates file with headers if it doesn't exist
        if not file_exists:
            writer.writerow(['Task', 'Answer', 'UseKG', 'ActiveAgents', 'NumActiveAgents', 'ExecutionTime', 'UserIntervention', 'GraphExplorerLoops', 'CodeGeneratorLoops', 'NumMessageExchanges'])
        # Append data
        writer.writerow([task, answer, kg, active_agents, num_active_agents, exec_time, interventions, explorer_loops, generator_loops, num_messages])

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002)
