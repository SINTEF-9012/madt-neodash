FROM python:3.9

WORKDIR /usr/influxdb

COPY ./* ./

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements_influxdb.txt


EXPOSE 4999

CMD ["python3", "influxdb_api.py"]
