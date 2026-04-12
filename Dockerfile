FROM python:3.11-slim

WORKDIR /app

# Install dependencies and curl for Ollama
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    pciutils \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama directly (more robust in Docker)
RUN curl -L https://ollama.com/download/ollama-linux-amd64 -o /usr/bin/ollama && \
    chmod +x /usr/bin/ollama

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-pull the dolphin-llama3 model into the image
# We start the server in the background, wait for it, pull the model, then stop the server.
RUN ollama serve & \
    sleep 5 && \
    ollama pull dolphin-llama3 && \
    pkill -f "ollama serve"

# Copy the rest of the project
COPY . .

# Create the data directory for SQLite
RUN mkdir -p /app/data

# Create a startup script that runs both Ollama daemon and the FastAPI server
RUN echo '#!/bin/bash\n\
ollama serve &\n\
\n\
echo "Waiting for Ollama to start..."\n\
while ! curl -s http://localhost:11434 > /dev/null; do\n\
    sleep 2\n\
done\n\
\n\
echo "Ollama is ready. Starting FastAPI server..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Command to run on Railway
CMD ["/app/start.sh"]

