# src/step4_assembler.py

import os, json
from .rag_handler import RAGHandler

OUTPUT_DOCS_DIR = "3_output_documentation"
MAP_FILE = os.path.join("2_intermediate_data", "project_map.json")
PROMPT_TEMPLATE_PATH = os.path.join("config", "prompt_templates", "final_summary_prompt.txt")


def run_assembly_phase(rag_handler: RAGHandler):
    """Usa RAG para buscar contexto y luego crea un README.md de alto nivel."""
    print("\n--- Iniciando Fase 4 (Ensamblaje con RAG): Creando Resumen de Alto Nivel ---")

    try:
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            project_map = json.load(f)
        entry_points = project_map.get("entry_points", [])
    except FileNotFoundError:
        print("[WARN] No se encontró el mapa del proyecto, el resumen no incluirá los puntos de entrada.")
        entry_points = []

    if not entry_points:
        print("[WARN] No se encontraron puntos de entrada. El resumen puede ser genérico.")

    # Crear una consulta para RAG basada en los puntos de entrada
    query = f"Genera un resumen del flujo principal del sistema comenzando desde los puntos de entrada: {', '.join(entry_points)}"
    print(f"  -> Buscando contexto en la Vector DB para: '{query}'...")

    # FIX: Cambiar 'query_knowledge_base' por el nombre correcto 'query_for_context'
    rag_context = rag_handler.query_for_context(query, n_results=5)

    print("  -> Llamando al LLM para el resumen final con contexto RAG...")
    try:
        with open(PROMPT_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        final_prompt = prompt_template.format(
            entry_points_list="- " + "\n- ".join([f"`{p}`" for p in entry_points]),
            rag_context=rag_context
        )

        # Importar aquí para evitar dependencia circular
        from . import llm_client
        summary_content = llm_client.generate_text(final_prompt)

        output_path = os.path.join(OUTPUT_DOCS_DIR, "README.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)

        print(f"    -> Resumen de alto nivel guardado en: {output_path}")

    except Exception as e:
        print(f"    [ERROR] Falló la fase de ensamblaje: {e}")