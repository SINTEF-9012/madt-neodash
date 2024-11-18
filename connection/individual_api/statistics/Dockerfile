FROM python:3.9

WORKDIR /usr/statistics

RUN pip3 install flask 
RUN pip3 install flask-restful
RUN pip3 install scapy
RUN pip3 install pandas
RUN pip3 install matplotlib

COPY . .

EXPOSE 5003

CMD ["python3", "statistics_api.py"]
