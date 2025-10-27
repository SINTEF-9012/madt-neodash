from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread, Event
import configparser
import json
import time
import os
import tempfile
import io
import sys
import urllib.request
import magic
import shutil
from py2neo import Graph
import traceback

# Load configurations from .ini files
config_kafka = configparser.ConfigParser()
config_kafka.read('kafka_config.ini')

config_neo4j = configparser.ConfigParser()
config_neo4j.read('neo4j_config.ini')

# Global graph data
UC = 0  # Default 0 - no UC
graph_data = []
full_graph_data = []
listener_threads = {}
stop_events = {}
app = Flask(__name__)

# driver = GraphDatabase.driver(config_neo4j.get('neo4j','uri'), auth=(config_neo4j.get('neo4j','username'), config_neo4j.get('neo4j','password')))
def get_py2neo_graph():
    return Graph(config_neo4j.get('neo4j','uri'), auth=(config_neo4j.get('neo4j','username'), config_neo4j.get('neo4j','password')))
    # return Graph('https://madt4bc-neo4j.dynabic.dev:443', auth=(config_neo4j.get('neo4j','username'), config_neo4j.get('neo4j','password')))

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


def start_listeners(uc: int):
    """Start all Kafka listeners for the given UC number."""
    global listener_threads, stop_events, UC
    # If no UC chosen: 
    if UC == 0:
        print(f"[neo4j_api.py] No UC selected yet. Waiting on selection ...")
        return
    # Define all topics for this UC
    uc_topic = config_kafka.get('kafka', f"uc{uc}_madt_topic")
    uc_full_topic = config_kafka.get('kafka', f"uc{uc}_madt_topic_complete_kg")
    uc_events_topic = config_kafka.get('kafka', f"uc{uc}_events_topic")
    uc_reaction_topic = config_kafka.get('kafka', f"uc{uc}_soar_response")        
    # Create stop events for graceful shutdown
    stop_events = {
        "graph": Event(),
        "events": Event(),
        "reaction": Event(),
        "status": Event(),
    }
    # Create and start each listener thread
    listener_threads = {
        "graph": Thread(target=neo4j_listen_for_changes, args=([uc_topic, uc_full_topic], stop_events["graph"])),
        "events": Thread(target=neo4j_listen_for_events, args=(uc_events_topic, stop_events["events"])),
        "reaction": Thread(target=neo4j_listen_for_reactions, args=(uc_reaction_topic, stop_events["reaction"])),
    }
    # Only UC=2 has status topic
    if uc == 2:
        uc_status_topic = config_kafka.get('kafka', f"uc{uc}_status")
        listener_threads["status"] = Thread(target=neo4j_listen_for_status, args=(uc_status_topic, stop_events["status"]))
    for name, thread in listener_threads.items():
        thread.start()
        print(f"[neo4j_api.py] Listener thread '{name}' started for UC{uc}")


def stop_listeners():
    """Stop all running Kafka listener threads gracefully."""
    global stop_events, listener_threads
    if not listener_threads:
        return
    print("[neo4j_api.py] Stopping all listener threads...")
    # Signal all threads to stop
    for event in stop_events.values():
        event.set()
    # Wait for all threads to exit
    for name, thread in listener_threads.items():
        thread.join(timeout=5)
        print(f"[neo4j_api.py] Listener '{name}' stopped.")
    listener_threads.clear()
    stop_events.clear()


@app.route('/neo4j_update_uc', methods=['POST'])
def neo4j_update_uc():
    global UC
    data = request.json
    try:
        new_uc = int(data["uc"])
        if new_uc != UC:
            stop_listeners()   # Stop current listeners
            UC = new_uc
            start_listeners(UC)  # Start new listeners
            print(f"[neo4j_api.py] --> UC changed to {UC}, listeners restarted.")
        return jsonify({"status": "success", "message": f"UC updated to {UC}"}), 200
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "UC value must be an integer"}), 400

@app.route('/neo4j_update_url', methods=['POST'])
def neo4j_update_url():
    data = request.json
    node_name = data['node_name']
    endpoint = data['endpoint']
    url = data['url']
    print("[neo4j_api.py] Received request to update:", node_name, " from bucket ", endpoint, " with URL: ", url)
    # with driver.session() as session:
    # with get_py2neo_graph() as session:
    session = get_py2neo_graph()
    result = session.run("MATCH (n) WHERE n.name = $node_name AND n.endpoint = $endpoint "
                            "SET n.url = $url RETURN n",
                            node_name=node_name, endpoint=endpoint, url=url)
    return jsonify([record["n"].get("url") for record in result])
    
