# Use official Python image from the Docker Hub
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=your_openai_api_key

# Set working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

RUN chmod +x docker-entrypoint.sh

# 5000: Flask web UI / API — 8000: MCP streamable-http (when APP_MODE=mcp + MCP_TRANSPORT=streamable-http)
EXPOSE 5000 8000

ENV APP_MODE=flask

ENTRYPOINT ["./docker-entrypoint.sh"]
