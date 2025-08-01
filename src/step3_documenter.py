# src/step3_documenter.py

import os
import json
import time
from . import llm_client  # FIX: Importación relativa explícita

# --- Configuración ---
# FIX: Las rutas deben construirse desde la raíz del proyecto, no desde 'src'
PREPROCESSED_DIR = os.path.join("2_intermediate_data", "preprocessed")
OUTPUT_DOCS_DIR = "3_output_documentation"
PROMPT_TEMPLATE_PATH = os.path.join("config", "prompt_template.txt")
CONFIG_PATH = os.path.join("config", "llm_config.json")


def create_documentation_for_artifact(enriched_json_path: str, prompt_template: str, delay: int):
    """Lee un JSON, formatea el prompt, llama al LLM y guarda el resultado."""
    print(f"  Procesando artefacto: {os.path.basename(enriched_json_path)}...")

    try:
        with open(enriched_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get("type") != "process":
            print(f"    -> Omitido (no es un proceso).")
            return

        # Preparar listas de dependencias para el prompt
        dependencies = data.get("dependencies", [])
        shared_resources = "\n    *   ".join([d for d in dependencies if ".shared" in d]) or "Ninguno"
        schemas_and_events = "\n    *   ".join(
            [d for d in dependencies if ".aeschema" in d or ".xsd" in d or ".wsdl" in d]) or "Ninguno"

        # Formatear el prompt con los datos del JSON
        formatted_prompt = prompt_template.format(
            json_content=json.dumps(data, indent=2),
            process_name=data.get("name", "N/A"),
            process_path=data.get("path", "N/A"),
            starter_name=data.get("starter", {}).get("name", "N/A"),
            starter_type=data.get("starter", {}).get("type", "N/A"),
            interval=data.get("starter", {}).get("config", {}).get("TimeInterval", "N/A"),
            unit=data.get("starter", {}).get("config", {}).get("FrequencyIndex", "N/A"),
            shared_resources=shared_resources,
            schemas_and_events=schemas_and_events
        )

        # Llamar al LLM a través de nuestro cliente
        doc_content = llm_client.generate_text(formatted_prompt)

        # Guardar el archivo .md
        base_name = os.path.basename(enriched_json_path).replace('.json', '')
        output_path = os.path.join(OUTPUT_DOCS_DIR, base_name + ".md")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)

        print(f"    -> Documentación guardada en: {output_path}")
        time.sleep(delay)  # Pequeña pausa para no saturar la API

    except Exception as e:
        print(f"    [ERROR] Falló la generación para {os.path.basename(enriched_json_path)}: {e}")


def run_documentation_phase():
    """Función principal de la Fase 3: orquesta la generación de documentos."""
    print("\n--- Iniciando Fase 3: Generación de Documentación con Gemini ---")

    if not os.path.isdir(PREPROCESSED_DIR):
        print(f"[ERROR] El directorio de pre-procesados '{PREPROCESSED_DIR}' no existe.")
        return

    try:
        with open(PROMPT_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            delay = config.get("request_delay_seconds", 1)
    except FileNotFoundError as e:
        print(f"[FATAL] No se pudo encontrar un archivo de configuración esencial: {e}")
        return

    for root, _, files in os.walk(PREPROCESSED_DIR):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                create_documentation_for_artifact(json_path, prompt_template, delay)