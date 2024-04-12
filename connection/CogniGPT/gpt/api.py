"""CogniGPT: Module providing basic open ai connection."""

# from os import open
from yaml import safe_load
import openai
# from answers import extract_code
from .answers import extract_code

GPT_ENGINE = 'gpt-4'

def load_credential():
    if openai.api_key:
        print('already set')
        return
    with open("openai.credential", 'r') as stream:
        credential_data = safe_load(stream)
    openai_config = credential_data['openai']
    openai.api_type = "azure"
    openai.api_base = openai_config['endpoint']
    openai.api_version = "2023-03-15-preview"
    openai.api_key = openai_config["key"]

def one_shot_call(prompt):
    
    messages = [{"role":"user", "content":prompt}]

    load_credential()
    response = openai.ChatCompletion.create(
        engine=GPT_ENGINE,
        messages = messages,
        temperature=0,
        max_tokens=80,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )
    return response['choices'][0]['message']['content']

def call_with_context(context: list, prompt: str, role='user') -> str:
    context.append({'role': role, 'content': prompt})
    load_credential()
    # print(context)
    response = openai.ChatCompletion.create(
        engine=GPT_ENGINE,
        messages = context,
        temperature=0,
        max_tokens=3000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )
    message = response['choices'][0]['message']
    context.append(message)
    return message['content']

# Original:
#CODE_ORACLE='''
#You are a python programming master. \
#The user will provide you a text describing what he or she wants, \
#and you generate pure Python code based on the text (not command line) \
#In the end of the generated code, after calling the function, please list all the required libraries, each \
#in a line, as comments. '''

# Updated:
CODE_ORACLE='''
You are a Python programming master. \
The user provides you with a task, and you generate a pure Python code to solve the task. \
At the end of the generated code, you must include one line of code to call to the function directly, never use the __main__ segment. \
After calling the function, please list all the required libraries, each in a line, as comments. '''

def generate_code(prompt):

    load_credential()
    messages = [
        {
            "role": "system",
            "content": CODE_ORACLE
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    response = openai.ChatCompletion.create(
        engine="gpt-4",
        messages = messages,
        temperature=0,
        max_tokens=2000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )
    content = response['choices'][0]['message']['content']
    code = extract_code(content)
    # print(code['code'])
    # print(code['lib'])
    return code


if __name__ == "__main__":
    print("Accessed api.py")