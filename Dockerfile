# Small image for the Python scripts. The AI model runs in a separate "ollama" container.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Default: run every step in order. Override the command to run a single script.
CMD ["python", "run_all.py"]
