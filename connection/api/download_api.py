from flask import Flask, send_from_directory, render_template_string
import os

app = Flask(__name__)

# Define the directory containing files
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the relative path to the file
file_name = "downloads"
file_path = os.path.join(script_dir, file_name)
DIRECTORY = file_path

# Simple HTML template for listing files
TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>File Download</title></head>
<body>
<h1>Available Files</h1>
<ul>
{% for file in files %}
  <li><a href="download/{{ file }}">{{ file }}</a></li>
{% endfor %}
</ul>
</body>
</html>
"""

@app.route("/")
def list_files():
    print(os.getcwd())
    files = os.listdir(DIRECTORY)
    return render_template_string(TEMPLATE, files=files)

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(DIRECTORY, filename, as_attachment=True)

if __name__ == "__main__":
    print(print(os.getcwd()))
    app.run(host='0.0.0.0', port=5004)