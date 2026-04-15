FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    pciutils \
    zstd \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama using the official script (now that zstd is available)
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Create the data directory for SQLite
RUN mkdir -p /app/data

# Create a startup script that runs both Ollama daemon and the FastAPI server
# We pull the models at RUNTIME to keep the Docker image small and bypass Railway's size limits.
RUN echo '#!/bin/bash\n\
ollama serve &\n\
\n\
echo "Waiting for Ollama to start..."\n\
while ! curl -s http://localhost:11434 > /dev/null; do\n\
    sleep 2\n\
done\n\
\n\
echo "Ollama is ready. Ensuring Mastermind models are active..."\n\
ollama pull dolphin3:8b\n\
ollama pull qwen2.5-coder:32b\n\
\n\
echo "Starting FastAPI server..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Command to run on Railway
CMD ["/app/start.sh"]

