# src/step2_preprocess.py
# (Anteriormente step2_preprocess.py, refactorizado para ser importable)

import os
import json
from lxml import etree as ET

# --- Configuración ---
SOURCE_ROOT = "1_tibco_project_source"
INTERMEDIATE_DIR = "../2_intermediate_data"
MAP_FILE = os.path.join(INTERMEDIATE_DIR, "project_map.json")
OUTPUT_DIR = os.path.join(INTERMEDIATE_DIR, "preprocessed")


# --- Funciones de Ayuda ---
def get_namespaces(xml_file):
    try:
        return dict([node for _, node in ET.iterparse(xml_file, events=['start-ns'])])
    except ET.XMLSyntaxError:
        return None


# --- Función de Enriquecimiento de Procesos ---
def enrich_process_file(file_path, dependencies, namespaces):
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(file_path, parser)
    root = tree.getroot()

    # Extraer Starter
    starter_element = root.find('pd:starter', namespaces)
    starter_data = {
        "name": starter_element.get('name'),
        "type": starter_element.find('pd:type', namespaces).text,
        "config": {
            child.tag.split('}')[-1]: child.text for child in starter_element.find('config')
        } if starter_element.find('config') is not None else {}
    }

    # Extraer Actividades
    activities_data = []
    activity_elements = root.findall('pd:activity', namespaces)
    for act in activity_elements:
        input_bindings = act.find('pd:inputBindings', namespaces)
        bindings_data = {}
        if input_bindings is not None and len(list(input_bindings)) > 0:
            payload_root = list(input_bindings)[0]
            bindings_data["event_payload_type"] = payload_root.tag.split('}')[-1]
            mappings = []
            for value_of in payload_root.xpath('.//xsl:value-of', namespaces=namespaces):
                target_field = value_of.getparent().tag.split('}')[-1]
                source_expression = value_of.get('select')
                mappings.append({"target_field": target_field, "source_expression": source_expression})
            bindings_data["field_mappings"] = mappings

        activity_data = {
            "name": act.get('name'),
            "type": act.find('pd:type', namespaces).text,
            "config": {
                child.tag.split('}')[-1]: child.text for child in act.find('config')
            } if act.find('config') is not None else {},
            "input_bindings": bindings_data
        }
        activities_data.append(activity_data)

    # Extraer Transiciones
    transitions_data = []
    transition_elements = root.findall('pd:transition', namespaces)
    for trans in transition_elements:
        transition_data = {
            "from": trans.find('pd:from', namespaces).text,
            "to": trans.find('pd:to', namespaces).text,
            "condition": trans.find('pd:conditionType', namespaces).text
        }
        transitions_data.append(transition_data)

    # Ensamblar el JSON enriquecido
    enriched_json = {
        "name": os.path.basename(file_path),
        "path": file_path.replace('\\', '/'),
        "type": "process",
        "dependencies": dependencies,
        "starter": starter_data,
        "activities": activities_data,
        "transitions": transitions_data
    }
    return enriched_json


# --- Función Principal ---
def run_preprocessing_phase():
    print("--- Iniciando Fase 2 (v2.1 - lxml): Pre-procesamiento y Enriquecimiento Semántico ---")

    if not os.path.exists(MAP_FILE):
        print(f"[ERROR] El archivo de mapa '{MAP_FILE}' no existe. Ejecuta la Fase 1 primero.")
        return

    with open(MAP_FILE, 'r', encoding='utf-8') as f:
        project_map = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])

    for relative_path, data in project_map["artifacts"].items():
        full_path = os.path.join(tibco_project_root, relative_path)
        output_path = os.path.join(OUTPUT_DIR, relative_path + ".json")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        enriched_data = None
        if data["type"] == "process" and os.path.exists(full_path):
            print(f"Enriqueciendo: {relative_path}")
            namespaces = get_namespaces(full_path)
            if namespaces is not None:
                namespaces['pd'] = 'http://xmlns.tibco.com/bw/process/2003'
                namespaces['xsl'] = 'http://www.w3.org/1999/XSL/Transform'
                enriched_data = enrich_process_file(full_path, data.get("dependencies", []), namespaces)
        else:
            enriched_data = data.copy()
            enriched_data['path'] = relative_path

        if enriched_data:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=4, ensure_ascii=False)

    print(f"\n--- Fase 2 Completada. Archivos enriquecidos guardados en: '{OUTPUT_DIR}' ---")


if __name__ == "__main__":
    run_preprocessing_phase()