from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

def initialize_qdrant():
    client = QdrantClient("http://localhost:6333")
    collection_name = "interview_demo"

    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=3, distance=Distance.COSINE),
    )

    toy_data = [
        {"id": 1, "vector": [0.9, 0.1, 0.1], "payload": {"concept": "Apple", "category": "Fruit"}},
        {"id": 2, "vector": [0.8, 0.2, 0.1], "payload": {"concept": "Banana", "category": "Fruit"}},
        {"id": 3, "vector": [0.1, 0.1, 0.9], "payload": {"concept": "Car", "category": "Vehicle"}},
    ]

    points = []
    for item in toy_data:
        print(f"  -> {item['payload']['concept']} : {item['vector']}")
        points.append(
            PointStruct(id=item["id"], vector=item["vector"], payload=item["payload"])
        )

    # Insert into the database
    client.upsert(collection_name=collection_name, points=points)
    print("\n[SUCCESS] Vectors successfully inserted into Qdrant.")
    print("[SUCCESS] Database is primed for the similarity showdown.")

if __name__ == "__main__":
    initialize_qdrant()