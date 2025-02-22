from flask import Flask, request, jsonify
from neo4j import GraphDatabase
# from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
import configparser
import json
import time
import os
from openai import OpenAI
from autogen import ConversableAgent, GroupChat, GroupChatManager, register_function
from autogen.coding import LocalCommandLineCodeExecutor, DockerCommandLineCodeExecutor
import tempfile
import io
import sys
import urllib.request
import magic
import shutil

# Load configurations from .ini files
#config_kafka = configparser.ConfigParser()
#config_kafka.read('kafka_config.ini')

config_neo4j = configparser.ConfigParser()
config_neo4j.read('neo4j_config.ini')

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

# Global graph data
graph_data = []

app = Flask(__name__)

driver = GraphDatabase.driver(config_neo4j.get('neo4j','uri'), auth=(config_neo4j.get('neo4j','username'), config_neo4j.get('neo4j','password')))

# Define a function to set the CORS headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'  # allowed origin
    response.headers['Access-Control-Allow-Methods'] = 'OPTIONS, GET, POST'  # Adjust as needed
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Apply the CORS function to all routes using the after_request decorator
@app.after_request
def apply_cors(response):
    return add_cors_headers(response)

@app.route('/neo4j_update_url', methods=['POST'])
def neo4j_update_url():
    data = request.json
    node_name = data['node_name']
    endpoint = data['endpoint']
    url = data['url']
    print("[neo4j_api.py] Received request to update:", node_name, " from bucket ", endpoint, " with URL: ", url)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name AND n.endpoint = $endpoint "
                             "SET n.url = $url RETURN n",
                             node_name=node_name, endpoint=endpoint, url=url)
        return jsonify([record["n"].get("url") for record in result])
    
@app.route('/neo4j_update_metadata', methods=['POST'])
def neo4j_update_metadata():
    data = request.json
    # All metadata:
    node_name = data['node_name']
    bucket = data['bucket']
    url = data['url']
    add_date = data['add_date']
    data_format = data['data_format']
    data_type = data['data_type']
    file_name = data['file_name']
    print("[neo4j_api.py] Received request to update:", node_name, " from bucket ", bucket, " with metadata.")
    print("[neo4j_api.py] URL: " + url)
    print("[neo4j_api.py] add_date: " + add_date)
    print("[neo4j_api.py] data_format: " + data_format)
    print("[neo4j_api.py] data_type: " + data_type)
    print("[neo4j_api.py] file_name: " + file_name)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name AND n.bucket = $bucket "
                             "SET n.url = $url, n.add_date = $add_date, n.format = $data_format, n.type = $data_type, n.file_name = $file_name RETURN n",
                             node_name=node_name, bucket=bucket, url=url, add_date=add_date, data_format=data_format, data_type=data_type, file_name=file_name)
        return jsonify([record["n"].get("url") for record in result])
    
@app.route('/neo4j_update_task', methods=['POST'])
def neo4j_update_task():
    data = request.json
    endpoint = data['endpoint']
    node_name = data['node_name']
    task = data['task']
    print("[neo4j_api.py] Received request to update:", node_name, " from bucket ",endpoint, " with task: ", task)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name AND n.endpoint = $endpoint "
                             "SET n.task = $task RETURN n",
                             node_name=node_name, task=task, endpoint=endpoint)
        return jsonify([record["n"].get("task") for record in result])
    
@app.route('/neo4j_update_result', methods=['POST'])
def neo4j_update_result():
    data = request.json
    node_name = data['node_name']
    result = data['result']
    endpoint = data['endpoint']
    print("[neo4j_api.py] Received request to update:", node_name, " from bucket:", endpoint, " with result: ", result)
    with driver.session() as session:
        session_result = session.run("MATCH (n) WHERE n.name = $node_name AND n.endpoint = $endpoint "
                             "SET n.result = $result RETURN n",
                             node_name=node_name, result=result, endpoint=endpoint)
        return jsonify([record["n"].get("result") for record in session_result])
    
@app.route('/fetch_url', methods=['POST'])
def fetch_url():
    data = request.json
    node_name = data['node_name']
    print("[neo4j_api.py] Received request to fetch URL from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (n:ANALYTICS)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                             "SET n.url = m.url RETURN m",
                             node_name=node_name)
        return jsonify([record["m"].get("url") for record in result])
    
@app.route('/fetch_endpoint', methods=['POST'])
def fetch_endpoint():
    data = request.json
    node_name = data['node_name']
    print("[neo4j_api.py] Received request to fetch endpoint from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (n)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                             "SET n.endpoint = m.endpoint RETURN m",
                             node_name=node_name)
        return jsonify([record["m"].get("endpoint") for record in result])
    
    
