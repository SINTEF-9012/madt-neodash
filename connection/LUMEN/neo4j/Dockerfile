FROM python:3.9

WORKDIR /usr/neo4j

COPY ./* ./

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements_neo4j.txt

EXPOSE 5001

CMD ["python3", "neo4j_api.py"]
