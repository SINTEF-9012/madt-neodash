FROM python:3.10-slim

RUN mkdir /opt/connection
WORKDIR /opt/connection
COPY . .

RUN conda env create -f enviroment.yml

EXPOSE 3000

CMD ["bash", "run.sh"]


