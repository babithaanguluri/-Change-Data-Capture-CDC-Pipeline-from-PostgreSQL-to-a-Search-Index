FROM node:18-slim

WORKDIR /app

# Install dependencies
COPY package.json .
RUN npm install

# Copy source
COPY . .

# Build frontend (Vite)
RUN npm run build

EXPOSE 8000

CMD ["node", "server.js"]
