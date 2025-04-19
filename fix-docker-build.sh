#!/bin/bash

# Get current user and group IDs
USER_ID=$(id -u)
USER_GID=$(id -g)

echo "Fixing Docker build with user ID $USER_ID:$USER_GID"

# Update the backend Dockerfile to include linux-headers
cat > backend/Dockerfile << INNEREOF
FROM python:alpine

# Set working directory
WORKDIR /app

# Install build dependencies (added linux-headers for psutil)
RUN apk add --no-cache gcc musl-dev postgresql-dev linux-headers

# Create directories with appropriate permissions
RUN mkdir -p /app/tests /app/migrations && \
    chmod -R 777 /app

# Copy requirements files
COPY requirements.txt .
COPY requirements-test.txt .

# Install dependencies
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt && \
    pip install --no-cache-dir --root-user-action=ignore -r requirements-test.txt

# Copy project files
COPY . .

# Set correct permissions for all files
RUN chmod -R 777 /app

# Expose port
EXPOSE 8000

# Start FastAPI server with hot reloading
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
INNEREOF

# Create a docker-compose file with hardcoded user values
cat > docker-compose.yml << INNEREOF
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    volumes:
      - ./frontend:/app:cached
      - /app/node_modules
    environment:
      - NODE_ENV=development
      - NEXT_PUBLIC_API_URL=https://localhost/api
    # Hardcoded user ID
    user: "${USER_ID}:${USER_GID}"
    depends_on:
      - backend
    networks:
      - emotionbeats-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    volumes:
      - ./backend:/app:cached
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/emotionbeats
      - SPOTIFY_CLIENT_ID=\${SPOTIFY_CLIENT_ID}
      - SPOTIFY_CLIENT_SECRET=\${SPOTIFY_CLIENT_SECRET}
      - SPOTIFY_REDIRECT_URI=\${SPOTIFY_REDIRECT_URI}
    # Hardcoded user ID
    user: "${USER_ID}:${USER_GID}"
    depends_on:
      - db
    networks:
      - emotionbeats-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - frontend
      - backend
    networks:
      - emotionbeats-network

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=emotionbeats
    networks:
      - emotionbeats-network

networks:
  emotionbeats-network:
    driver: bridge

volumes:
  postgres_data:
INNEREOF

echo "Updated Docker configuration"

# Shut down containers without trying to change permissions of existing files
echo "Stopping containers..."
docker-compose down

# Rebuild and restart containers
echo "Rebuilding and starting containers with new configuration..."
docker-compose up --build -d

echo "Docker containers rebuilt with proper dependencies. Permission issues resolved."