@app.route('/neo4j_get_result', methods=['GET'])
def neo4j_get_result():
    endpoint = request.args.get('endpoint')
    print("[neo4j_api.py] Received request to get result from Analytics node associated with endpoint: ", endpoint)
    with driver.session() as session:
        result = session.run("MATCH (n:ANALYTICS) WHERE n.endpoint = $endpoint "
                             "RETURN n", endpoint=endpoint)
        return jsonify([record["n"].get("result") for record in result])
    
@app.route('/neo4j_get_task', methods=['GET'])
def neo4j_get_task():
    endpoint = request.args.get('endpoint')
    print("[neo4j_api.py] Received request to get task from Analytics node associated with endpoint: ", endpoint)
    with driver.session() as session:
        result = session.run("MATCH (n:ANALYTICS) WHERE n.endpoint = $endpoint "
                             "RETURN n", endpoint=endpoint)
        return jsonify([record["n"].get("task") for record in result])
    
@app.route('/neo4j_get_parent_type', methods=['GET'])
def neo4j_get_parent_type():
    endpoint = request.args.get('endpoint')
    node_name = request.args.get('node_name')
    print("[neo4j_api.py] Received request to get parent node type of Analytics node with endpoint:", endpoint)
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n:ANALYTICS {endpoint: $endpoint, name: $node_name})-[:WorksOn]->(target)
            RETURN target
            """,
            endpoint=endpoint, node_name=node_name
        )
        return jsonify([record["target"].get("name") for record in result])
     
# - - - - -  - - - - -   - - - - -  Add more customized functions here: - - - - -   - - - - -   - - - - - 
@app.route('/neo4j_get_data', methods=['GET'])
def neo4j_get_data():
    query = request.args.get('query')
    with driver.session() as session:
        result = session.run(query)
        result_data = [record.data() for record in result]
        return jsonify(result_data)

@app.route('/neo4j_run_query', methods=['POST'])
def neo4j_run_query():
    data = request.json
    query = data['query']
    print("[neo4j_api.py] Received query to execute in Neo4J:", query)
    with driver.session() as session:
        session_result = session.run(query)
        # We are assuming that the query returns something to jsonify
        results = [record.data() for record in session_result]
        return jsonify(results)
    
@app.route('/api/neo4j_get_graph', methods=['GET'])
def neo4j_get_graph():
    # API wrap for function obtaining current graph in Neo4J
    data = neo4j_graph()
    return jsonify(data)


def neo4j_graph():
    query = """
    MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    try:
        with driver.session() as session:
            results = session.run(query)
            new_graph_data = []
            for record in results:
                node1 = record["n"]
                rel = record["r"]
                node2 = record["m"]
                # Adjusted to include relationship details as specified
                new_graph_data.append({
                    "n": {
                        "identity": int(node1.element_id),
                        "labels": list(node1.labels),
                        "properties": dict(node1),
                        "elementId": str(node1.element_id)
                    },
                    "r": {
                        "identity": int(rel.element_id),
                        "start": int(rel.start_node.element_id),
                        "end": int(rel.end_node.element_id),
                        "type": rel.type,
                        "properties": dict(rel),
                        "elementId": str(rel.element_id),
                        "startNodeElementId": str(rel.start_node.element_id),
                        "endNodeElementId": str(rel.end_node.element_id)
                    },
                    "m": {
                        "identity": node2.element_id,
                        "labels": list(node2.labels),
                        "properties": dict(node2),
                        "elementId": str(node2.element_id)
                    },
                })
            return new_graph_data
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    finally:
        driver.close()

# UNCOMMENT FOR KAFKA INTEGRATION
'''
def neo4j_listen_for_changes(topic):
    global graph_data
    print(f'[neo4j_api.py] Checking for changes...')
    # Fetch current graph: 
    current_graph = neo4j_graph()
    # Check IF the last message its same as current graph, if not, update:
    if str(graph_data) != str(current_graph):
        print(f"[neo4j_api.py] Updating kafka topic with changed KG.")
        producer = KafkaProducer(
            bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')],
            security_protocol=config_kafka.get('kafka', 'security_protocol'),
            sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
            sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
            sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        )
        graph_data = current_graph
        producer.send(topic, json.dumps(graph_data).encode('utf-8'))
        producer.flush()
        producer.close()
    # Checks updates indefinitely
    time.sleep(3600) # Check each hour for updates
    neo4j_listen_for_changes(topic)
'''

