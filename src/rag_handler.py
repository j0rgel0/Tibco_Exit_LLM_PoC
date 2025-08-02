# src/rag_handler.py

import os, json, fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions

DB_PATH = "vector_db"
COLLECTION_NAME = "tibco_knowledge_base"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150


class RAGHandler:
    def __init__(self):
        print("  -> Inicializando Cliente de Base de Datos Vectorial (ChromaDB)...")
        try:
            self.client = chromadb.PersistentClient(path=DB_PATH)
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL)
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"     - Conectado a la colección '{COLLECTION_NAME}'.")
        except Exception as e:
            print(f"    [FATAL] No se pudo inicializar ChromaDB: {e}")
            self.client = None

    def _chunk_text(self, text: str):
        """Función auxiliar para dividir un texto largo en fragmentos."""
        return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP)]

    def populate_from_external_docs(self, external_docs_dir: str):
        """Puebla la base de conocimiento desde fuentes externas como PDFs."""
        if not self.client: return
        print(f"\n--- Poblando RAG desde Documentos Externos en '{external_docs_dir}' ---")

        try:
            self.client.delete_collection(name=COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME,
                                                                   embedding_function=self.embedding_function)
            print("  -> Colección anterior limpiada y recreada.")
        except Exception as e:
            print(f"    [INFO] No se pudo eliminar la colección (puede que no existiera). Error: {e}")

        all_chunks, all_metadatas, all_ids = [], [], []
        chunk_id = 0

        if os.path.isdir(external_docs_dir):
            for filename in os.listdir(external_docs_dir):
                if filename.lower().endswith(".pdf"):
                    file_path = os.path.join(external_docs_dir, filename)
                    print(f"    - Procesando PDF: {filename}")
                    try:
                        with fitz.open(file_path) as doc:
                            full_text = "".join(page.get_text() for page in doc)

                        chunks = self._chunk_text(full_text)
                        for chunk in chunks:
                            all_chunks.append(chunk)
                            all_metadatas.append({"source": f"Documentation: {filename}"})
                            all_ids.append(f"pdf_chunk_{chunk_id}")
                            chunk_id += 1
                    except Exception as e:
                        print(f"      [WARN] No se pudo procesar el PDF {filename}: {e}")
        else:
            print(f"  [WARN] El directorio de conocimiento externo '{external_docs_dir}' no existe.")

        if not all_chunks:
            print("  [WARN] No se encontraron documentos externos para añadir a la base de conocimiento.")
            return

        print(f"  -> Añadiendo {len(all_chunks)} fragmentos de documentos externos...")
        if all_chunks:
            self.collection.add(documents=all_chunks, metadatas=all_metadatas, ids=all_ids)
            print("  -> Base de conocimiento poblada con documentos externos.")

    def update_from_generated_docs(self, generated_docs_dir: str):
        """Añade los .md generados a la base de conocimiento existente."""
        if not self.client: return
        print(f"\n--- Actualizando RAG con Documentos Generados en '{generated_docs_dir}' ---")

        all_chunks, all_metadatas, all_ids = [], [], []
        # Empezamos el ID donde lo dejó la ingesta de PDFs
        chunk_id = self.collection.count()

        for root, _, files in os.walk(generated_docs_dir):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        source_name = os.path.relpath(file_path, generated_docs_dir).replace('\\', '/')

                        chunks = self._chunk_text(content)
                        for chunk in chunks:
                            all_chunks.append(chunk)
                            all_metadatas.append({"source": f"Generated Doc: {source_name}"})
                            all_ids.append(f"md_chunk_{chunk_id}")
                            chunk_id += 1
                    except Exception as e:
                        print(f"    [WARN] No se pudo procesar el MD {file}: {e}")

        if not all_chunks:
            print("  [WARN] No se encontraron documentos generados para añadir.")
            return

        print(f"  -> Añadiendo {len(all_chunks)} fragmentos de documentos generados...")
        if all_chunks:
            self.collection.add(documents=all_chunks, metadatas=all_metadatas, ids=all_ids)
            print("  -> Base de conocimiento actualizada con documentos generados.")

    def query_for_context(self, query_text: str, n_results: int = 5) -> str:
        """Busca en la Vector DB y devuelve el contexto relevante."""
        if not self.client or self.collection.count() == 0:
            print("    [WARN] La base de conocimiento está vacía. No se puede recuperar contexto.")
            return "Contexto no disponible."
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self.collection.count())
            )
            context = "\n\n---\n\n".join(results['documents'][0])
            return context
        except Exception as e:
            print(f"    [ERROR] Falló la consulta a la Vector DB: {e}")
            return "Error al consultar la base de conocimiento."