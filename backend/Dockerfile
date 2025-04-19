FROM python:alpine

# Set working directory
WORKDIR /app

# Install build dependencies (added linux-headers for psutil)
RUN apk add --no-cache gcc musl-dev postgresql-dev linux-headers

# Create directories with appropriate permissions
RUN mkdir -p /app/tests /app/migrations &&     chmod -R 777 /app

# Copy requirements files
COPY requirements.txt .
COPY requirements-test.txt .

# Install dependencies
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt &&     pip install --no-cache-dir --root-user-action=ignore -r requirements-test.txt

# Copy project files
COPY . .

# Set correct permissions for all files
RUN chmod -R 777 /app

# Expose port
EXPOSE 8000

# Start FastAPI server with hot reloading
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
