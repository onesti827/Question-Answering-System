import json

from chunker import Chunker
from embedder import Embedder
from vector_db import VectorDB

def answer_query(db, embedder, query, top_k=3):
    print(f"\nSearching for: {query}")
    print("-" * 50)
    results = db.query(embedder, query, n_results=top_k)
    print(f"\nFound {top_k} matches:\n")
    for i, (doc, dist) in enumerate(zip(results["documents"], results["distances"])):
        print(f"[{i+1}] Score: {dist:.2f}")
        print(f"{doc[:200]}...\n")
    return results["documents"]

# Main pipeline
def main():
    print("\n>> Phase 3: Question Answering System <<\n")
    # Load dataset
    print("loading articles...")
    try:
        with open("dataset\my_wikinews_subset.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        print(f"error loading dataset: {e}")
        return
    print(f"loaded {len(articles)} articles\n")
    # chunking
    all_chunks = []
    chunk_ids = []
    print("step 1: chunking text...")
    for i, article in enumerate(articles):
        text = article["text"]
        title = article["title"]
        chunks = Chunker.chunk_text(text)
        if i < 3:  # only show first 3
            print(f"  {title[:50]}... -> {len(chunks)} chunks")
        for j, c in enumerate(chunks):
            all_chunks.append(c)
            chunk_ids.append(f"d{i}_c{j}") # d stands for document, c stands for chunk
    print(f"total: {len(all_chunks)} chunks\n")
    # embedding
    print("step 2: creating embeddings...")
    embedder = Embedder()
    sample_emb = embedder.embed(all_chunks[0])[0]
    print(f"dimension: {len(sample_emb)}\n")
    # vector db
    print("step 3: storing in vector database...")
    db = VectorDB(dimension=len(sample_emb))
    db.add_vectors(embedder, all_chunks, chunk_ids)
    print(f"stored {len(all_chunks)} vectors\n")
    # interactive query loop
    print("-" * 50)
    print("ready! enter a query to search")
    print("examples: 'china', 'technology news', 'sports'")
    print("(press enter with no input to exit)")
    print("-" * 50)
    while True:
        user_q = input("\n> ").strip()
        if not user_q:
            print("done")
            break
        answer_query(db, embedder, user_q)

if __name__ == "__main__":
    main()
