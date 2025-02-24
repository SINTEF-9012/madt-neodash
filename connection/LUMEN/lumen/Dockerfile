FROM python:3.9

# Create and set the working directory
WORKDIR /usr/lumen

# Copy all files to the working directory in the container
COPY ./* ./

# Convert line endings for run.sh and all .py files to Unix format
RUN sed -i 's/\r$//' run_lumen.sh && \
    find . -name "*.py" -exec sed -i 's/\r$//' {} +

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements.txt

# Expose the necessary ports
EXPOSE 4999
EXPOSE 5000
EXPOSE 5001
EXPOSE 5002

# Give execute permission to run.sh
RUN chmod +x run_lumen.sh

CMD ["bash", "run_lumen.sh"]
