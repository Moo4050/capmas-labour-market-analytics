import pandas as pd
import requests
import uuid
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
CSV_PATH = r"C:\Users\abdoe\Downloads\Rag_data.csv"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "rag_data"
BATCH_SIZE = 100
WORKERS = 5

def create_collection():
    requests.delete(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    data = {"vectors": {"size": 768, "distance": "Cosine"}}
    resp = requests.put(f"{QDRANT_URL}/collections/{COLLECTION_NAME}", json=data)
    print("Collection created:", resp.status_code)

def get_embedding(text):
    resp = requests.post(OLLAMA_URL, json={
        "model": "nomic-embed-text",
        "prompt": text
    }, timeout=60)
    return resp.json()["embedding"]

def row_to_text(row):
    parts = [f"{col}: {val}" for col, val in row.items() 
             if pd.notna(val) and str(val).strip() != ""]
    return " | ".join(parts)

def process_row(args):
    idx, row = args
    try:
        text = row_to_text(row)
        embedding = get_embedding(text)
        return {
            "id": str(uuid.uuid4()),
            "vector": embedding,
            "payload": {
                "text": text,
                "row_index": idx,
                **{k: str(v) for k, v in row.items() if pd.notna(v)}
            }
        }
    except:
        return None

def upload_batch(points):
    try:
        requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
            json={"points": points},
            timeout=60
        )
    except:
        pass

# Main
print("Reading CSV...")
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', low_memory=False)
print(f"Total rows: {len(df)}")

create_collection()

points = []
errors = 0
rows = list(df.iterrows())

with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    futures = {executor.submit(process_row, row): row for row in rows}
    
    with tqdm(total=len(rows), desc="Embedding") as pbar:
        for future in as_completed(futures):
            result = future.result()
            if result:
                points.append(result)
            else:
                errors += 1
            
            if len(points) >= BATCH_SIZE:
                upload_batch(points)
                points = []
            
            pbar.update(1)

if points:
    upload_batch(points)

print(f"\nDone! Errors: {errors}")
print("All data in Qdrant!")