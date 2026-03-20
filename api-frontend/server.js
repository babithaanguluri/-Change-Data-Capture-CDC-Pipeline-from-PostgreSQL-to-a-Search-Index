const express = require('express');
const cors = require('cors');
const path = require('path');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 8000;

app.use(cors());
app.use(express.json());

// SSE Clients
let clients = [];

// Health check
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'healthy' });
});

// CDC Notification endpoint (called by consumer)
app.post('/api/cdc-notify', (req, res) => {
  const event = req.body;
  console.log('Received CDC event:', event);
  
  // Forward to SSE clients
  clients.forEach(client => {
    client.res.write(`data: ${JSON.stringify(event)}\n\n`);
  });
  
  res.status(200).json({ success: true });
});

// SSE Stream
app.get('/api/cdc-stream', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });
  
  // Send a comment to keep the connection open and flush headers
  res.write(':ok\n\n');
  
  const clientId = Date.now();
  const newClient = { id: clientId, res };
  clients.push(newClient);
  
  console.log(`New SSE client connected: ${clientId}`);
  
  req.on('close', () => {
    console.log(`SSE client disconnected: ${clientId}`);
    clients = clients.filter(c => c.id !== clientId);
  });
});

// Serve static frontend
app.use(express.static(path.join(__dirname, 'dist')));

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
