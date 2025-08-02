# src/step3_documenter.py (Versión 11 - "Agente de Análisis de Interacciones")

import os, json, time
from . import llm_client

PREPROCESSED_DIR = os.path.join("2_intermediate_data", "preprocessed")
OUTPUT_DOCS_DIR = "3_output_documentation"
PROMPT_DIR = os.path.join("config", "prompt_templates")
CONFIG_PATH = os.path.join("config", "llm_config.json")


def load_prompt(prompt_name: str) -> str:
    try:
        with open(os.path.join(PROMPT_DIR, prompt_name), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""


def generate_documentation_for_process(json_path: str, delay: int):
    """
    Actúa como un agente que documenta un proceso iterando sobre sus interacciones.
    """
    print(f"  Agente analizando: {os.path.basename(json_path)}...")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            main_process_data = json.load(f)

        # --- 1. Cargar Prompts del Agente ---
        summary_prompt = load_prompt("process_summary_prompt.txt")
        interaction_prompt = load_prompt("interaction_prompt.txt")

        # --- 2. Ensamblar el Documento Final por Partes ---
        doc_parts = [f"# Especificación Técnica: {main_process_data.get('name', 'N/A')}"]

        # Parte A: Resumen y Metadatos (LLM)
        print("    -> Generando resumen...")
        summary_context = {"metadata": main_process_data.get("metadata"),
                           "activities": main_process_data.get("activities")}
        summary = llm_client.generate_text(
            summary_prompt.replace("{json_content}", json.dumps(summary_context, indent=2)))
        doc_parts.append(summary)
        doc_parts.append("\n---\n")

        # Parte B: Contratos de Interfaz (Directo)
        doc_parts.append("## Contrato de Interfaz del Proceso")
        doc_parts.append("### Esquema de Entrada (`<startType>`)")
        doc_parts.append(f"```xml\n{main_process_data.get('input_schema_xml', 'No definido')}\n```")
        doc_parts.append("### Esquema de Salida (`<endType>`)")
        doc_parts.append(f"```xml\n{main_process_data.get('output_schema_xml', 'No definido')}\n```")
        doc_parts.append("\n---\n")

        # Parte C: Bucle de Interacciones (LLM por cada interacción)
        doc_parts.append("## Secuencia de Actividades y Análisis de Interacciones")
        for activity in main_process_data.get("activities", []):
            activity_type = activity.get("type")

            if activity_type == "com.tibco.pe.core.CallProcessActivity":
                print(f"    -> Analizando interacción con: {activity.get('name')}")
                subprocess_name = activity.get("config", {}).get("processName", "").lstrip('/')
                subprocess_json_path = os.path.join(PREPROCESSED_DIR, subprocess_name + ".json")

                if os.path.exists(subprocess_json_path):
                    with open(subprocess_json_path, 'r', encoding='utf-8') as f:
                        subprocess_data = json.load(f)

                    # Llamada al LLM para esta interacción específica
                    prompt = interaction_prompt.replace("{main_process_json}", json.dumps(main_process_data, indent=2))
                    prompt = prompt.replace("{subprocess_json}", json.dumps(subprocess_data, indent=2))
                    prompt = prompt.replace("{calling_activity_json}", json.dumps(activity, indent=2))
                    interaction_md = llm_client.generate_text(prompt)
                    doc_parts.append(interaction_md)
                else:
                    doc_parts.append(
                        f"### Actividad: `{activity.get('name')}`\n*   **Error:** No se encontró el archivo JSON para el subproceso `{subprocess_name}`.")
            else:
                # Documentar actividades que no son llamadas a subprocesos (lógica simple)
                doc_parts.append(f"### Actividad: `{activity.get('name')}`")
                doc_parts.append(f"*   **Tipo:** `{activity_type}`")
                # (Se puede añadir más lógica aquí para otros tipos de actividades si es necesario)

        # --- 3. Guardar el Documento Ensamblado ---
        final_doc = "\n".join(doc_parts)
        relative_path = os.path.relpath(json_path, PREPROCESSED_DIR)
        md_path = relative_path.replace('.json', '.md')
        output_path = os.path.join(OUTPUT_DOCS_DIR, md_path)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_doc)

        print(f"    -> Documento ensamblado guardado en: {output_path}")
        time.sleep(delay)

    except Exception as e:
        print(f"    [ERROR] Falló la generación para {os.path.basename(json_path)}: {e}")


def run_atomic_documentation_phase():
    print("\n--- Iniciando Fase 3 (Agente de Análisis): Documentación Detallada ---")
    if not os.path.isdir(PREPROCESSED_DIR): print(f"[ERROR] Directorio pre-procesado no encontrado."); return
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        delay = config.get("request_delay_seconds", 1)
    except FileNotFoundError as e:
        print(f"[FATAL] Archivo de config no encontrado: {e}"); return

    for root, _, files in os.walk(PREPROCESSED_DIR):
        for file in files:
            if file.endswith(".process.json"):
                json_path = os.path.join(root, file)
                generate_documentation_for_process(json_path, delay)