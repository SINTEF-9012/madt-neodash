from flask import Flask, request, jsonify
from openai import OpenAI
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_agentchat.tools import AgentTool, TeamTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.conditions import TextMessageTermination, SourceMatchTermination, MaxMessageTermination, TextMentionTermination
from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent, UserProxyAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_core.model_context import BufferedChatCompletionContext, ChatCompletionContext
from autogen_agentchat.ui import Console
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, ModelClientStreamingChunkEvent
from autogen_core.tools import BaseTool, FunctionTool, ToolResult
from autogen_agentchat.base import Response
from pathlib import Path
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
from typing import Annotated, Literal, List, Optional, Union, Sequence, Any, Callable, Dict, Mapping, AsyncGenerator
from datetime import datetime

import asyncio
import nest_asyncio

# Create a single global event loop for all requests
global_loop = asyncio.new_event_loop()
nest_asyncio.apply()
asyncio.set_event_loop(global_loop)

def run_async(coro):
    """Run async coroutine safely using the persistent global loop."""
    global global_loop
    if global_loop.is_closed():
        # Recreate if something closed it accidentally
        global_loop = asyncio.new_event_loop()
        nest_asyncio.apply()
        asyncio.set_event_loop(global_loop)
    return global_loop.run_until_complete(coro)

# OpenAI version - if key is available:
"""
config = configparser.ConfigParser(allow_no_value = True)
config.read('openaiapi.ini')
openai_api_key = config.get('openai', 'OPENAI_API_KEY')

openai_model_client = OpenAIChatCompletionClient(
    model = "gpt-4.1",
    api_key = openai_api_key,
)

# Must disable parallel tool calls to avoid concurrency issues in AgentTool/TeamTool
openai_model_client_no_parallel_calls = OpenAIChatCompletionClient(
    model = "gpt-4.1",
    api_key = openai_api_key,
    parallel_tool_calls=False,  
)
"""

# Assuming your Ollama server is running locally on port 11434:
ollama_model_client = OllamaChatCompletionClient(model="llama3.1:8b", host= "http://llm:11434")

