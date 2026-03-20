# CDC Pipeline Implementation

A complete Change Data Capture (CDC) pipeline orchestrating PostgreSQL, Meilisearch, and a custom CDC consumer.

## Architecture

- **PostgreSQL**: Source database with logical decoding enabled (`wal_level=logical`).
- **Meilisearch**: Search engine for fast indexing and retrieval.
- **CDC Consumer**: Python service that captures DB changes and updates the search index. It also notifies the API via webhooks.
- **API/Frontend**: Node.js backend serving SSE for real-time updates and a React frontend for the dashboard.

## What You'll Need

To run this pipeline, you only need one thing installed on your computer:

*   **Docker Desktop**: This handles everything else! You don't need to install PostgreSQL, Node.js, or Python locally because they all run inside secure, pre-configured containers.

Make sure Docker is running before you start.

## Quick Start

1. Clone the repository.
2. Run `docker-compose up --build -d`.
3. Open `http://localhost:8009` in your browser.

## API Implementation

The API is implemented using Node.js and Express. It handles two main responsibilities:

### 1. CDC Notification Endpoint
- **Method**: `POST`
- **Endpoint**: `/api/cdc-notify`
- **Purpose**: Received real-time notifications from the CDC Consumer.
- **Request Body Example**:
  ```json
  {
    "table": "products",
    "operation": "INSERT",
    "timestamp": "2026-03-20T15:00:00Z"
  }
  ```

### 2. SSE Stream Endpoint
- **Method**: `GET`
- **Endpoint**: `/api/cdc-stream`
- **Purpose**: Streams CDC event metadata to connected clients.
- **Headers**: `Content-Type: text/event-stream`

## API Reference & Testing Guide

Use these commands to verify every component of the pipeline during your video demo.

### 1. Dashboard API (Node.js)

| Method | Endpoint | Description | Test Command (PowerShell) | Test Command (Bash) |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/health` | API Health Check | `Invoke-RestMethod http://localhost:8009/api/health` | `curl http://localhost:8009/api/health` |
| **GET** | `/api/cdc-stream` | SSE Metadata Stream | `curl.exe -N -i http://localhost:8009/api/cdc-stream` | `curl -N -i http://localhost:8009/api/cdc-stream` |
| **POST** | `/api/cdc-notify` | Manual CDC Trigger | *See below for JSON body* | *See below for JSON body* |

#### Manual CDC Trigger (POST)
**Windows (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8009/api/cdc-notify" -Method Post -ContentType "application/json" -Body '{"table": "products", "operation": "INSERT", "timestamp": "2026-03-20T15:00:00Z"}'
```
**Linux/macOS (Bash):**
```bash
curl -X POST "http://localhost:8009/api/cdc-notify" -H "Content-Type: application/json" -d '{"table": "products", "operation": "INSERT", "timestamp": "2026-03-20T15:00:00Z"}'
```

### 2. Search Engine API (Meilisearch)

| Method | Endpoint | Description | Test Command (PowerShell) | Test Command (Bash) |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/health` | Meilisearch Health | `Invoke-RestMethod http://localhost:7709/health` | `curl http://localhost:7709/health` |
| **POST** | `/indexes/products/search` | Search Products | *See below for JSON body* | *See below for JSON body* |

#### Search Products (POST)
**Windows (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://localhost:7709/indexes/products/search" -Method Post -Headers @{"Authorization"="Bearer masterKey"} -ContentType "application/json" -Body '{"q": "Test Product"}'
```
**Linux/macOS (Bash):**
```bash
curl -X POST "http://localhost:7709/indexes/products/search" -H "Authorization: Bearer masterKey" -H "Content-Type: application/json" --data-binary '{ "q": "Test Product" }'
```

### 3. Database Verification (PostgreSQL)
**All Platforms:**
```bash
# Verify total products (>= 5000)
docker exec cdc_postgres psql -U postgres -d cdc_db -c "SELECT count(*) FROM products;"

# Verify Publication status
docker exec cdc_postgres psql -U postgres -d cdc_db -c "SELECT * FROM pg_publication;"
```

## Video Demo Steps

To demonstrate the full functionality of the CDC pipeline, follow these steps:

### 1. Initial State & Orchestration
- Show `docker-compose.yml` to explain the services (Postgres, Meilisearch, CDC Consumer, API/Frontend).
- Run `docker-compose ps` to show all services are healthy.
- Open the frontend at `http://localhost:8009`. Point out the "LIVE" status indicator.

### 2. Initialization & Seeding
- Connect to Postgres: `docker exec -it cdc_postgres psql -U postgres -d cdc_db`.
- Run `SELECT count(*) FROM products;` to show that 5,000+ products were automatically seeded.
- Search for a product on the frontend to show it's already indexed in Meilisearch.

### 3. Change Data Capture (INSERT)
- In the Postgres terminal, insert a new product:
  ```sql
  INSERT INTO products (name, description, price, category_id) 
  VALUES ('Super Gadget 3000', 'A revolutionary new gadget.', 299.99, 1);
  ```
- Show the **Real-time CDC Feed** on the frontend updating immediately.
- Search for "Super Gadget 3000" and show it appearing in the search results.

### 4. Change Data Capture (UPDATE)
- Update the price of the product:
  ```sql
  UPDATE products SET price = 199.99 WHERE name = 'Super Gadget 3000';
  ```
- Show the feed updating and the price changing in the search results.

### 5. Change Data Capture (DELETE)
- Delete the product:
  ```sql
  DELETE FROM products WHERE name = 'Super Gadget 3000';
  ```
- Show the feed updating and the product disappearing from search results.

### 6. LSN Recovery & Persistence
- Stop the consumer: `docker-compose stop cdc-consumer`.
- Insert a unique product while the consumer is offline:
  ```sql
  INSERT INTO products (name, description, price, category_id) 
  VALUES ('Offline Sync Test', 'This was added while consumer was down.', 99.99, 1);
  ```
- Restart the consumer: `docker-compose start cdc-consumer`.
- Show the product appearing in the feed and search results shortly after restart, demonstrating recovery from the last saved LSN.

### 7. SSE Metadata
- Show a terminal running `curl -N http://localhost:8009/api/cdc-stream`.
- Make a change in the DB and show the JSON metadata streaming in the terminal.
