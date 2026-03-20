import os
import sys
import time
import json
import struct
import psycopg2
import psycopg2.extras
from psycopg2 import sql
from meilisearch import Client
from faker import Faker
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/cdc_db")
MEILI_HTTP_ADDR = os.getenv("MEILI_HTTP_ADDR", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey")
API_URL = os.getenv("API_URL", "http://api-frontend:8000/api/cdc-notify")
CHECKPOINT_FILE = "/app/lsn_checkpoint.txt"
SLOT_NAME = "my_replication_slot"
PUBLICATION_NAME = "my_publication"

fake = Faker()

class PGOutputParser:
    def __init__(self):
        self.relations = {}

    def parse(self, msg):
        msg_type = chr(msg[0])
        if msg_type == 'R':  # Relation
            return self._parse_relation(msg)
        elif msg_type == 'I':  # Insert
            return self._parse_insert(msg)
        elif msg_type == 'U':  # Update
            return self._parse_update(msg)
        elif msg_type == 'D':  # Delete
            return self._parse_delete(msg)
        elif msg_type == 'B':  # Begin
            return {'type': 'BEGIN'}
        elif msg_type == 'C':  # Commit
            return {'type': 'COMMIT', 'lsn': struct.unpack('>Q', msg[1:9])[0]}
        return None

    def _parse_relation(self, msg):
        pos = 1
        rel_id = struct.unpack('>I', msg[pos:pos+4])[0]
        pos += 4
        
        # Schema name (null-terminated string)
        schema_end = msg.find(b'\x00', pos)
        schema_name = msg[pos:schema_end].decode('utf-8')
        pos = schema_end + 1
        
        # Relation name (null-terminated string)
        rel_end = msg.find(b'\x00', pos)
        rel_name = msg[pos:rel_end].decode('utf-8')
        pos = rel_end + 1
        
        # Replica identity setting (1 byte)
        pos += 1
        
        # Number of columns (2 bytes)
        num_cols = struct.unpack('>H', msg[pos:pos+2])[0]
        pos += 2
        
        columns = []
        for _ in range(num_cols):
            # Flags (1 byte)
            pos += 1
            # Column name (null-terminated string)
            col_end = msg.find(b'\x00', pos)
            col_name = msg[pos:col_end].decode('utf-8')
            pos = col_end + 1
            # Data type ID (4 bytes)
            pos += 4
            # Type modifier (4 bytes)
            pos += 4
            columns.append(col_name)
            
        self.relations[rel_id] = {
            'schema': schema_name,
            'table': rel_name,
            'columns': columns
        }
        return {'type': 'RELATION', 'table': rel_name}

    def _parse_insert(self, msg):
        pos = 1
        rel_id = struct.unpack('>I', msg[pos:pos+4])[0]
        pos += 4
        
        # 'N' for new tuple
        pos += 1
        
        data = self._parse_tuple(msg, pos, rel_id)
        return {'type': 'INSERT', 'table': self.relations[rel_id]['table'], 'data': data}

    def _parse_update(self, msg):
        pos = 1
        rel_id = struct.unpack('>I', msg[pos:pos+4])[0]
        pos += 4
        
        # Optional: 'K' for key or 'O' for old if REPLICA IDENTITY FULL
        if chr(msg[pos]) in ('K', 'O'):
            # Skip old tuple data for simplicity if not needed, but we might need it for PK changes
            # For this task, we assume PK doesn't change frequently or we just use current ID
            num_cols = struct.unpack('>H', msg[pos+1:pos+3])[0]
            pos += 3
            for _ in range(num_cols):
                kind = chr(msg[pos])
                pos += 1
                if kind in ('n', 'u'): continue
                length = struct.unpack('>I', msg[pos:pos+4])[0]
                pos += 4 + length
        
        # 'N' for new tuple
        if chr(msg[pos]) == 'N':
            pos += 1
            data = self._parse_tuple(msg, pos, rel_id)
            return {'type': 'UPDATE', 'table': self.relations[rel_id]['table'], 'data': data}
        return None

    def _parse_delete(self, msg):
        pos = 1
        rel_id = struct.unpack('>I', msg[pos:pos+4])[0]
        pos += 4
        
        # 'K' for key or 'O' for old
        kind = chr(msg[pos])
        pos += 1
        
        data = self._parse_tuple(msg, pos, rel_id)
        return {'type': 'DELETE', 'table': self.relations[rel_id]['table'], 'data': data}

    def _parse_tuple(self, msg, pos, rel_id):
        num_cols = struct.unpack('>H', msg[pos:pos+2])[0]
        pos += 2
        
        data = {}
        columns = self.relations[rel_id]['columns']
        
        for i in range(num_cols):
            kind = chr(msg[pos])
            pos += 1
            if kind == 'n': # Null
                data[columns[i]] = None
            elif kind == 'u': # Unchanged toast
                pass
            elif kind == 't': # Text
                length = struct.unpack('>I', msg[pos:pos+4])[0]
                pos += 4
                val = msg[pos:pos+length].decode('utf-8')
                pos += length
                data[columns[i]] = val
        return data

def seed_data(conn):
    print("Checking for existing data...", flush=True)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM products")
    count = cur.fetchone()[0]
    print(f"Current product count: {count}", flush=True)
    
    if count < 5000:
        print(f"Seeding {5000 - count} more products...")
        
        # Ensure categories exist
        cur.execute("SELECT category_id FROM categories LIMIT 1")
        if not cur.fetchone():
            categories = ['Electronics', 'Books', 'Home & Garden', 'Toys', 'Sports']
            for cat in categories:
                cur.execute("INSERT INTO categories (name) VALUES (%s)", (cat,))
        
        cur.execute("SELECT category_id FROM categories")
        category_ids = [r[0] for r in cur.fetchall()]
        
        batch_size = 500
        for _ in range(0, 5000 - count, batch_size):
            products = []
            for _ in range(min(batch_size, 5000 - count - len(products))):
                products.append((
                    fake.commerce_product_name() if hasattr(fake, 'commerce_product_name') else fake.word(),
                    fake.sentence(),
                    fake.random_number(digits=4) / 100,
                    fake.random_element(category_ids)
                ))
            
            args_str = ','.join(cur.mogrify("(%s,%s,%s,%s)", x).decode('utf-8') for x in products)
            cur.execute("INSERT INTO products (name, description, price, category_id) VALUES " + args_str + " RETURNING product_id")
            product_ids = [r[0] for r in cur.fetchall()]
            
            # Seed inventory
            inventory = [(pid, fake.random_int(min=0, max=100)) for pid in product_ids]
            inv_args_str = ','.join(cur.mogrify("(%s,%s)", x).decode('utf-8') for x in inventory)
            cur.execute("INSERT INTO inventory (product_id, quantity) VALUES " + inv_args_str)
            
            conn.commit()
        print("Seeding complete.")

def main():
    print("Starting CDC Consumer...", flush=True)
    
    # Wait for Meilisearch
    meili_client = Client(MEILI_HTTP_ADDR, MEILI_MASTER_KEY)
    while True:
        try:
            meili_client.health()
            print("Meilisearch is healthy", flush=True)
            break
        except:
            print("Waiting for Meilisearch...", flush=True)
            time.sleep(2)

    # Initialize Meilisearch index
    index = meili_client.index('products')
    index.update_settings({
        'searchableAttributes': ['name', 'description', 'category'],
        'filterableAttributes': ['category', 'in_stock'],
        'sortableAttributes': ['price']
    })

    # Connect to Postgres
    print(f"Connecting to database: {DATABASE_URL}", flush=True)
    conn = psycopg2.connect(DATABASE_URL)
    print("Database connected", flush=True)
    seed_data(conn)
    
    # Setup Logical Replication
    print("Setting up logical replication connection...", flush=True)
    repl_conn = psycopg2.connect(DATABASE_URL, connection_factory=psycopg2.extras.LogicalReplicationConnection)
    print("Logical replication connection established", flush=True)
    cur = repl_conn.cursor()
    
    try:
        cur.create_replication_slot(SLOT_NAME, output_plugin='pgoutput')
    except psycopg2.errors.DuplicateObject:
        pass
    
    # Get last LSN
    start_lsn = 0
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            line = f.read().strip()
            if line:
                start_lsn = int(line)

    print(f"Starting replication from LSN: {start_lsn}")
    
    options = {
        'proto_version': '1',
        'publication_names': PUBLICATION_NAME
    }
    
    cur.start_replication(slot_name=SLOT_NAME, options=options, start_lsn=start_lsn)
    
    parser = PGOutputParser()
    
    def handle_message(msg):
        print(f"DEBUG: Received message type: {chr(msg.payload[0])}", flush=True)
        # Notify Postgres that we received the message
        msg.cursor.send_feedback(write_lsn=msg.data_start, flush_lsn=msg.data_start)
        
        parsed = parser.parse(msg.payload)
        if not parsed:
            return

        if parsed['type'] == 'COMMIT':
            # Save checkpoint
            with open(CHECKPOINT_FILE, 'w') as f:
                f.write(str(msg.data_start))
            return

        if parsed['type'] in ('INSERT', 'UPDATE', 'DELETE') and parsed['table'] == 'products':
            print(f"Processing {parsed['type']} for {parsed['table']}")
            
            data = parsed.get('data')
            if parsed['type'] in ('INSERT', 'UPDATE'):
                # We want a flattened document. Since we only have product data here, 
                # in a real world we might fetch category and inventory, 
                # but for this task, if it's just from the 'products' table, we use what we have.
                # Actually, the requirement says "An INSERT statement executed on the products table... must result in a new document".
                doc = {
                    'id': data['product_id'],
                    'name': data['name'],
                    'description': data['description'],
                    'price': float(data['price']),
                    'category_id': data['category_id']
                }
                index.add_documents([doc], primary_key='id')
            elif parsed['type'] == 'DELETE':
                index.delete_document(data['product_id'])

            # Notify API for SSE
            try:
                requests.post(API_URL, json={
                    'table': parsed['table'],
                    'operation': parsed['type'],
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }, timeout=1)
            except Exception as e:
                print(f"Failed to notify API: {e}")

    cur.consume_stream(handle_message)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)
