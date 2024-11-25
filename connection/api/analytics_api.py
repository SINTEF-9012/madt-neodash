from flask import Flask, request, jsonify
from openai import OpenAI
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

@app.route('/analytics_generate_code', methods=['GET'])
def analytics_generate_code():
    task = request.args.get('task')
    url = request.args.get('url')
    # Static (has URL provided for download) vs Realtime (assumes always CSV format):
    if url:
        # Download the file:
        local_filename, headers = urllib.request.urlretrieve(url)
        print("[analytics_api.py] The temporary file path is:", local_filename)
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(local_filename)
        print("[analytics_api.py] The file format is:", file_type)
        # Move the file to new directory (otherwise might not be available outside function)
        download_dir = "./temp"
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        final_path = os.path.join(download_dir, os.path.basename(local_filename))
        shutil.move(local_filename, final_path)
        print("[analytics_api.py] Moved file to:", final_path)
    else:
        file_type = "CSV"
        final_path = "outputs/influxdb_outputs.csv"
    # Wrap LLM prompt with info about the type of file it's supposed to analyze:
    wrapped_task = wrap(task, file_type = file_type, file_path = final_path)
    # Generate code:
    print("[analytics_api.py] Received request to generate code based on wrapped task:", wrapped_task)
    code = generate_code(wrapped_task)
    code = code["code"]
    response_content = {'code': code}
    # Return the output as JSON:
    return jsonify(response_content)

@app.route('/analytics_run_code', methods=['GET'])
def analytics_run_code():
    print(f"[analytics_api.py] Received request to run code.")
    code = request.args.get('code')
    response = run_code(code)
    # Delete everything in temp for cleanup:
    #for filename in os.listdir("./temp"):
    #        file_path = os.path.join("./temp", filename)
    #        try:
    #            if os.path.isfile(file_path):  # Ensure it's a file
    #                os.remove(file_path)
    #                print("[analytics_api.py] Deleted file:", file_path)
    #        except Exception as e:
    #            print(f"[analytics_api.py] Error deleting file {file_path}: {e}")
    # Return the output as JSON:
    print(f"[analytics_api.py] Execution response content:")
    print(response)
    response_content = {'response': response}
    return jsonify(response_content)

def wrap(task : str, file_type : str, file_path : str):
    '''
        Wraps task with additional information about file type/name for more context. 
    Args:
        task (str) : Task given by user in string form
        file_type (str) : Type of file in string form
        file_path (str) : Path of file in string form
    '''
    # TODO: To achieve better results, update also the oracle in CogniGPT/cognigpt/gpt/api.py.
    wrapped_task = ''' Task to solve:  ' ''' + task  + ''' '.
                    Context: You have a file of type: ' ''' + file_type  + ''' ' on path:  ' ''' + file_path  + ''' '. '''
    return wrapped_task

def generate_code(prompt):
    # Setup client:
    client = OpenAI(api_key=openai_api_key)
    # System message:
    system_message = '''
        You are a Python programming master. \
        You generate pure Python code to solve tasks. \
        You will get a task, and a path to a file of a specific type. \
        If the task can be performed, generate one function called solve_task(file_path) that solves the task.  \
        The results MUST be formatted as a dictionary following one of three alternatives:   \
        1) If results can be shown in a bar graph (e.g. mapping unique items to quantitative values), use format {key (str) : val (int/float), ...}.  \
        2) If results can be shown in a chord chart (e.g. mapping unique items to each other item in the set by quantitative values), use format {key_0 : [0, val_1, ..., val_k],  key_1 : [val_0, 0, ..., val_k], ... key_k : [val_0, val_1, ..., 0]}, where key_N (str) and val_N (int/float).  \
        3) If none of the two alternatives above are valid, use format {"answer": val (str/float/int)}.  \
        The dictionary MUST be printed at the end e.g. print(result_dict), NOT RETURNED. Also include one line of code to call solve_task function directly. NEVER use the __main__ segment. \
        Additional note 1: dpkt is available.  \
        Additional note 2: Simple questions that do not require further analysis should be answered using the third alternative.
        '''
    # Setup chat completion (lower temeprature --> more deterministic):
    completion = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=2500,
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}]
    )
    content = completion.choices[0].message.content
    code = extract_code(content)
    print("[analytics_api.py] Generated code:")
    print(code['code'])
    return code

def extract_code(content: str): 
    result = {'code': ''}
    code_begin = content.find("```python")
    if code_begin < 0:
        result['code'] = content
        return result
    else:
        code_end = content.find("```", code_begin + 3)
        result['code'] = content[code_begin + 9 :code_end].strip() # + 9 is '```python'
        return result

def run_code(code):
    # TODO: For now, we ignore libraries, and manually install in requirements instead.
    # TODO: Change to safer approach that does not have a risk for code injection - aka AGENT
    # Ask the user for confirmation
    # confirm = input("[analytics_api.py] Press Enter to execute the code, or Ctrl+C to cancel: ")
    # If the user presses Enter, continue to execute
    # if confirm == "":
    #   perform execution
    # else:
    #    # If the user does not press Enter, return None
    #    print("[analytics_api.py] Execution cancelled.")
    #    return None
    # Create a StringIO object to capture output
    output_buffer = io.StringIO()
    # Save the current stdout so that we can restore it later
    original_stdout = sys.stdout
    # Redirect stdout to the buffer
    sys.stdout = output_buffer
    scope = {}
    try:
        # Execute the code in the specified scope
        exec(code, scope)
    except Exception as e:
        # Handle any execution errors
        output = f"[analytics_api.py] Error during execution: {e}"
    else:
        # Get the content of the buffer
        output = output_buffer.getvalue()
    finally:
        # Restore the original stdout and close the buffer
        sys.stdout = original_stdout
        output_buffer.close()
    return output
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002)
