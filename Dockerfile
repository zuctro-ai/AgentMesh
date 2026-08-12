FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app

# Set PYTHONPATH to root
ENV PYTHONPATH=/app

# Default command runs the Control Plane Gateway
EXPOSE 8000 50051

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
