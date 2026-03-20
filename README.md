# CDC Pipeline Implementation

A complete Change Data Capture (CDC) pipeline orchestrating PostgreSQL, Meilisearch, and a custom CDC consumer.

## Architecture

- **PostgreSQL**: Source database with logical decoding enabled (`wal_level=logical`).
- **Meilisearch**: Search engine for fast indexing and retrieval.
- **CDC Consumer**: Python service that captures DB changes and updates the search index. It also notifies the API via webhooks.
- **API/Frontend**: Node.js backend serving SSE for real-time updates and a React frontend for the dashboard.

## Requirements

- Docker and Docker Compose

20: 3. Open `http://localhost:8009` in your browser.
21: 
22: ## API Implementation
23: 
24: The API is implemented using Node.js and Express. It handles two main responsibilities:
25: 
26: ### 1. CDC Notification Endpoint
27: - **Endpoint**: `POST /api/cdc-notify`
28: - **Purpose**: Received real-time notifications from the CDC Consumer.
29: - **Implementation**:
30:   ```javascript
31:   app.post('/api/cdc-notify', (req, res) => {
32:     const event = req.body;
33:     // Broadcast to all connected SSE clients
34:     clients.forEach(client => {
35:       client.res.write(`data: ${JSON.stringify(event)}\n\n`);
36:     });
37:     res.status(200).json({ success: true });
38:   });
39:   ```
40: - **Request Body Example**:
41:   ```json
42:   {
43:     "table": "products",
44:     "operation": "INSERT",
45:     "timestamp": "2026-03-20T15:00:00Z"
46:   }
47:   ```
48: 
49: ### 2. SSE Stream Endpoint
50: - **Endpoint**: `GET /api/cdc-stream`
51: - **Purpose**: Streams CDC event metadata to connected clients.
52: - **Headers**: `Content-Type: text/event-stream`
53: - **Implementation**:
54:   ```javascript
55:   app.get('/api/cdc-stream', (req, res) => {
56:     res.setHeader('Content-Type', 'text/event-stream');
57:     res.setHeader('Cache-Control', 'no-cache');
58:     res.setHeader('Connection', 'keep-alive');
59:     // Add client to the list
60:     const newClient = { id: Date.now(), res };
61:     clients.push(newClient);
62:     // Remove client on disconnect
63:     req.on('close', () => {
64:       clients = clients.filter(c => c.id !== newClient.id);
65:     });
66:   });
67:   ```
68: 
69: ## API Reference & Testing Guide
70: 
71: Use these commands to verify every component of the pipeline during your video demo.
72: 
73: ### 1. Dashboard API (Node.js)
74: 
| Method | Endpoint | Description | Test Command (PowerShell) | Test Command (Bash) |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/health` | API Health Check | `Invoke-RestMethod http://localhost:8009/api/health` | `curl http://localhost:8009/api/health` |
| **GET** | `/api/cdc-stream` | SSE Metadata Stream | `curl.exe -N -i http://localhost:8009/api/cdc-stream` | `curl -N -i http://localhost:8009/api/cdc-stream` |
| **POST** | `/api/cdc-notify` | Manual CDC Trigger | *See below for JSON body* | *See below for JSON body* |
75: 
76: #### Manual CDC Trigger (POST)
77: **Windows (PowerShell):**
78: ```powershell
79: Invoke-RestMethod -Uri "http://localhost:8009/api/cdc-notify" -Method Post -ContentType "application/json" -Body '{"table": "products", "operation": "INSERT", "timestamp": "2026-03-20T15:00:00Z"}'
80: ```
81: **Linux/macOS (Bash):**
82: ```bash
83: curl -X POST "http://localhost:8009/api/cdc-notify" -H "Content-Type: application/json" -d '{"table": "products", "operation": "INSERT", "timestamp": "2026-03-20T15:00:00Z"}'
84: ```
85: 
86: ### 2. Search Engine API (Meilisearch)
87: 
| Method | Endpoint | Description | Test Command (PowerShell) | Test Command (Bash) |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/health` | Meilisearch Health | `Invoke-RestMethod http://localhost:7709/health` | `curl http://localhost:7709/health` |
| **POST** | `/indexes/products/search` | Search Products | *See below for JSON body* | *See below for JSON body* |
88: 
89: #### Search Products (POST)
90: **Windows (PowerShell):**
91: ```powershell
92: Invoke-RestMethod -Uri "http://localhost:7709/indexes/products/search" -Method Post -Headers @{"Authorization"="Bearer masterKey"} -ContentType "application/json" -Body '{"q": "Test Product"}'
93: ```
94: **Linux/macOS (Bash):**
95: ```bash
96: curl -X POST "http://localhost:7709/indexes/products/search" -H "Authorization: Bearer masterKey" -H "Content-Type: application/json" --data-binary '{ "q": "Test Product" }'
97: ```
98: 
99: ### 3. Database Verification (PostgreSQL)
100: **All Platforms:**
101: ```bash
102: # Verify total products (>= 5000)
103: docker exec cdc_postgres psql -U postgres -d cdc_db -c "SELECT count(*) FROM products;"
104: 
105: # Verify Publication status
106: docker exec cdc_postgres psql -U postgres -d cdc_db -c "SELECT * FROM pg_publication;"
107: ```
108: 
109: ## Video Demo Steps

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
