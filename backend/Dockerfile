FROM python:3.13-alpine

# Set working directory
WORKDIR /app

# Install build dependencies and curl for health checks
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    linux-headers \
    libffi-dev \
    openssl-dev \
    cargo \
    rust \
    curl

# Create directories with appropriate permissions
RUN mkdir -p /app/tests /app/migrations && \
    chmod -R 777 /app

# Copy requirements files
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Copy project files
COPY . .

# Set correct permissions for all files
RUN chmod -R 777 /app

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Start FastAPI server with hot reloading
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]