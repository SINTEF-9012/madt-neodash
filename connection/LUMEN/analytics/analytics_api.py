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
DEBUG_MODE = False

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
            api_url = "http://???:5001/neo4j_run_query"  # Update this if the API runs on a different host
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
        system_message = "You can access a Neo4j Graph Database, and you can answer questions by querying the database. For this, generate Cypher queries and use a registered tool to execute the query and retrive the knowledge you need."
        "The graph has the following schema:"
        "An ASSET node has the properties: name, layer, ip, description and uid."
        "A DATASOURCE node has properties: name, type, format, bucket, endpoint and uid, and is always the DataSourceOf an ASSET."
        "A STATICDATA node has properties: name, type, file_name, add_date, format and uid, and is always the DataOf an ASSET."
        "An ASSET can have the following relations to another ASSET: DistributesTo, ConnectTo, Manages, DataTo and Secures."
        "Use the correct relationship direction, that is: DATASOURCE-[:DataSourceOf]->ASSET, and STATICDATA-[:DataOf]->[ASSET].",
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
            "max_turns": 3,
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
            "http://???:5001/influxdb_download_data",
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
            "http://???:5000/minio_local_download",
            params={
                'endpoint': input.bucket
            }
        )
        if response.ok:
            json_response = response.json()
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
        system_message = "You return the file path for relevant data files, given a task and a bucket ID."
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
            "max_turns": 3,
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
        human_input_mode="ALWAYS",  # always ask for human input
    )

    #chat_result = human_proxy.initiate_chat(
    #    graph_operator,
    #    message=task
    #)

    task_planner = ConversableAgent(
        "TaskPlanner",
        system_message = "You are an expert task planner that make plans for a group of agents."
        "Given a task, you break down it into sub-tasks, each of which should be performed by one of your 'partner' agents."
        "You will be introduced to your 'partner' agents. It is fine if not all agents are involved, but typically they are."
        "Context: The agents analyze data inside a digital twin. Assets and data nodes (MinIO and InfluxDB) are found in a knowledge graph. Help solve an user-specified task by planning agent actions.",
        llm_config = openai_llm_config,
        code_execution_config=False,  # Turn off code execution for this agent.
        human_input_mode = "ALWAYS"
    )

    code_generator = ConversableAgent("CodeGenerator",
        llm_config=openai_llm_config,
        system_message = '''
            You generate pure Python code, with no explanations. \
            You will get a task, and a path to a file (of a specific type). \
            Generate one function called solve_task(file_path) that tries to solve the entire or at least part of the task. \
            At the end, include one line of code to call solve_task function. Do not use the __main__ segment! \
            At the end, always print the result. \
            Assume these dependencies/packages are already installed: numpy, scapy, pandas, matplotlib, dpkt.  \
        ''',
        code_execution_config=False,  
        human_input_mode="ALWAYS",  
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower(),
    )

    # Create an evaluator:
    output_evaluator = ConversableAgent("OutputEvaluator",
        llm_config=openai_llm_config,
        system_message = "You evaluate code execution outputs. Given a task and an output, check whether the output answers the task. \
                    If the output is valid, explain the result in a humanly manner (eventually adding some recommandations) and end your response with TERMINATE. \
                    Else, if the output is an error or it does not make sense, your response should only explain the problem. ",
        code_execution_config=False, 
        human_input_mode="ALWAYS",  
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
        human_input_mode="ALWAYS",  
    )

    task_planner.description = "Provides a plan/sub-tasks for all agents, given a task."
    graph_operator.description = "Has access to knowledge graph. Generates CYPHER queries and executes them. Can search for bucket IDs. "
    filepath_driver.description = "Provides the file path to relevant data files after saving them locally, given a task and a bucket ID."
    code_generator.description = "Generates Python code, given a task."
    code_executor.description = "Executes generated Python code and prints the execution output, given a task and a file path."
    output_evaluator.description = "Evaluates code execution output and terminates if satisfied."

    group_chat = GroupChat(agents=[task_planner, graph_operator, filepath_driver, code_generator, code_executor, output_evaluator], messages=[],)

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=openai_llm_config,
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower()
    )

    current_date = datetime.now()

    chat_result = human_proxy.initiate_chat(
        group_chat_manager,
        message=f" Task: {task}. Current date: {current_date}",
        summary_method="reflection_with_llm",
    )

    sys.exit()

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
