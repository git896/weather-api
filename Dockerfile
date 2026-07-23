# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the API code
COPY . .

# App Runner expects the container to listen on the port it's configured
# with. 8000 matches what we've been using locally.
EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
