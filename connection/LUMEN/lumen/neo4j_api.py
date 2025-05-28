from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
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

# Load configurations from .ini files
config_kafka = configparser.ConfigParser()
config_kafka.read('kafka_config.ini')

config_neo4j = configparser.ConfigParser()
config_neo4j.read('neo4j_config.ini')

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
    uc = request.args.get('uc')
    # API wrap for function obtaining current graph in Neo4J
    data = neo4j_graph(uc)
    return jsonify(data)


def neo4j_graph(uc):
    query = f"""
    MATCH (n:ASSET)-[r]->(m:ASSET) WHERE n.uc = {uc} AND m.uc = {uc}
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

def neo4j_listen_for_events(topic):
    # Fetch current UC:
    uc = int(topic[2]) # Fetch UC number
    # uc = 1 # TODO REMOVE Test purposes
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
        print(f'[neo4j_api.py] Listening for messages on topic: {topic}, for use case {uc}')
        for message in consumer:
            message_content = message.value
            print(f'[neo4j_api.py] Received message: {message_content} from partition: {message.partition}, offset: {message.offset}')
            properties  = parse_alarm_properties(message_content) 
            # New EVENT with the properties fetched from alarm. Related to source ip asset
            query_event = """
            MERGE (asset:ASSET {ip: $dst_ip, uc: $uc})
            CREATE (event:EVENT $props)
            SET event.uc = $uc
            SET event.uid = apoc.create.uuid()
            CREATE (event)-[:EventOf]->(asset)
            RETURN event, asset
            """
            # Use the dst_ip from the parsed properties; if absent, the query might fail.
            dst_ip = properties.get("dst_ip")
            
            # Log the parameters that will be passed for debugging.
            print(f"[neo4j_api.py] Creating EVENT node with properties: {properties} and linking to ASSET node with ip: {dst_ip}")
            
             # New ATTACKER with the properties fetched from alarm. Related to source ip asset
            query_attack = """
            MERGE (asset:ASSET {ip: $dst_ip, uc: $uc})
            CREATE (attk:ATTACK $props)
            SET attk.uc = $uc
            SET attk.ip = $src_ip
            SET attk.uid = apoc.create.uuid()
            CREATE (attk)-[:Attacks]->(asset)
            RETURN attk, asset
            """
            # Use the dst_ip from the parsed properties; if absent, the query might fail.
            src_ip = properties.get("src_ip")
             # Log the parameters that will be passed for debugging.
            print(f"[neo4j_api.py] Creating ATTACKER node with properties: {properties} and linking to ASSET node with ip: {src_ip}")
            # Run the query with parameters using the Neo4j driver.
            with driver.session() as session:
                session.run(query_event, dst_ip=dst_ip, props=properties,  uc=uc)
                session.run(query_attack, dst_ip = dst_ip, src_ip=src_ip, props=properties,  uc=uc)
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

    # Iterate over all objects to extract other properties
    for obj in objects:
        obj_type = obj.get("type", "").lower()

        if obj_type == "identity":
            properties["identity_name"] = obj.get("name")

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
            properties["attack_created"] = obj.get("created")
            properties["attack_modified"] = obj.get("modified")
            # External references (e.g., TTP)
            ext_refs = obj.get("external_references", [])
            if ext_refs and isinstance(ext_refs, list):
                properties["ttp_id"] = ext_refs[0].get("external_id")
            # Simulation extension
            sim_ext = obj.get("extensions", {}).get("x-simulation-ext", {})
            if sim_ext:
                properties["simulation"] = sim_ext.get("simulation")

    return properties

def neo4j_listen_for_changes(topic):
    global graph_data
    # Fetch current UC:
    uc = int(topic[2]) # Fetch UC number
    print(f'[neo4j_api.py] Checking for changes in knowledge graph...')
    # Fetch current graph: 
    current_graph = neo4j_graph(uc)
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

@app.route('/neo4j_add_node', methods=['POST'])
def neo4j_add_node():
    print("[neo4j_api.py] Request to add node to KG initiated.")
    data = request.json
    node_type = data.get("type", "")
    name = data.get("name", "")
    description = data.get("description", "")
    layer = data.get("layer", "")
    endpoint = data.get("endpoint", "")
    asset_types = data.get("assetTypes", {})
    custom_props = data.get("customProps", [])
    usecase = int(data.get("usecase", ""))
    datasource_tag = False
    staticdata_tag = False
    if not name or not node_type:
        return jsonify({"error": "Missing required fields"}), 400

    # Merge base properties
    props = {
        "name": name,
        "description": description,
        "layer": layer,
        "uc": usecase
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
            n.uid = apoc.create.uuid()
    """
    print("[neo4j_api.py] Props in Query contain:" + query)
    # If ASSET, and Data Source is selected
    if node_type == "ASSET" and asset_types.get("datasource"):
        datasource_tag = True # Set to true
        query += f"""
        WITH n
        CREATE (ds:DATASOURCE {{
            name: n.name + "_DataSource",
            uid: apoc.create.uuid(),
            bucket: n.uid,
            uc: n.uc,
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
            uid: apoc.create.uuid(),
            bucket: n.uid,
            uc: n.uc
        }})
        MERGE (sd)-[:StaticDataOf]->(n)
        """
    query += "\nRETURN n.uid"
    try:
        with driver.session() as session:
            result = session.run(query)
            for record in result:
                uid = record["n.uid"]  # Access each uid from the record
                print("[neo4j_add_node] UID of node created: " + uid)
            return jsonify({"message": f"{node_type} node created.", "datasource": datasource_tag, "staticdata": staticdata_tag, "uid":uid}), 200
    except Exception as e:
        print("[neo4j_add_node] Error:", e)
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
        with driver.session() as session:
            # Step 1: Get labels of the source node
            source_labels = session.run(
                "MATCH (n {uid: $uid}) RETURN labels(n) AS labels",
                {"uid": source_uid}
            ).single()["labels"]
            source_labels_target = session.run(
                "MATCH (n {uid: $uid}) RETURN labels(n) AS labels",
                {"uid": target_uid}
            ).single()["labels"]
            # Step 2: Determine relationship type
            if "ASSET" in source_labels:
                relation_type = "ConnectTo"
            elif "EVENT" in source_labels:
                relation_type = "EventOf"
            elif "RISK" in source_labels:
                if "CONSEQUENCE" in source_labels_target:
                    relation_type = "LeadsTo"
                elif "EVENT" in source_labels_target:
                    relation_type = "RiskOf"
                else:
                    relation_type = "RiskOf"
            elif "ATTACK" in source_labels:
                relation_type = "AttackOn"
            elif "CONSEQUENCE" in source_labels:
                relation_type = "Affects"
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
        print("[neo4j_add_relation] Error:", e)
        return jsonify({"error": str(e)}), 500
    
def get_events_report():
    print("[neo4j_api.py] Request to run query in Neo4J and fetch event information for reporting purposes.")
    query = """
    MATCH (e:EVENT)-[:EventOf]->(a:ASSET)
    RETURN a.name AS asset, count(e) AS event_count
    """
    # Data containers
    asset_events = []
    total_events = 0

    with driver.session() as session:
        results = session.run(query)
        # Process each record returned by Neo4j
        for record in results:
            event_count = record["event_count"]
            total_events += event_count
            asset_events.append({
                "name": record["asset"],
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

if __name__ == '__main__':
    # UNCOMMENT FOR KAFKA INTEGRATION FOR MADT4BC TOPIC:
    # print(f'[neo4j_api.py] Listeners starting...')  
    # madt_topic = config_kafka.get('kafka', 'madt_topic')
    # listener_thread_graph = Thread(target=neo4j_listen_for_changes, args=(madt_topic,))
    # listener_thread_graph.start()
    # events_topic = config_kafka.get('kafka', 'events_topic')
    # listener_thread_events = Thread(target=neo4j_listen_for_events, args=(events_topic,))
    # listener_thread_events.start()
    app.run(host="0.0.0.0", port=5001)