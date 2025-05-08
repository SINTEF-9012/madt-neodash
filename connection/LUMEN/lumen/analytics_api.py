from flask import Flask, request, jsonify
from openai import OpenAI
from autogen import ConversableAgent, GroupChat, GroupChatManager, register_function, Agent, gather_usage_summary
from autogen.cache import Cache
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
        is_termination_msg=lambda msg: (msg["content"]) and ("TERMINATE" in msg["content"])
    )

    # LUMEN EXPERIMENT VERSION:
    """
    graph_explorer = ConversableAgent(
        "GraphExplorer",
        system_message = "Your name is GraphOperator. You can answer questions by querying a Neo4j Graph Database. Generate Cypher queries and use the registered tool to execute the query.\
        The graph follows a strict schema:  \
        (1) ASSET node has properties: name, layer, ip, description and uid. An ASSET has different relations to another ASSET (e.g. ConnectTo, Manages, Secures, etc.). \
        (2) DATASOURCE node has properties: name, type (type of data), format (data format), bucket, endpoint and uid. To get bucket, use the relation: (ds:DATASOURCE)-[:DataSourceOf]->(a:ASSET).\
        (3) STATICDATA node has properties: name, type (type of data), format (data format), bucket, file_name, add_date, and uid. To get bucket, use the relation: (sd:STATICDATA)-[:StaticDataOf]->(a:ASSET).\
        Important: Use (sd:STATICDATA)-[:StaticDataOf]->(a:ASSET) and (ds:DATASOURCE)-[:DataSourceOf]->(a:ASSET) relationships to obtain bucket IDs. Use the correct direction of the relation! Only one statement per query is allowed.",
        llm_config = openai_llm_config,
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER"
    )
    """
    # KUBERNETES DEPLOYMENT VERSION:
    graph_explorer = ConversableAgent(
        "GraphExplorer",
        system_message = "Your name is GraphOperator. You can answer questions by querying a Neo4j Graph Database. Generate Cypher queries and use the registered tool to execute the query.\
        The graph follows a strict schema:  \
        (1) ASSET node has properties: name, layer, ip, description and uid. An ASSET has different relations to another ASSET (e.g. ConnectTo, Manages, Secures, etc.). \
        (2) DATASOURCE node has properties: name, type (type of data), format (data format), bucket, endpoint and uid. To get bucket, use the relation: (ds:DATASOURCE)-[:DataSourceOf]->(a:ASSET).\
        (3) STATICDATA node has properties: name, type (type of data), format (data format), bucket, file_name, add_date, and uid. To get bucket, use the relation: (sd:STATICDATA)-[:StaticDataOf]->(a:ASSET). \
        (4) EVENT node has properties: attack_type, src_ip, dst_ip, simulation, attack_created, number_observed, description and uid. Use the relation: (e:EVENT)-[:EventOf]->(a:ASSET). \
        (5) RISK node has properties: name, likelihood and consequence and uid. It is connected to an EVENT via relation: (r:RISK)-[:RiskOf]->(a:EVENT).\
        (6) CONSEQUENCE node has properties: name, description, createdAt, and uid. Relations to other nodes:(r:RISK)-[:LeadsTo]->(c:CONSEQUENCE), (c:CONSEQUENCE)-[:Affects]->(a:ASSET). \
        Important: Use (sd:STATICDATA)-[:StaticDataOf]->(a:ASSET) and (ds:DATASOURCE)-[:DataSourceOf]->(a:ASSET) relationships to obtain bucket IDs. Use the correct direction of the relation! Only one statement per query is allowed.",
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

    nested_chats_graph = [
        {
            "recipient": graph_explorer,
            "max_turns": 2,
            "summary_method": "last_msg"
        }
    ]

    graph_operator.register_nested_chats(
        nested_chats_graph, 
        trigger = lambda sender: sender not in [graph_explorer]
    )

    # Create nested chat agent for FileExporter:

    def getFilepathTimeseries(input: Annotated[TimeseriesInput, "Return file path of data saved locally from InfluxDB."]) -> str:
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

    def getFilepathStatic(input: Annotated[StaticInput, "Return file path of data saved locally from MinIO."]) -> str:
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
        is_termination_msg=lambda msg: (msg["content"]) and ("TERMINATE" in msg["content"])
    )

    filepath_exporter = ConversableAgent(
        "FilePathExporter",
        system_message = "Your name is FilePathDriver. Given a task and a bucket ID, you save the data locally and return the file path for relevant data files using the registered tools. If no bucket ID is provided, write TERMINATE. "
        "You can obtain both MinIO (static data) and InfluxDB (time-series data) file paths through two registered functions by creating the necessary function argument(s).",
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

    nested_chats_filepath = [
        {
            "recipient": filepath_exporter,
            "max_turns": 2,
            "summary_method": "last_msg"
        }
    ]

    filepath_driver.register_nested_chats(
        nested_chats_filepath, 
        trigger = lambda sender: sender not in [filepath_exporter]
    )

    # Human proxy to initiate the chat:
    human_proxy = ConversableAgent(
        "HumanProxy",
        llm_config=False,  # no LLM used for human proxy
        code_execution_config=False,
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  # always ask for human input
    )

    task_planner = ConversableAgent(
        "TaskPlanner",
        system_message = "Your name is TaskPlanner. You create plans for specialized agents that you will be introduced to. If your plan was not succesful, construct a new one. If your plan is succesful, write TERMINATE."
        "Given a task, break it down into sub-tasks, each of which should be performed by one agent. Not all agents need to participate, it depends on the task."
        "[CONTEXT] A knowledge graph represents a network topology of assets (ASSET nodes). Agents can access data through the bucket property of data nodes (STATICDATA and DATASOURCE nodes holding information about data stored in MinIO and InfluxDB)."
        "If the task asks to analyze specific data, file paths to locally downloaded data files can be used when generating code that reads the file and analyzes the content. Some tasks only require information of the knowledge graph. ",
        llm_config = openai_llm_config,
        code_execution_config=False,  # Turn off code execution for this agent.
        human_input_mode = "ALWAYS"  if DEBUG_MODE else "NEVER"
    )


    code_generator = ConversableAgent("CodeGenerator",
        llm_config=openai_llm_config,
        system_message = '''
            Your name is CodeGenerator. You generate pure Python code, with no explanations. You might also be asked to revise your previous code. \
            You will get a task, and a path to a file (of a specific type), or a revision request. If any of these are not provided, write TERMINATE. \
            Generate one function called solve_task(file_path) that tries to solve the entire or at least part of the task. \
            If the task is abstract or ambiguous, you may create multiple conditional branches to cover the possible variations. \
            At the end, include one line of code to call solve_task function. Do not use the __main__ segment! \
            At the end, always print the result. \
            Assume these dependencies/packages are already installed: numpy, scapy, pandas, matplotlib, dpkt.  \
        ''',
        code_execution_config=False,  
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
        is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
    )

    # Create an evaluator:
    output_repeater = ConversableAgent("OutputRepeater",
        llm_config=openai_llm_config,
        system_message = "Your name is OutputRepeater. Given a task and an answer, respond following one of the two alternatives:\
                    1. If the answer satisfies the task, repeat the exact answer, and write TERMINATE at the end. Do not add any explanations unless the answer is purely numerical! \
                    2. If the answer contains an error, does not make sense, or is plainly wrong, repeat the answer and explain the problem. ",
        code_execution_config=False, 
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
    )

    # Create a local command line code executor.
    local_executor = LocalCommandLineCodeExecutor(
    timeout=180,  # Timeout (3 min)
    work_dir=llm_work_dir,  
    )

    # Create an agent with code executor configuration.
    code_executor = ConversableAgent("CodeExecutor",
        llm_config=False, 
        code_execution_config={"executor": local_executor}, 
        human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",  
    )

    # Comment out descriptions to use system message instead.
    task_planner.description = "Provides a plan/sub-tasks for agents, given a task. This agent should be the first to engage."
    graph_operator.description = "Has access to knowledge graph. Generates CYPHER queries and executes them. Can search for bucket IDs. "
    filepath_driver.description = "Saves data files locally and provides their file path, given a task and a bucket ID."
    code_generator.description = "Generates Python code, given a task and a file path."
    code_executor.description = "Executes generated Python code and prints the execution output."
    output_repeater.description = "Repeats an output/answer and stops the chat if task is solved. This agent should be the last to engage."
    # human_proxy.description = "Provides additional human input, in case the task is missing information or unclear."
   
    allowed_transitions = {
        task_planner: [graph_operator, code_generator, task_planner, output_repeater],
        graph_operator: [filepath_driver, output_repeater, graph_operator],
        filepath_driver: [code_generator, output_repeater],
        code_generator: [code_executor,],
        code_executor: [output_repeater,],
        output_repeater: [task_planner, code_generator],
        # human_proxy: [task_planner, human_proxy],
    }

    group_chat = GroupChat(agents=[task_planner, graph_operator, filepath_driver, code_generator, code_executor, output_repeater], messages=[], send_introductions = True, allowed_or_disallowed_speaker_transitions=allowed_transitions, speaker_transitions_type="allowed")

    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=openai_llm_config,
        is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
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
    task_planner_loops = 0
    full_response = ""
    for message in group_chat.messages:
        msg_count = msg_count + 1
        all_agents.append(message['name'])
        if message['name'] == "OutputRepeater":
            result = message['content']
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + result
        elif message['name'] == "GraphOperator":
            kg = True
            explorer_loops = explorer_loops + 1
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        elif message['name'] == "CodeGenerator":
            generator_loops = generator_loops + 1
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        elif message['name'] == "TaskPlanner":
            task_planner_loops = task_planner_loops + 1
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        elif message['name'] == "GraphExplorer":
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        elif message['name'] == "CodeExecutor":
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        elif message['name'] == "FilePathDriver":
            full_response = full_response + " \n --------NEXT AGENT:--------- " + message['name'] + message['content']
        # print("Msg "+ str(msg_count) + " Name: " + message['name'])
    # Remove TERMINATE from answer before returning and saving:
    result = result.replace("TERMINATE", "")
    response_content = {'result': result}
    active_agents = set(all_agents)
    generator_loops = generator_loops if generator_loops >= 2 else 0 # If code generator is only used once --> no loops
    explorer_loops = explorer_loops if explorer_loops >= 2 else 0 # If code generator is only used once --> no loops
    task_planner_loops = task_planner_loops if task_planner_loops >= 2 else 0
    usage_summary = gather_usage_summary([task_planner, graph_operator, filepath_driver, code_generator, code_executor, output_repeater])
    ### LUMEN EXPERIMENTS: task - final answer - full answer -  KG (YES/NO) - ACTIVE AGENTS - NUMBER ACTIVE AGENTS - EXEC TIME - LOOPS COUNT for GENERATOR/EXPLORER/TASKPLANNER - TOTAL NUM MESSAGES EXCHANGED - COST  -
    print("[analytics_api.py] Record:")
    print([task, result, full_response, kg, active_agents, len(active_agents), exec_time, explorer_loops, generator_loops, task_planner_loops, msg_count, usage_summary["usage_including_cached_inference"]])
    # record_task_result(task, result, full_response, kg, active_agents, len(active_agents), exec_time, explorer_loops, generator_loops, task_planner_loops, msg_count, usage_summary["usage_including_cached_inference"])
    # Return the output as JSON:
    return jsonify(response_content)  

def get_unique_filename(base_path):
    if not os.path.exists(base_path):
        return base_path
    base, ext = os.path.splitext(base_path)
    counter = 1
    while True:
        new_path = f"{base}_({counter}){ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def record_task_result(task, answer, full_response, kg, active_agents, num_active_agents, exec_time, explorer_loops, generator_loops, task_planner_loops, num_messages, cost):
    filename = './downloads/lumen_report.csv'
    unique_filename = get_unique_filename(filename)
    file_exists = os.path.isfile(unique_filename)

    with open(unique_filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # Automatically creates file with headers if it doesn't exist
        if not file_exists:
            writer.writerow(['Task', 'Answer', 'CompleteChat', 'UseKG', 'ActiveAgents', 'NumActiveAgents', 'ExecutionTime', 'GraphExplorerLoops', 'CodeGeneratorLoops', 'TaskPlannerLoops','NumMessageExchanges','Cost', "ManualLabel"])
        # Append data
        writer.writerow([task, answer, full_response, kg, active_agents, num_active_agents, exec_time, explorer_loops, generator_loops, task_planner_loops, num_messages, cost, "OK"])

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002)
