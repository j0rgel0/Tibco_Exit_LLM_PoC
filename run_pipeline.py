# run_pipeline.py (Ubicado en la raíz del proyecto)

from src.step1_discover import run_discovery_phase
from src.step2_preprocess import run_preprocessing_phase
from src.step3_documenter import run_atomic_documentation_phase
from src.step4_assembler import run_assembly_phase
from src.step5_build_html import run_html_build_phase
from src.llm_client import initialize_llm
from src.rag_handler import RAGHandler

KNOWLEDGE_BASE_SOURCE_DIR = "knowledge_base_source"


def main():
    """Orquesta la ejecución de todo el pipeline con Agente de Análisis y RAG."""
    print("===== INICIANDO PIPELINE CON AGENTE DE ANÁLISIS Y RAG DE DOBLE FUENTE =====")

    # --- Inicialización de Componentes ---
    rag_handler = RAGHandler()
    if not initialize_llm():
        print("[ERROR] El pipeline se detuvo porque el cliente LLM no pudo inicializarse.")
        return

    # --- FASE 1: Descubrir artefactos y dependencias ---
    run_discovery_phase()

    # --- FASE 2: Enriquecer los artefactos con su estructura interna ---
    run_preprocessing_phase()

    # --- FASE 3A: Poblar la base de conocimiento RAG con la documentación externa (PDFs) ---
    rag_handler.populate_from_external_docs(KNOWLEDGE_BASE_SOURCE_DIR)

    # --- FASE 3B: El Agente documenta cada proceso, consultando el RAG si es necesario ---
    # (La versión actual de step3 no consulta, pero está lista para hacerlo si se añade la lógica)
    run_atomic_documentation_phase()

    # --- FASE 3C: Actualizar la base de conocimiento con los documentos recién generados ---
    rag_handler.update_from_generated_docs("3_output_documentation")

    # --- FASE 4: Ensamblar un resumen de alto nivel usando el conocimiento COMPLETO de RAG ---
    run_assembly_phase(rag_handler)

    # --- FASE 5: Construir el documento HTML final ---
    run_html_build_phase()

    print("\n===== PIPELINE COMPLETADO =====")
    print(f"Revisa la documentación final en el archivo: '3_output_documentation/TIBCO_Migration_Specification.html'")


if __name__ == "__main__":
    main()