@app.route('/neo4j_create_attack', methods=['POST'])
def neo4j_create_attack():
    try:
        print(f"[neo4j_api.py] Adding new Attack node to KG.")
        data = request.get_json()
        properties = data.get('properties', {})  # Expecting 'properties' to be a dictionary

        # Constructing the query dynamically based on whether properties are provided
        if properties:
            query = "CREATE (a:Attack {props}) RETURN a"
            params = {'props': properties}
        else:
            query = "CREATE (a:Attack) RETURN a"
            params = {}

        with driver.session() as session:
            # Running the query directly in the session
            result = session.run(query, **params)
            nodes = [{"id": record["a"].id, "properties": record["a"].properties} for record in result]
            print(f"[neo4j_api.py] Attack node succesfully added to KG.")
            return jsonify(nodes), 200

    except Exception as e:
        return jsonify({"[neo4j_api.py] Encountered error when adding new Attack node:": str(e)}), 400
    

@app.route('/neo4j_create_threat', methods=['POST'])
def neo4j_create_threat():
    try:
        print(f"[neo4j_api.py] Adding new Threat node to KG.")
        data = request.get_json()
        properties = data.get('properties', {})  # Expecting 'properties' to be a dictionary

        # Constructing the query dynamically based on whether properties are provided
        if properties:
            query = "CREATE (a:Threat {props}) RETURN a"
            params = {'props': properties}
        else:
            query = "CREATE (a:Threat) RETURN a"
            params = {}

        with driver.session() as session:
            # Running the query directly in the session
            result = session.run(query, **params)
            nodes = [{"id": record["a"].id, "properties": record["a"].properties} for record in result]
            print(f"[neo4j_api.py] Threat node succesfully added to KG.")
            return jsonify(nodes), 200

    except Exception as e:
        return jsonify({"[neo4j_api.py] Encountered error when adding new Threat node:": str(e)}), 400

#### ______________________________________LUMEN________________________________________####
def query_neo4j(query:str)->str:
    try:
        records, summary, keys = driver.execute_query(query)
        return repr(records)
    except Exception as e:
        return repr(e) 

@app.route('/analytics_generate_and_run_code', methods=['GET'])
def analytics_generate_and_run_code():
    task = request.args.get('task')
    llm_work_dir = "./downloads"
    # Ask FileExplorer to locally download data: 

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
        "Be careful about the direction of the relationships, i.e., DATASOURCE-[:DataSourceOf]->ASSET, and STATICDATA-[:DataOf]->[ASSET]",
        llm_config = openai_llm_config,
        code_execution_config=False,
        human_input_mode= "ALWAYS" if DEBUG_MODE else "NEVER"
    )

    register_function(
        query_neo4j,
        caller = graph_explorer,
        executor = graph_operator,
        description = "Query or modify the neo4j graph database. The input is a cypher query, and the output is a list of records returned from the query."
    )

    nested_chats = [
        {
            "recipient": graph_explorer,
            "max_turns": 4,
            "summary_method": "last_msg"
        }
    ]

    graph_operator.register_nested_chats(
        nested_chats, 
        trigger = lambda sender: sender not in [graph_explorer]
    )

    # Human proxy to initiate the chat:
    human_proxy = ConversableAgent(
        "HumanTask",
        llm_config=False,  # no LLM used for human proxy
        human_input_mode="ALWAYS",  # always ask for human input
    )

    code_generator = ConversableAgent("CodeGenerator",
        llm_config=ollama_llm_config,
        system_message = '''
            You generate pure Python code, with no explanations. \
            You will get a task, and a path to a file (of a specific type). \
            Generate one function called solve_task(file_path) that tries to solve the entire or at least part of the task. \
            At the end, include one line of code to call solve_task function. Do not use the __main__ segment! \
            At the end, always print the result. \
            Assume these dependencies/packages are already installed: numpy, scapy, pandas, matplotlib, dpkt.  \
        ''',
        code_execution_config=False,  
        human_input_mode="NEVER",  
        is_termination_msg=lambda msg: "terminate" in msg["content"].lower(),
    )

    # Create an evaluator:
    output_evaluator = ConversableAgent("OutputEvaluator",
        llm_config=ollama_llm_config,
        system_message = '''
            You evaluate code execution outputs. Given a task and an output, you decide whether the output answers the task.  \
            If the output is valid, only return TERMINATE. If the output is an error or it does not make sense, explain the problem. 
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

    code_generator.description = "Generates Python code given a task."
    code_executor.description = "Executes generated Python code and prints the execution output."
    output_evaluator.description = "Evaluates execution output and terminates if satisfied."

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
    # UNCOMMENT FOR KAFKA INTEGRATION:
    #topic = config_kafka.get('kafka', 'topic')
    #listener_thread = Thread(target=neo4j_listen_for_changes, args=(topic,))
    #print(f'[neo4j_api.py] Listener starting...')
    #listener_thread.start()
    app.run(host="0.0.0.0", port=5001)