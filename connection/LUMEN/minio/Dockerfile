FROM python:3.9

WORKDIR /usr/minio

COPY ./* ./

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements_minio.txt


EXPOSE 5000

CMD ["python3", "minio_api.py"]
