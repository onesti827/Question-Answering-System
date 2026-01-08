import numpy as np
import faiss

class VectorDB:

    def __init__(self, dimension=384):
        self.index = faiss.IndexFlatL2(dimension)
        self.texts = []
        self.ids = []

    def add_vectors(self, embedder, texts, ids):
        vectors = embedder.embed(texts)
        vectors = np.array(vectors).astype('float32')
        self.index.add(vectors)
        self.texts.extend(texts)
        self.ids.extend(ids)

    def query(self, embedder, query_text, n_results=5):
        query_vec = embedder.embed([query_text]).astype('float32')
        distances, indices = self.index.search(query_vec, n_results)
        docs = [self.texts[i] for i in indices[0]]
        id_list = [self.ids[i] for i in indices[0]]
        return {
            "documents": docs,
            "distances": distances[0].tolist(),
            "ids": id_list
        }