# All agents get following config. Change LLM config 
current_model_client = ollama_model_client


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

    # User proxy:
    # user_proxy = UserProxyAgent("user_proxy")

    # Graph Operator:
    async def create_content(query: str) -> str:
        """
        Run a Cypher query against Neo4j via the API and return results.  Returns String representation.
        """
        try:
            api_url = "http://localhost:5001/neo4j_run_query"  # Adjust if API host differs
            payload = {"query": query}
            headers = {"Content-Type": "application/json"}
            # Run the API call in a thread (since requests is blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(api_url, data=json.dumps(payload), headers=headers)
            )
            # Check response and parse content
            if response.status_code == 200:
                records = response.text 
                return repr(records) + "<(CREATION_KEY)>"
            else:
                return repr({"Error in graph_operator": f"{response.status_code} - {response.text}"})
        except Exception as e:
            return repr({"Error in graph_operator": str(e)})
    

    async def retrieve_content(asset_name: str) -> str:
        """ Provides information on an ASSET node, including linked STATICDATA and DATASOURCE buckets."""
        try:
            if asset_name == "":
                return await content_overview()
            else:
                # Build Cypher query
                query = f"""
                MATCH (a:ASSET {{name: "{asset_name}"}})
                OPTIONAL MATCH (a)<-[*]-(sd:STATICDATA)
                OPTIONAL MATCH (a)<-[*]-(ds:DATASOURCE)
                RETURN a AS asset,
                    collect(DISTINCT {{bucket: sd.bucket, type: sd.type}}) AS static_buckets,
                    collect(DISTINCT {{bucket: ds.bucket, type: ds.type}}) AS datasource_buckets
                """
                # Call the Neo4j API via create_content()
                raw_result = await create_content(query)
                # Remove the custom creation marker
                cleaned = raw_result.replace("<(CREATION_KEY)>", "").strip()
                if "Error in graph_operator" in cleaned:
                    # Fallback if no asset found
                    return f"No asset found with name '{asset_name}'."
                else:
                    return repr(cleaned)
        except Exception as e:
            return repr({"Error in graph_operator": str(e)})

    async def content_overview() -> str:
        """ Returns a full overview of the knowledge graph: all nodes (with properties) and all relationships.  """
        try:
            query = """
            MATCH (n)
            WHERE NOT n:EVENT
            OPTIONAL MATCH (n)-[r]->(m)
            WHERE NOT m:EVENT
            RETURN
                collect(DISTINCT {
                    id: id(n),
                    labels: labels(n),
                    properties: properties(n)
                }) AS nodes,
                collect(DISTINCT {
                    id: id(r),
                    type: type(r),
                    start: id(startNode(r)),
                    end: id(endNode(r)),
                    properties: properties(r)
                }) AS relationships
            """
            # Call the Neo4j API via create_content()
            raw_result = await create_content(query)
            # Remove the custom creation marker
            cleaned = raw_result.replace("<(CREATION_KEY)>", "<(OVERVIEW_KEY)>").strip()
            if "Error in graph_operator" in cleaned:
                # Fallback if no data is found
                return "No data is found in the Neo4J graph."
            else:
                return repr(cleaned)
        except Exception as e:
            return repr({"Error in graph_operator": str(e)})
    
    DB_SCHEMA = """           
            Nodes:
            [ASSET] with properties:
                - name: str            # Name
                - ip: str | List[str]  # IP address(es)
                - description: str     # Asset description
                - criticality: str     # Criticality level (low, medium, high)
            [DATASOURCE] with properties:
                - name: str            # Name of the data source
                - format: str          # Data format
                - bucket: str          # Bucket ID
            [STATICDATA] with properties:
                - name: str            # Name
                - format: str          # Data format
                - bucket: str          # Bucket ID
    """
    graph_operator = AssistantAgent(
        name = "graph_operator",
        model_client = current_model_client,
        tools = [retrieve_content, create_content, content_overview],
        description = "An agent that creates and retrieves content from a Neo4J database.",
        system_message = f""" You answer user requests by creating or retrieving Neo4J content using registered tools:
                        -  retrieve_content: given an asset name, provides information on that asset;
                        -  content_overview: provides full overview of graph content (only use if user asks for more than one asset);
                        -  create_content: executes any Cypher query of choice (only CREATE statements allowed);
                        Creation rules you MUST follow:
                        1) Follow the schema: {DB_SCHEMA};
                        2) One Cypher statement only;
                        3) Use empty strings when properties are not given by the user; """,  
        max_tool_iterations = 1,
        reflect_on_tool_use = False
    )

    # File Path Driver:
    async def getFilepathTimeseries(bucket: str, start_time: str, end_time: str) -> str:
        """ Query time-series data from InfluxDB, save it locally as a CSV, and return the file path."""
        try:
            response = requests.get(
                "http://localhost:4999/influxdb_download_data",
                params={
                    "endpoint": bucket,
                    "start": start_time,
                    "end": end_time
                }
            )
            # Check the response status and content
            if response.ok:
                json_response = response.json()
                # Retrieved data content:
                # output = json_response['output']
                file_path = json_response['filename']
                print(f"[InfluxDB] filepath_driver saved time-series CSV data to path: {file_path}")
                return file_path
            # Handle failed response codes
            print(f"[InfluxDB] filepath_driver HTTP error <(BUCKET_ERROR)> {response.status_code}: {response.text}")
            return f"[InfluxDB] filepath_driver HTTP error <(BUCKET_ERROR)> {response.status_code}: {response.text}"
        except Exception as e:
            print(f"[InfluxDB] Error in filepath_driver <(BUCKET_ERROR)>: {e}")
            return f"[InfluxDB] Error in filepath_driver <(BUCKET_ERROR)>: {e}"
        
    timeseries_filepath_tool = FunctionTool(getFilepathTimeseries, description="Returns the file path of data saved from InfluxDB (time-series) given a bucket and a time selection (ISO 8601 datetime-local YYYY-MM-DDTHH:mm format). ")

    async def getFilepathStatic(bucket: str) -> str:
        """ Download the last file from a given MinIO bucket, save it locally, and return the file path."""
        try:
            response = requests.get(
                "http://localhost:5000/minio_lumen_download",
                params={
                    'endpoint': bucket
                }
            )
            if response.ok:
                json_response = response.json()
                print(json_response)
                file_path = json_response["file_path"]
                print(f"[MinIO] filepath_driver saved static data to path: {file_path}")
                return file_path
            print(f"[MinIO] filepath_driver HTTP error <(BUCKET_ERROR)> {response.status_code}: {response.text}")
            return f"[MinIO] filepath_driver HTTP error <(BUCKET_ERROR)> {response.status_code}: {response.text}"
        except Exception as e:
            print(f"[MinIO] Error in filepath_driver <(BUCKET_ERROR)>: {e}")
            return f"[MinIO] Error in filepath_driver <(BUCKET_ERROR)>: {e}"

    static_filepath_tool = FunctionTool(
    getFilepathStatic, description="Returns the file path of object saved from MinIO (static) given a bucket."
    )

    filepath_driver = AssistantAgent(
        name = "filepath_driver",
        model_client = current_model_client,
        tools = [timeseries_filepath_tool, static_filepath_tool],
        description = "An agent that fetches data, saves it locally and returns the file path. ",
        system_message = """Given a user request, find the bucket associated with the asset of interest and call your tools (timeseries_filepath_tool, static_filepath_tool) to save the data requested and return the file path.
                            You can obtain MinIO (static data) and InfluxDB (time-series data) file paths through two registered functions by filling the function argument(s).
                            For time-series data only: use ISO 8601 datetime-local YYYY-MM-DDTHH:mm format for eventual start_time and end_time. """,
        max_tool_iterations = 1,
        reflect_on_tool_use = False 
    )

    # Code Generator + Executor
    llm_work_dir = "./downloads"
    executor =  LocalCommandLineCodeExecutor(timeout = 360, work_dir = llm_work_dir)
    code_generator = CodeExecutorAgent(
        name = "code_generator",
        code_executor = executor,
        model_client = current_model_client,
        description = "An agent that generates Python code to analyze files. ",
        system_message = """Given an user request and a file path, generate Python code to analyze the content of the file on that path. Call main() at the end, then execute the code.
                            Do not explain the code, only output the code part. Note: For time-series data, the file is a CSV with columns: timestamp, measurement, field and value.
                            Pre-installed packages: numpy, scapy, pandas, matplotlib, dpkt (for PCAP analysis)."""
    )

    # Output Repeater
    output_repeater = AssistantAgent(
        name = "output_repeater",
        model_client= current_model_client,
        description = "An agent that gives the output of previous agent to the user.",
        system_message="Repeat the response of the previous agent and write TERMINATE at the end to finish the conversation. If an error is present, explain it."
    )

    # Team
    text_mention_termination = TextMentionTermination("TERMINATE")
    max_messages_termination = MaxMessageTermination(max_messages=10)
    termination = text_mention_termination | max_messages_termination

    def selector_func(messages: Sequence[BaseAgentEvent | BaseChatMessage]) -> str | None:
        if len(messages) == 1:
            return "graph_operator"
        if messages[-1].source == "graph_operator":
            # If just creating content, just go straight to end of conversation:
            if "<(CREATION_KEY)>" in messages[-1].to_text():
                return "output_repeater"
            # If obtaining content overview, just go straight to end of conversation:
            elif "<(OVERVIEW_KEY)>" in messages[-1].to_text():
                return "output_repeater"
            else:
                return "filepath_driver"
        if messages[-1].source == "filepath_driver":
            if "<(BUCKET_ERROR)>" in messages[-1].to_text():
                return "output_repeater"
            else:
                return "code_generator"
        if messages[-1].source == "code_generator":
            return "output_repeater"
        if messages[-1].source == "output_repeater":
            return None
        return None
    
    # Create the group chat
    selector_team = SelectorGroupChat(
        [graph_operator, filepath_driver, code_generator, output_repeater],
        model_client=ollama_model_client,
        selector_func=selector_func,
        allow_repeated_speaker=False,
        termination_condition=termination
    )

    current_date = datetime.now()
    full_task = f" Task: {task} | Current date: {current_date}"
    
    async def run_team_and_collect():
        start_time = time.time()
        await selector_team.reset()
        await executor.start()
        result_text = ""
        async for event in selector_team.run_stream(task=full_task):
            # We only care about chat messages, not internal events
            if hasattr(event, "source") and getattr(event, "source", "") == "output_repeater":
                print(event.to_text())
                result_text += event.to_text()
            else:
                if isinstance(event, BaseChatMessage) or isinstance(event, BaseAgentEvent):
                    print(event.to_text())
        await executor.stop()
        await selector_team.reset()
        end_time = time.time()
        print(f"(EVALUATION PURPOSES) Execution time: {end_time - start_time:.4f} seconds")
        return result_text

    # Run async safely
    result = run_async(run_team_and_collect())

    # Cleanup result
    cleaned_result = result.replace("TERMINATE", "").strip()
    response_content = {"result": cleaned_result}
    return jsonify(response_content)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002)