@app.route('/neo4j_update_metadata', methods=['POST'])
def neo4j_update_metadata():
    print("[neo4j_api.py] neo4j_update_metadata called." + str(request.json))
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
    # with driver.session() as session:
    # with get_py2neo_graph() as session:
    session = get_py2neo_graph()
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
    # with driver.session() as session:
    session = get_py2neo_graph()
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
    # with driver.session() as session:
    session = get_py2neo_graph()
    session_result = session.run("MATCH (n) WHERE n.name = $node_name AND n.endpoint = $endpoint "
                            "SET n.result = $result RETURN n",
                            node_name=node_name, result=result, endpoint=endpoint)
    return jsonify([record["n"].get("result") for record in session_result])
    
@app.route('/fetch_url', methods=['POST'])
def fetch_url():
    data = request.json
    node_name = data['node_name']
    print("[neo4j_api.py] Received request to fetch URL from related static node and update ", node_name)
    # with driver.session() as session:
    session = get_py2neo_graph()
    result = session.run("MATCH (n:ANALYTICS)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                            "SET n.url = m.url RETURN m",
                            node_name=node_name)
    return jsonify([record["m"].get("url") for record in result])
    
@app.route('/fetch_endpoint', methods=['POST'])
def fetch_endpoint():
    data = request.json
    node_name = data['node_name']
    print("[neo4j_api.py] Received request to fetch endpoint from related static node and update ", node_name)
    # with driver.session() as session:
    session = get_py2neo_graph()
    result = session.run("MATCH (n)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                            "SET n.endpoint = m.endpoint RETURN m",
                            node_name=node_name)
    return jsonify([record["m"].get("endpoint") for record in result])
    
    
@app.route('/neo4j_get_result', methods=['GET'])
def neo4j_get_result():
    endpoint = request.args.get('endpoint')
    print("[neo4j_api.py] Received request to get result from Analytics node associated with endpoint: ", endpoint)
    # with driver.session() as session:
    session = get_py2neo_graph() 
    result = session.run("MATCH (n:ANALYTICS) WHERE n.endpoint = $endpoint "
                                "RETURN n", endpoint=endpoint)
    return jsonify([record["n"].get("result") for record in result])
    
@app.route('/neo4j_get_task', methods=['GET'])
def neo4j_get_task():
    endpoint = request.args.get('endpoint')
    print("[neo4j_api.py] Received request to get task from Analytics node associated with endpoint: ", endpoint)
    # with driver.session() as session:
    session = get_py2neo_graph()
    result = session.run("MATCH (n:ANALYTICS) WHERE n.endpoint = $endpoint "
                            "RETURN n", endpoint=endpoint)
    return jsonify([record["n"].get("task") for record in result])
    
@app.route('/neo4j_get_parent_type', methods=['GET'])
def neo4j_get_parent_type():
    endpoint = request.args.get('endpoint')
    node_name = request.args.get('node_name')
    print("[neo4j_api.py] Received request to get parent node type of Analytics node with endpoint:", endpoint)
    #with driver.session() as session:
    session = get_py2neo_graph()
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
    # with driver.session() as session:
    #     result = session.run(query)
    #     result_data = [record.data() for record in result]
    #     return jsonify(result_data)
    graph = get_py2neo_graph()
    return graph.run(query).data()

@app.route('/neo4j_run_query', methods=['POST'])
def neo4j_run_query():
    data = request.json
    query = data['query']
    print("[neo4j_api.py] Received query to execute in Neo4J:", query)
    # with driver.session() as session:
    #     session_result = session.run(query)
    #     # We are assuming that the query returns something to jsonify
    #     results = [record.data() for record in session_result]
    #     return jsonify(results)
    graph = get_py2neo_graph()
    return graph.run(query).data()
    
@app.route('/api/neo4j_get_graph', methods=['GET'])
def neo4j_get_graph():
    uc = request.args.get('uc')
    # API wrap for function obtaining current graph in Neo4J
    data = neo4j_graph() # Before neo4j_graph(uc)
    return jsonify(data)


def neo4j_graph():
    query = f"""
    MATCH (n:ASSET)-[r]->(m:ASSET)
    RETURN n, r, m
    """
    try:
        # with driver.session() as session:
        session = get_py2neo_graph()
        results = session.run(query)
        new_graph_data = []
        for record in results:
            node1 = record["n"]
            rel = record["r"]
            node2 = record["m"]
            # Adjusted to include relationship details as specified
            new_graph_data.append({
                "n": {
                    "identity": int(node1.identity),
                    "labels": list(node1.labels),
                    "properties": dict(node1),
                    "elementId": str(node1.identity)
                },
                "r": {
                    "identity": int(rel.identity),
                    "start": int(rel.start_node.identity),
                    "end": int(rel.end_node.identity),
                    "type": rel.__class__.__name__,
                    "properties": dict(rel),
                    "elementId": str(rel.identity),
                    "startNodeElementId": str(rel.start_node.identity),
                    "endNodeElementId": str(rel.end_node.identity)
                },
                "m": {
                    "identity": node2.identity,
                    "labels": list(node2.labels),
                    "properties": dict(node2),
                    "elementId": str(node2.identity)
                },
            })
        return new_graph_data
    except Exception as e:
        # print("im here")
        print(f"An error occurred: {e}")
        return []
    finally:
        None
        # driver.close()

