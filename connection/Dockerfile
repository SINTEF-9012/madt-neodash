FROM python:3.10-slim

RUN mkdir /opt/connection
WORKDIR /opt/connection

COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 3000

CMD ["bash", "run.sh"]


