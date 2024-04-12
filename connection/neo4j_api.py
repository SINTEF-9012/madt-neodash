from flask import Flask, request, jsonify
from neo4j import GraphDatabase

app = Flask(__name__)

# Configure Neo4j connection - TODO: Create .ini file for this too.
uri = "bolt://localhost:7687"  # Replace with your Neo4j instance
username = "neo4j"             # Replace with your username
password = "sindit-neo4j"        # Replace with your password
driver = GraphDatabase.driver(uri, auth=(username, password))

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

@app.route('/update_url', methods=['POST'])
def update_url():
    data = request.json
    node_endpoint = data['node_endpoint']
    url = data['url']
    print("Received request to update:", node_endpoint, "with URL:", url)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.endpoint = $node_endpoint "
                             "SET n.url = $url RETURN n",
                             node_endpoint=node_endpoint, url=url)
        return jsonify([record["n"].get("url") for record in result])
    
@app.route('/update_task', methods=['POST'])
def update_task():
    data = request.json
    node_name = data['node_name']
    task = data['task']
    print("Received request to update:", node_name, "with task: ", task)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name "
                             "SET n.task = $task RETURN n",
                             node_name=node_name, task=task)
        return jsonify([record["n"].get("task") for record in result])
    
@app.route('/fetch_url', methods=['POST'])
def fetch_url():
    data = request.json
    node_name = data['node_name']
    print("Received request to fetch URL from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (n:ANALYTICS)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                             "SET n.url = m.url RETURN m",
                             node_name=node_name)
        return jsonify([record["m"].get("url") for record in result])
    
@app.route('/fetch_endpoint', methods=['POST'])
def fetch_endpoint():
    data = request.json
    node_name = data['node_name']
    print("Received request to fetch endpoint from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (n)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                             "SET n.endpoint = m.endpoint RETURN m",
                             node_name=node_name)
        return jsonify([record["m"].get("endpoint") for record in result])
    
@app.route('/fetch_type', methods=['POST'])
def fetch_type():
    data = request.json
    node_name = data['node_name']
    print("Received request to fetch type from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (n)-[a:WorksOn]->(m:STATICDATA) WHERE n.name = $node_name "
                             "SET n.type = m.type RETURN m",
                             node_name=node_name)
        return jsonify([record["m"].get("type") for record in result])
    
@app.route('/fetch_result', methods=['POST'])
def fetch_result():
    data = request.json
    node_name = data['node_name']
    print("Received request to fetch execution result from related static node and update ", node_name)
    with driver.session() as session:
        result = session.run("MATCH (c:COUNT)-[:WorksOn]->(s:STATICDATA)<-[:WorksOn]-(a:ANALYTICS) WHERE c.name = $node_name "
                             "SET c.result = a.result RETURN a",
                             node_name=node_name)
        return jsonify([record["a"].get("result") for record in result])
    
@app.route('/update_code', methods=['POST'])
def update_code():
    data = request.json
    node_name = data['node_name']
    code = data['code']
    print("Received request to update:", node_name, "with code: ", code)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name "
                             "SET n.code = $code RETURN n",
                             node_name=node_name, code=code)
        return jsonify([record["n"].get("code") for record in result])
    
@app.route('/update_lib', methods=['POST'])
def update_lib():
    data = request.json
    node_name = data['node_name']
    lib = data['lib']
    print("Received request to update:", node_name, "with lib: ")
    print(lib)
    with driver.session() as session:
        result = session.run("MATCH (n) WHERE n.name = $node_name "
                             "SET n.lib = $lib RETURN n",
                             node_name=node_name, lib=lib)
        return jsonify([record["n"].get("lib") for record in result])
    
@app.route('/update_result', methods=['POST'])
def update_result():
    data = request.json
    node_name = data['node_name']
    result = data['result']
    print("Received request to update:", node_name, "with result: ", result)
    with driver.session() as session:
        session_result = session.run("MATCH (n) WHERE n.name = $node_name "
                             "SET n.result = $result RETURN n",
                             node_name=node_name, result=result)
        return jsonify([record["n"].get("result") for record in session_result])

if __name__ == '__main__':
    app.run(host="localhost", port=5001)