def neo4j_full_graph():
    query = f"""
    MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    try:
        #with driver.session() as session:
        session = get_py2neo_graph() 
        results = session.run(query)
        new_graph_data = []
        for record in results:
            node1 = record["n"]
            rel = record["r"]
            node2 = record["m"]
            # Adjusted to include relationship details as specified
            new_graph_data.append({
                "n": {
                    "identity": int(node1.identity),
                    "labels": list(node1.labels),
                    "properties": dict(node1),
                    "elementId": str(node1.identity)
                },
                "r": {
                    "identity": int(rel.identity),
                    "start": int(rel.start_node.identity),
                    "end": int(rel.end_node.identity),
                    "type": rel.__class__.__name__,
                    "properties": dict(rel),
                    "elementId": str(rel.identity),
                    "startNodeElementId": str(rel.start_node.identity),
                    "endNodeElementId": str(rel.end_node.identity)
                },
                "m": {
                    "identity": node2.identity,
                    "labels": list(node2.labels),
                    "properties": dict(node2),
                    "elementId": str(node2.identity)
                },
            })
        # print(new_graph_data)
        return new_graph_data
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    finally:
        None
        # driver.close()

def neo4j_listen_for_status(topic, stop_event):
    # Listen to kafka topic continuously
    consumer = KafkaConsumer(topic,
        bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')],
        security_protocol=config_kafka.get('kafka', 'security_protocol'),
        sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
        sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
        sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        auto_offset_reset=config_kafka.get('kafka', 'auto_offset_reset'), 
        enable_auto_commit=True,        # Automatically commit offsets
        value_deserializer=lambda x: x.decode('utf-8')  # Deserialize messages to string
    )
    # Keep listening indefinitely:
    try:
        print(f'[neo4j_api.py] Listening for status messages on topic: {topic}')
        for message in consumer:
            if stop_event.is_set():
                print("[neo4j_api.py] Stopping listener: status")
                break
            message_content = message.value
            print(f'[neo4j_api.py] Received status message from partition: {message.partition}, offset: {message.offset}')
            uid_to_status  = parse_status_properties(message_content)
            # If dict not empty:
            if uid_to_status:
                # Iterate the asset uids in dict:
                for uuid, status in uid_to_status.items():
                    # Search for ASSET with given uuid and update status
                    query_status = """
                    MATCH (asset:ASSET {uid: $uuid})
                    SET asset.status = $status
                    RETURN asset
                    """
                    # Run the query with parameters using the Neo4j driver:
                    session = get_py2neo_graph()
                    print(f"[neo4j_api.py] Updating status of ASSET node with UID {uuid} to {status}.")
                    session.run(query_status, {"uuid": uuid, "status": status})
    except KeyboardInterrupt:
        print("[neo4j_api.py] Consumer stopped from keyboard.")
    except Exception as e:
        print(f"[neo4j_api.py] Error processing message: {e}")
    finally:
        consumer.close()

def parse_status_properties(message_content):
    """ Parse Kafka message content containing a list of {uuid, value} dicts into a dictionary mapping uuid -> value. """
    try:
        # Decode bytes if necessary
        if isinstance(message_content, bytes):
            message_content = message_content.decode("utf-8")
        data = json.loads(message_content)
        # Ensure it’s a list of dicts with expected fields
        if isinstance(data, list):
            return {item["uuid"]: item["value"] for item in data if "uuid" in item and "value" in item}
        else:
            print(f"[neo4j_api.py] Unexpected format: {type(data)} — expected list.")
            return {}
    except json.JSONDecodeError as e:
        print(f"[neo4j_api.py] JSON decode error: {e}")
        return {}
    except Exception as e:
        print(f"[neo4j_api.py] Unexpected error: {e}")
        return {}


def neo4j_listen_for_reactions(topic, stop_event):
# Listen to kafka topic continuously
    consumer = KafkaConsumer(topic,
        bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')],
        security_protocol=config_kafka.get('kafka', 'security_protocol'),
        sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
        sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
        sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        auto_offset_reset=config_kafka.get('kafka', 'auto_offset_reset'), 
        enable_auto_commit=True,        # Automatically commit offsets
        value_deserializer=lambda x: x.decode('utf-8')  # Deserialize messages to string
    )
    # Keep listening indefinitely:
    try:
        print(f'[neo4j_api.py] Listening for messages on topic: {topic}')
        for message in consumer:
            if stop_event.is_set():
                print("[neo4j_api.py] Stopping listener: reaction")
                break
            message_content = message.value
            print(f'[neo4j_api.py] Received reaction message from partition: {message.partition}, offset: {message.offset}')
            properties  = parse_reaction_properties(message_content)
            # Create REACTION node with properties:
            query_reaction = """
            MERGE (asset:ASSET {uid: $target_uid})
            MERGE (attk:ATTACKER {uid: $attacker_uid})
            CREATE (react:REACTION $props)
            SET react.uid = randomUUID()
            CREATE (react)-[:Involves]->(asset)
            CREATE (react)-[:Mitigates]->(attk)
            RETURN react, asset, attk
            """
            target_uid = properties.get("target_uuid")
            attacker_uid = properties.get("attacker_uuid")
            # Run the query with parameters using the Neo4j driver:

            # with driver.session() as session:
            session = get_py2neo_graph()
            print(f"[neo4j_api.py] Creating REACTION node, linking to ASSET node with UID: {target_uid} and ATTACKER node with UID: {attacker_uid} ")
            session.run(query_reaction, target_uid=target_uid, attacker_uid=attacker_uid, props=properties)
    except KeyboardInterrupt:
        print("[neo4j_api.py] Consumer stopped from keyboard.")
    except Exception as e:
        print(f"[neo4j_api.py] Error processing message: {e}")
    finally:
        consumer.close()


def parse_reaction_properties(message_content):
    """
    Parses a JSON message from SOAR4BC and extracts properties
    Returns a dictionary with extracted properties.
    """
    try:
        data = json.loads(message_content)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {}
    properties = {}
        # List of expected fields to extract
    expected_fields = [
        "action",
        "attacker_ip",
        "target_ip",
        "status",
        "details",
        "attacker_uuid",
        "target_uuid",
        "timestamp"
    ]
    properties = {field: data.get(field) for field in expected_fields if field in data}
    return properties


def neo4j_listen_for_events(topic, stop_event):
    # Listen to kafka topic continuously
    consumer = KafkaConsumer(topic,
        bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')],
        security_protocol=config_kafka.get('kafka', 'security_protocol'),
        sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
        sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
        sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
        auto_offset_reset=config_kafka.get('kafka', 'auto_offset_reset'), 
        enable_auto_commit=True,        # Automatically commit offsets
        value_deserializer=lambda x: x.decode('utf-8')  # Deserialize messages to string
    )
    # Keep listening indefinitely:
    try:
        print(f'[neo4j_api.py] Listening for messages on topic: {topic}')
        for message in consumer:
            if stop_event.is_set():
                print("[neo4j_api.py] Stopping listener: events")
                break
            message_content = message.value
            print(f'[neo4j_api.py] Received event message from partition: {message.partition}, offset: {message.offset}')
            properties  = parse_alarm_properties(message_content) 
            # Use the src_uid and dst_uid from the parsed properties; if absent, the query might fail.
            dst_uid = properties.get("dst_asset_uuid")
            src_uid = properties.get("src_asset_uuid")
            src_ip = properties.get("src_ip")
            selected_keys = ["attack_uuid", "attack_type", "attack_id", "attack_created", "attack_modified", "simulation"]
            attk_properties = {k: properties[k] for k in selected_keys if k in properties}
            # TODO: Check if targeted asset is found in the knowledge graph, otherwise ignore the event.
            query_check_asset = """
            MATCH (asset:ASSET {uid: $dst_uid})
            RETURN COUNT(asset) > 0 AS asset_exists
            """
            session = get_py2neo_graph()
            result = session.run(query_check_asset, {"dst_uid": dst_uid})
            asset_exists = result.evaluate()
            if asset_exists:                # New EVENT with the properties fetched from alarm. Related to source ip asset
                query_event = """
                MERGE (asset:ASSET {uid: $dst_uid})
                CREATE (event:EVENT $props)
                SET event.uid = randomUUID()
                CREATE (event)-[:Affects]->(asset)
                RETURN event, asset
                """
            # Use the src_uid and dst_uid from the parsed properties; if absent, the query might fail.
            dst_uid = properties.get("dst_asset_uuid")
            src_uid = properties.get("src_asset_uuid")
            src_ip = properties.get("src_ip")

            # If attacker has no uuid: 
            if src_uid == "":
                # New ATTACKER with ip of src_ip and generated uuid. Links to target asset
                query_attack = """
                MERGE (asset:ASSET {uid: $dst_uid})
                CREATE (attk:ATTACKER $attk_props)
                SET attk.ip = $src_ip
                SET attk.uid = randomUUID()
                CREATE (attk)-[:Attacks]->(asset)
                RETURN attk, asset
                """
                session = get_py2neo_graph()
                print(f"[neo4j_api.py] Creating EVENT node, and linking to ASSET node with UID: {dst_uid}")
                result = session.run(query_event, dst_uid=dst_uid, props=properties)
                record = result.evaluate()  # Get the first returned record
                if record:
                    event_uid = record["event_uid"]
                    print(f"[neo4j_api.py] Created EVENT node with UID: {event_uid}")
                else:
                    event_uid = None
                    print("[neo4j_api.py] No EVENT node created or returned.")
                # Check if attacker (identified by src_uid) is already present in KG: 
                query_check_attacker = """
                    MATCH (n)
                    WHERE (n:ASSET OR n:ATTACKER) AND n.uid = $src_uid
                    RETURN COUNT(n) > 0 AS attacker_exists
                """
                session = get_py2neo_graph()
                result = session.run(query_check_attacker, {"src_uid": src_uid})
                attacker_exists = result.evaluate()
                if attacker_exists:
                    query_attack = """
                        MERGE (asset:ASSET {uid: $dst_uid})
                        MERGE (event:EVENT {uid: $event_uid})
                        MERGE (attk:ATTACKER {uid: $src_uid})
                        ON CREATE SET attk.ip = $src_ip, attk += $attk_props
                        MERGE (attk)-[:Attacks]->(asset)
                        MERGE (attk)-[:Produces]->(event)
                        RETURN attk, asset
                    """
                    # session.run(query_attack, dst_uid=dst_uid, src_ip=src_ip, attk_props=attk_properties)
                else:
                    # New ATTACKER with ip of src_ip and generated uuid. Links to target asset
                    query_attack = """
                        MERGE (asset:ASSET {uid: $dst_uid})
                        MERGE (event:EVENT {uid: $event_uid})
                        CREATE (attk:ATTACKER $attk_props)
                        SET attk.ip = $src_ip
                        SET attk.uid = apoc.create.uuid()
                        CREATE (attk)-[:Attacks]->(asset)
                        CREATE (attk)-[:Produces]->(event)
                        RETURN attk, asset
                    """
                # Run the query with parameters using the Neo4j driver:
                session = driver.session()
                print(f"[neo4j_api.py] Creating ATTACKER node and linking to ASSET node with UID: {dst_uid}")
                session.run(query_attack, dst_uid=dst_uid, src_ip=src_ip, src_uid=src_uid, attk_props=attk_properties, event_uid=event_uid)
            else:
                print(f"[neo4j_api.py] EVENT recorded but skipped due to no ASSET being found with uid: {dst_uid}")
    except KeyboardInterrupt:
        print("[neo4j_api.py] Consumer stopped from keyboard.")
    except Exception as e:
        print(f"[neo4j_api.py] Error processing message: {e}")
    finally:
        consumer.close()
def parse_alarm_properties(message_content):
    """
    Parses a STIX alert message and extracts properties.
    
    The function expects a STIX bundle JSON message, with objects that may include:
      - An "identity" object (for source identity, e.g. 'MMT-PROBE'),
      - An "observed-data" object (holding event-related properties),
      - "ipv4-addr" objects (for source and destination IP addresses),
      - A "x-attack-type" object (for attack-related properties).
    
    Returns a dictionary with extracted properties.
    """
    try:
        data = json.loads(message_content)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {}

    properties = {}
    objects = data.get("objects", [])

    # First, locate the observed-data object to get IP references
    observed = next(
        (o for o in objects if o.get("type") == "observed-data"),
        None
    )
    ip_refs = []
    if observed:
        ip_refs = observed.get("object_refs", [])
        # Extract generic observed-data fields
        properties.update({
            "observed_data_id": observed.get("id"),
            "first_observed": observed.get("first_observed"),
            "last_observed": observed.get("last_observed"),
            "number_observed": observed.get("number_observed")
        })
        # Description extension
        obs_ext = observed.get("extensions", {}).get("x-observed-data-ext", {})
        if obs_ext:
            properties["description"] = obs_ext.get("description")

        src_asset_uuid = dst_asset_uuid = attack_uuid = None
        for ref in observed.get("object_refs", []):
            if ref.startswith("ipv4-addr--"):
                uuid_part = ref.split("ipv4-addr--", 1)[1]
                if src_asset_uuid is None:
                    src_asset_uuid = uuid_part
                else:
                    dst_asset_uuid = uuid_part
            elif ref.startswith("x-attack-type--"):
                attack_uuid = ref.split("x-attack-type--", 1)[1]

        properties["src_asset_uuid"] = src_asset_uuid
        properties["dst_asset_uuid"] = dst_asset_uuid
        properties["attack_uuid"] = attack_uuid

    # Iterate over all objects to extract other properties
    for obj in objects:
        obj_type = obj.get("type", "").lower()
        if obj_type == "identity":
            properties["identity_id"] = obj.get("id")
            properties["identity_name"] = obj.get("name")
            properties["identity_class"] = obj.get("identity_class")
            properties["identity_created"] = obj.get("created")
            properties["identity_modified"] = obj.get("modified")
            properties["identity_spec_version"] = obj.get("spec_version")

        elif obj_type == "ipv4-addr":
            obj_id = obj.get("id")
            ip_val = obj.get("value")
            # Assign based on position in observed-data.object_refs
            if len(ip_refs) >= 1 and obj_id == ip_refs[0]:
                properties["src_ip"] = ip_val
            elif len(ip_refs) >= 2 and obj_id == ip_refs[1]:
                properties["dst_ip"] = ip_val

        elif obj_type == "x-attack-type":
            properties["attack_type"] = obj.get("user_id")
            properties["attack_id"] = obj.get("id")
            properties["attack_created"] = obj.get("created")
            properties["attack_modified"] = obj.get("modified")
            # External references (e.g., TTP)
            ext_refs = obj.get("external_references", [])
            if ext_refs and isinstance(ext_refs, list):
                properties["ttp_id"] = ext_refs[0].get("external_id")
                properties["source_name"] = ext_refs[0].get("source_name")
                properties["url"] = ext_refs[0].get("url")
            # Simulation extension
            sim_ext = obj.get("extensions", {}).get("x-simulation-ext", {})
            if sim_ext:
                properties["simulation"] = sim_ext.get("simulation")
    return properties

def neo4j_graph_update(current_graph, topic, asset_only: bool):
    global graph_data
    global full_graph_data
    # Check IF the last message its same as current graph, if not, update:
    if asset_only:
        if str(graph_data) != str(current_graph):
            print(f"[neo4j_api.py] Updating kafka topic with changed KG (asset only).")
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
        else: 
            print(f"[neo4j_api.py] Same KG recorded (asset only).")
    else:
        if str(full_graph_data) != str(current_graph):
            print(f"[neo4j_api.py] Updating kafka topic with changed KG (complete).")
            producer = KafkaProducer(
                bootstrap_servers=[config_kafka.get('kafka', 'bootstrap_servers')],
                security_protocol=config_kafka.get('kafka', 'security_protocol'),
                sasl_mechanism=config_kafka.get('kafka', 'sasl_mechanism'),
                sasl_plain_username=config_kafka.get('kafka', 'sasl_plain_username'),
                sasl_plain_password=config_kafka.get('kafka', 'sasl_plain_password'),
            )
            full_graph_data = current_graph
            producer.send(topic, json.dumps(graph_data).encode('utf-8'))
            producer.flush()
            producer.close()
            # Produce new topic mapping:
            print(f"[neo4j_api.py] Updating topic mapping if needed.")
            neo4j_update_topic_mapping()
        else: 
            print(f"[neo4j_api.py] Same KG recorded (complete).")

def neo4j_update_topic_mapping():
    # Query Neo4j for all DATASOURCE nodes

    #with driver.session() as session:
    session = get_py2neo_graph()
    query = "MATCH (d:DATASOURCE) RETURN d.endpoint AS endpoint, d.bucket AS bucket"
    result = session.run(query)
    mapping = {}
    for record in result:
        endpoint = record["endpoint"]
        bucket = record["bucket"]
        if endpoint and bucket:
            mapping.setdefault(endpoint, []).append(bucket)
    # driver.close()
    # Deduplicate buckets
    for k in mapping:
        mapping[k] = list(set(mapping[k]))

    os.makedirs("downloads", exist_ok=True)
    output_path = os.path.join("downloads", "topic_mapping.json")

    # Check if existing file has same content
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = {}
        if existing_data == mapping:
            print("[neo4j_api.py] topic_mapping file is up-to-date. No changes made.")
            return

    # Save updated mapping
    with open(output_path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"[neo4j_api.py] topic_mapping written to {output_path}")


def neo4j_listen_for_changes(topics, stop_event):
    """
    Periodically checks the Neo4j knowledge graph for changes and publishes updates to Kafka.
    Stops gracefully when stop_event is set.
    """
    print(f'[neo4j_api.py] Listening for knowledge graph changes on topics: {topics}')

    try:
        while not stop_event.is_set():
            print('[neo4j_api.py] Checking for changes in knowledge graph...')
            current_graph = neo4j_graph()
            current_full_graph = neo4j_full_graph()
            # Publish updates to Kafka
            neo4j_graph_update(current_graph, topic=topics[0], asset_only=True)
            neo4j_graph_update(current_full_graph, topic=topics[1], asset_only=False)
            # Sleep before next check
            for _ in range(10): 
                if stop_event.is_set():
                    print('[neo4j_api.py] Stop signal received (changes listener). Exiting...')
                    return
                time.sleep(1)
    except Exception as e:
        print(f"[neo4j_api.py] Error in neo4j_listen_for_changes: {e}")
    finally:
        print('[neo4j_api.py] Exiting neo4j_listen_for_changes loop cleanly.')


@app.route('/neo4j_create_attacker', methods=['POST'])
def neo4j_create_attacker():
    try:
        print(f"[neo4j_api.py] Adding new Attacker node to KG.")
        data = request.get_json()
        properties = data.get('properties', {})  # Expecting 'properties' to be a dictionary
        # Constructing the query dynamically based on whether properties are provided
        if properties:
            query = "CREATE (a:ATTACKER {props}) RETURN a"
            params = {'props': properties}
        else:
            query = "CREATE (a:ATTACKER) RETURN a"
            params = {}
        # with driver.session() as session:
        session = get_py2neo_graph() 
        # Running the query directly in the session
        result = session.run(query, **params)
        nodes = [{"id": record["a"].id, "properties": record["a"].properties} for record in result]
        print(f"[neo4j_api.py] Attacker node succesfully added to KG.")
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
            query = "CREATE (a:THREAT {props}) RETURN a"
            params = {'props': properties}
        else:
            query = "CREATE (a:THREAT) RETURN a"
            params = {}
        # with driver.session() as session:
        session = get_py2neo_graph() 
            # Running the query directly in the session
        result = session.run(query, **params)
        nodes = [{"id": record["a"].id, "properties": record["a"].properties} for record in result]
        print(f"[neo4j_api.py] Threat node succesfully added to KG.")
        return jsonify(nodes), 200
    except Exception as e:
        return jsonify({"[neo4j_api.py] Encountered error when adding new Threat node:": str(e)}), 400

@app.route('/neo4j_add_node', methods=['POST'])
def neo4j_add_node():
    print("[neo4j_api.py] Request to add node to KG initiated.")
    data = request.json
    node_type = data.get("type", "")
    name = data.get("name", "")
    endpoint = data.get("endpoint", "")
    asset_types = data.get("assetTypes", {})
    custom_props = data.get("customProps", [])
    datasource_tag = False
    staticdata_tag = False
    if not name or not node_type:
        return jsonify({"error": "Missing required fields"}), 400

    # Merge base properties
    props = {
        "name": name,
    }
    for prop in custom_props:
        key, value = prop.get("key"), prop.get("value")
        if key and value:
            props[key] = value
    set_statements = ",\n            ".join([
    f'n.{k} = {json.dumps(v)}' for k, v in props.items()])
    query = f"""
        CREATE (n:{node_type})
        SET {set_statements},
            n.uid = randomUUID()
    """
    print("[neo4j_api.py] Props in Query contain:" + query)
    # If ASSET, and Data Source is selected
    if node_type == "ASSET" and asset_types.get("datasource"):
        datasource_tag = True # Set to true
        query += f"""
        WITH n
        CREATE (ds:DATASOURCE {{
            name: n.name + "_DataSource",
            uid: randomUUID(),
            bucket: n.uid,
            endpoint: "{endpoint}"
        }})
        MERGE (ds)-[:DataSourceOf]->(n)
        """
    if node_type == "ASSET" and asset_types.get("staticdata"):
        staticdata_tag = True # Set to true
        query += f"""
        WITH n
        CREATE (sd:STATICDATA {{
            name: n.name + "_StaticData",
            uid: randomUUID(),
            bucket: n.uid
            type: '',
            file_name: '',
            add_date: '',
            format: ''
        }})
        MERGE (sd)-[:StaticDataOf]->(n)
        """
    query += "\nRETURN n.uid"
    print("[TEST] Final Query: " + query)
    try:
        # with driver.session() as session:
        session = get_py2neo_graph()
        result = session.run(query)
        for record in result:
            uid = record["n.uid"]  # Access each uid from the record
            print("[neo4j_add_node] UID of node created: " + uid)
        return jsonify({"message": f"{node_type} node created.", "datasource": datasource_tag, "staticdata": staticdata_tag, "uid":uid}), 200
    except Exception as e:
        print("[neo4j_add_node] Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/neo4j_add_static_data', methods=['POST'])
def neo4j_add_static_data():
    print("[neo4j_api.py] Request to add static data to selected asset.")
    data = request.json
    asset_uid = data.get("asset_uid")
    if not asset_uid:
        return jsonify({"error": "Missing asset UID"}), 400
    try:
        # with driver.session() as session:
        session = get_py2neo_graph()
        cypher = """
                MATCH (a:ASSET {uid: $asset_uid})
                CREATE (s:STATICDATA {
                    uid: randomUUID(),
                    name: a.name + '_StaticData',
                    type: '',
                    file_name: '',
                    add_date: '',
                    format: ''
                })
                MERGE (s)-[:StaticDataOf]->(a)
                WITH a
                MATCH (a)<-[:StaticDataOf]-(d:STATICDATA)
                SET d.bucket = d.uid
                RETURN d.uid
            """
        result = session.run(cypher, {"asset_uid": asset_uid})
        for record in result:
            uid = record["d.uid"]  # Access uid from the record
            print("[neo4j_api.py] UID of static data node created: " + uid)
        return jsonify({"message": "Created StaticData node.", "uid":uid}), 200
    except Exception as e:
        print("[neo4j_api.py] Error creating static node:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/neo4j_add_relation', methods=['POST'])
def neo4j_add_relation():
    print("[neo4j_api.py] Request to add relationship to KG initiated.")
    data = request.json
    source_uid = data.get("source_uid")
    target_uid = data.get("target_uid")
    if not source_uid or not target_uid:
        return jsonify({"error": "Missing source or target UID"}), 400
    try:
        # with driver.session() as session:
        session = get_py2neo_graph() 
        # Step 1: Get labels of the source node
        source_labels = session.run(
            "MATCH (n {uid: $uid}) RETURN labels(n) AS labels",
            {"uid": source_uid}
        ).evaluate()
        target_labels = session.run(
            "MATCH (n {uid: $uid}) RETURN labels(n) AS labels",
            {"uid": target_uid}
        ).evaluate()
        # Step 2: Determine relationship type
        if "ASSET" in source_labels:
            relation_type = "ConnectTo"
        elif "EVENT" in source_labels:
            if "ASSET" in target_labels:
                relation_type = "Affects"
            elif "CONSEQUENCE" in target_labels:
                relation_type = "Causes"
            else:
                relation_type = "Affects"
        elif "CONSEQUENCE" in source_labels:
            relation_type = "Impacts"
        elif "ATTACKER" in source_labels:
            if "ASSET" in target_labels:
                relation_type = "Attacks"
            elif "CONSEQUENCE" in target_labels:
                relation_type = "Causes"
            elif "EVENT" in target_labels:
                relation_type = "Produces"
            else:
                relation_type = "Attacks"
        elif "THREAT" in source_labels:
            if "ASSET" in target_labels:
                relation_type = "On"
            elif "EVENT" in target_labels:
                relation_type = "LeadsTo"
            elif "CONSEQUENCE" in target_labels:
                relation_type = "Causes"
            else:
                relation_type = "ThreatOf"
        else:
            return jsonify({"error": "Unsupported source node type"}), 400
        # Step 3: Create relationship in Cypher
        cypher = f"""
            MATCH (source {{uid: $source_uid}}), (target {{uid: $target_uid}})
            MERGE (source)-[:{relation_type}]->(target)
        """
        session.run(cypher, {
            "source_uid": source_uid,
            "target_uid": target_uid
        })
        return jsonify({"message": f"Created {relation_type} relationship."}), 200
    except Exception as e:
        print("[neo4j_api.py] Error:", e)
        return jsonify({"error": str(e)}), 500
    
def get_events_report():
    print("[neo4j_api.py] Request to run query in Neo4J and fetch event information for reporting purposes.")
    query = """
    MATCH (e:EVENT)-[:Affects]->(a:ASSET)
    RETURN a.name AS asset, a.criticality AS criticality, count(e) AS event_count
    """
    # Data containers
    asset_events = []
    total_events = 0

    # with driver.session() as session:
    session = get_py2neo_graph() 
    results = session.run(query)
    # Process each record returned by Neo4j
    for record in results:
        event_count = record["event_count"]
        total_events += event_count
        asset_events.append({
            "name": record["asset"],
            "criticality": record["criticality"],
            "events": event_count
        })
    print("[neo4j_api.py] Query ran successfully. Number of events detected: " + str(total_events))
    # Package the data into a dict
    return {
        "total": total_events,
        "assets": asset_events
    }

@app.route("/neo4j_events", methods=["GET"])
def neo4j_events():
    print("[neo4j_api.py] Request to fetch current events in Neo4J (report).")
    try:
        report = get_events_report()
        return jsonify(report)
    except Exception as e:
        # Log and return an error response if needed.
        return jsonify({"error": str(e)}), 500
    
@app.route("/ping", methods=["GET", "POST"])
def ping():
    print("Ping route called", flush=True)
    return "pong"

if __name__ == '__main__':
    start_listeners(UC)
    app.run(host="0.0.0.0", port=5001)