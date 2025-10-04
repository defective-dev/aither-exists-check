FROM python:3.12

# Set up a virtual environment to isolate our Python dependencies
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Set the working directory in the container
WORKDIR /app

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Set the entry point for the container
ENTRYPOINT ["python", "/app/main.py", "--config-path", "/config", "--log-path", "/logs"]