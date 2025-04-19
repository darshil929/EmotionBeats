FROM node:slim

# Set working directory
WORKDIR /app

# Create a directory with appropriate permissions
RUN mkdir -p /app/node_modules && \
    chmod -R 777 /app

# Update npm
RUN npm install -g npm@latest

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy project files
COPY . .

# Set permissions to ensure host user can access files
RUN chmod -R 777 /app

# Expose port
EXPOSE 3000

# Start development server with hot reloading
CMD ["npm", "run", "dev"]
