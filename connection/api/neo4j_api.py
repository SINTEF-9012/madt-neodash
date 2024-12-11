from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
import configparser
import json
import time

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
                        "identity": node1.id,
                        "labels": list(node1.labels),
                        "properties": dict(node1),
                        "elementId": str(node1.id)
                    },
                    "r": {
                        "identity": rel.id,
                        "start": rel.start_node.id,
                        "end": rel.end_node.id,
                        "type": rel.type,
                        "properties": dict(rel),
                        "elementId": str(rel.id),
                        "startNodeElementId": str(rel.start_node.id),
                        "endNodeElementId": str(rel.end_node.id)
                    },
                    "m": {
                        "identity": node2.id,
                        "labels": list(node2.labels),
                        "properties": dict(node2),
                        "elementId": str(node2.id)
                    },
                })
            return new_graph_data
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    finally:
        driver.close()

    
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


if __name__ == '__main__':
    topic = config_kafka.get('kafka', 'topic')
    listener_thread = Thread(target=neo4j_listen_for_changes, args=(topic,))
    print(f'[neo4j_api.py] Listener starting...')
    listener_thread.start()
    app.run(host="0.0.0.0", port=5001)