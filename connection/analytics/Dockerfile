FROM python:3.9

WORKDIR /usr/analytics

COPY ./* ./

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements_analytics.txt

EXPOSE 5002

CMD ["python3", "analytics_api.py"]
