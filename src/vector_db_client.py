# src/vector_db_client.py

import chromadb
from sentence_transformers import SentenceTransformer
import os

# --- Configuración ---
DB_PATH = os.path.join("2_intermediate_data", "vector_db")
COLLECTION_NAME = "tibco_knowledge_base"
# Modelo de embeddings multilingüe y de alto rendimiento que se ejecuta localmente.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


class VectorDBClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorDBClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        print("  -> Inicializando Cliente de Base de Datos Vectorial (ChromaDB)...")
        # Asegurarse que el directorio para la DB persistente exista
        os.makedirs(DB_PATH, exist_ok=True)

        # 1. Cargar el modelo de embeddings localmente
        # Este modelo convierte texto a vectores numéricos. Se descarga automáticamente la primera vez.
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"     - Modelo de embeddings '{EMBEDDING_MODEL_NAME}' cargado.")

        # 2. Inicializar el cliente de la base de datos que persiste en disco
        self.client = chromadb.PersistentClient(path=DB_PATH)

        # 3. Obtener o crear la colección donde se almacenarán los datos
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # Usar similitud de coseno
        )
        print(f"     - Conectado a la colección '{COLLECTION_NAME}'.")
        self._initialized = True

    def add_documents(self, documents):
        """Añade documentos (pre-divididos por LangChain) a la colección."""
        if not documents:
            return

        print(f"     - Generando embeddings y añadiendo {len(documents)} fragmentos a la DB...")
        self.collection.add(
            ids=[f"{doc.metadata.get('source', 'unknown')}_page{doc.metadata.get('page', 0)}_{i}" for i, doc in
                 enumerate(documents)],
            documents=[doc.page_content for doc in documents],
            metadatas=[doc.metadata for doc in documents]
        )

    def query(self, query_text: str, n_results: int = 3) -> str:
        """Busca en la DB los fragmentos más relevantes para una consulta."""
        if self.collection.count() == 0:
            print("    [WARN] La base de conocimiento está vacía. No se puede recuperar contexto.")
            return "La base de conocimiento está vacía. No se pudo recuperar contexto."

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

        if not results or not results.get('documents') or not results['documents'][0]:
            return "No se encontró contexto relevante en la base de conocimiento."

        # Concatena los fragmentos recuperados en un solo string
        context_str = "\n\n---\n\n".join(results['documents'][0])
        return context_str


# Instancia global para ser usada por otros módulos
# La inicialización se dispara la primera vez que se importa este módulo.
db_client = VectorDBClient()