import math
from qdrant_client import QdrantClient

def calculate_cosine_similarity(vec_a, vec_b):
    if len(vec_a) != len(vec_b):
        raise ValueError("Dimensions mismatch.")
    
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a**2 for a in vec_a))
    mag_b = math.sqrt(sum(b**2 for b in vec_b))
    
    if mag_a == 0 or mag_b == 0:
        return 0.0
        
    return dot_product / (mag_a * mag_b)

def main():
    client = QdrantClient("http://localhost:6333")
    collection_name = "interview_demo"
    
    target = "Citrus"
    target_vector = [0.85, 0.15, 0.1]
    
    print(f"Target: '{target}' {target_vector}\n")

    print("QDRANT NATIVE SEARCH RESULTS")
    db_results = client.query_points(
        collection_name=collection_name,
        query=target_vector, 
        limit=1
    )
    
    best_db_match = db_results.points[0]
    print(f"Match: '{best_db_match.payload['concept']}'")
    print(f"Qdrant Cosine Score: {best_db_match.score:.4f}\n")

    print("(FROM SCRATCH) SEARCH RESULTS")
    
    # fetching records stored in interview_demo collection
    scroll_results, _ = client.scroll(
        collection_name=collection_name,
        limit=10,
        with_payload=True,
        with_vectors=True
    )
    
    best_custom_score = -1.0
    best_custom_match = None
    
    for record in scroll_results:
        db_vector = record.vector
        score = calculate_cosine_similarity(target_vector, db_vector)
        
        if score > best_custom_score:
            best_custom_score = score
            best_custom_match = record.payload['concept']

    print(f"Match: '{best_custom_match}'")
    print(f"Calculated Cosine Score: {best_custom_score:.4f}\n")

    if abs(best_db_match.score - best_custom_score) < 0.0001:
        print("[SUCCESS] Custom math implementation matches the database engine perfectly.\n")
    else:
        print("[FAILED] Math mismatch detected.\n")

if __name__ == "__main__":
    main()