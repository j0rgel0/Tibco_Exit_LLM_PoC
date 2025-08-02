# build_knowledge_base.py

import os
from src.vector_db_client import VectorDBClient
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Configuración ---
KNOWLEDGE_SOURCE_DIR = "knowledge_base_source"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def run_knowledge_base_build():
    """
    Lee documentos desde KNOWLEDGE_SOURCE_DIR, los procesa y los añade
    a la base de datos vectorial local.
    """
    print("--- Iniciando Construcción de la Base de Conocimiento Local (RAG) ---")
    if not os.path.isdir(KNOWLEDGE_SOURCE_DIR):
        print(f"[ERROR] El directorio '{KNOWLEDGE_SOURCE_DIR}' no fue encontrado.")
        print("Por favor, créalo y añade tus archivos de documentación (ej. PDFs).")
        return

    docs_to_process = [f for f in os.listdir(KNOWLEDGE_SOURCE_DIR) if f.endswith(".pdf")]
    if not docs_to_process:
        print(
            f"[WARN] No se encontraron archivos PDF en '{KNOWLEDGE_SOURCE_DIR}'. La base de conocimiento estará vacía.")
        return

    print(f"Se encontraron {len(docs_to_process)} documentos para procesar.")

    # Inicializa el cliente de la base de datos vectorial
    db_client = VectorDBClient()

    # Inicializa el divisor de texto
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    total_chunks = 0
    for doc_name in docs_to_process:
        try:
            full_path = os.path.join(KNOWLEDGE_SOURCE_DIR, doc_name)
            print(f"  -> Procesando: {doc_name}")

            # 1. Cargar el documento PDF
            loader = PyPDFLoader(full_path)
            documents = loader.load()

            # 2. Dividir el texto en fragmentos (chunks)
            chunks = text_splitter.split_documents(documents)
            print(f"     - Documento dividido en {len(chunks)} fragmentos.")

            # 3. Añadir los fragmentos a la base de datos vectorial
            db_client.add_documents(chunks)
            total_chunks += len(chunks)

        except Exception as e:
            print(f"    [ERROR] Falló el procesamiento de {doc_name}: {e}")

    print(f"\n--- Construcción Finalizada. Se han indexado {total_chunks} fragmentos de texto. ---")


if __name__ == "__main__":
    run_knowledge_base_build()