FROM node:22-slim

WORKDIR /app

# Install language runtimes and compilers
RUN apt-get update && apt-get install -y --no-install-recommends 
    python3 
    default-jdk 
    gcc 
    g++ 
    && rm -rf /var/lib/apt/lists/*

# Install Node.js backend dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Copy backend source code
COPY . .

ENV NODE_ENV=production

EXPOSE 5000

CMD ["node", "server.js"]