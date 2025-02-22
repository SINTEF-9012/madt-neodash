FROM python:3.9

# Create and set the working directory
WORKDIR /usr/full_api

COPY ./* ./

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements_full.txt

EXPOSE 5000

CMD ["python3", "full_api.py"]
