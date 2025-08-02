# src/step2_preprocess.py (Versión 3.0 - "Deep Parse")

import os
import json
from lxml import etree as ET

# --- Configuración ---
SOURCE_ROOT = "1_tibco_project_source"
INTERMEDIATE_DIR = "2_intermediate_data"
MAP_FILE = os.path.join(INTERMEDIATE_DIR, "project_map.json")
OUTPUT_DIR = os.path.join(INTERMEDIATE_DIR, "preprocessed")

# --- Funciones de Ayuda ---
def get_namespaces(xml_file):
    try:
        return dict([node for _, node in ET.iterparse(xml_file, events=['start-ns'])])
    except ET.XMLSyntaxError:
        return None

def parse_xslt_logic(element, namespaces):
    """
    Parsea recursivamente la lógica XSLT dentro de un binding para extraer condiciones y valores.
    """
    if element is None:
        return None

    # Caso 1: Lógica condicional <xsl:choose>
    choose_node = element.find('xsl:choose', namespaces)
    if choose_node is not None:
        conditions = []
        for when_node in choose_node.findall('xsl:when', namespaces):
            conditions.append({
                "condition": when_node.get("test"),
                "value": when_node.find('.//xsl:value-of', namespaces).get('select') if when_node.find('.//xsl:value-of', namespaces) is not None else "N/A"
            })
        otherwise_node = choose_node.find('xsl:otherwise', namespaces)
        if otherwise_node is not None:
            conditions.append({
                "condition": "otherwise",
                "value": otherwise_node.find('.//xsl:value-of', namespaces).get('select') if otherwise_node.find('.//xsl:value-of', namespaces) is not None else "N/A"
            })
        return {"type": "conditional", "logic": conditions}

    # Caso 2: Mapeo directo <xsl:value-of>
    value_of_node = element.find('xsl:value-of', namespaces)
    if value_of_node is not None:
        return {"type": "direct", "value": value_of_node.get('select')}

    return {"type": "unknown", "value": "No se pudo parsear la lógica"}


# --- Función de Enriquecimiento de Procesos ---
def enrich_process_file(file_path, dependencies, namespaces):
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(file_path, parser)
    root = tree.getroot()

    # --- Starter ---
    starter_element = root.find('pd:starter', namespaces)
    starter_data = None
    if starter_element is not None:
        starter_data = {
            "name": starter_element.get('name'),
            "type": starter_element.find('pd:type', namespaces).text if starter_element.find('pd:type', namespaces) is not None else "N/A",
            "config": {child.tag.split('}')[-1]: child.text for child in starter_element.find('config')} if starter_element.find('config') is not None else {}
        }

    # --- Process Variables ---
    variables_data = []
    variables_element = root.find('pd:processVariables', namespaces)
    if variables_element is not None:
        for var_container in variables_element:
            var_def = var_container.find('.//xsd:element', namespaces)
            if var_def is not None:
                variables_data.append({
                    "name": var_def.get("name"),
                    "type_details": ET.tostring(var_def, pretty_print=True).decode()
                })

    # --- Activities ---
    activities_data = []
    activity_elements = root.findall('pd:activity', namespaces)
    for act in activity_elements:
        config_element = act.find('config')
        config_data = {child.tag.split('}')[-1]: child.text for child in config_element} if config_element is not None else {}

        # Parseo profundo de inputBindings
        input_bindings = act.find('pd:inputBindings', namespaces)
        bindings_data = {}
        if input_bindings is not None and len(list(input_bindings)) > 0:
            payload_root = list(input_bindings)[0]
            bindings_data["payload_root"] = payload_root.tag.split('}')[-1]
            field_mappings = []
            for field in payload_root:
                field_mappings.append({
                    "target_field": field.tag.split('}')[-1],
                    "mapping_logic": parse_xslt_logic(field, namespaces)
                })
            bindings_data["field_mappings"] = field_mappings

        activity_data = {
            "name": act.get('name'),
            "type": act.find('pd:type', namespaces).text if act.find('pd:type', namespaces) is not None else "N/A",
            "config": config_data,
            "input_bindings": bindings_data
        }
        activities_data.append(activity_data)

    # --- Transitions ---
    transitions_data = []
    transition_elements = root.findall('pd:transition', namespaces)
    for trans in transition_elements:
        transitions_data.append({
            "from": trans.find('pd:from', namespaces).text,
            "to": trans.find('pd:to', namespaces).text,
            "condition": trans.find('pd:conditionType', namespaces).text
        })

    # --- Ensamblar JSON ---
    return {
        "name": os.path.basename(file_path),
        "path": file_path.replace('\\', '/'),
        "type": "process",
        "dependencies": dependencies,
        "starter": starter_data,
        "process_variables": variables_data,
        "activities": activities_data,
        "transitions": transitions_data
    }

# --- Función Principal ---
def run_preprocessing_phase():
    print("--- Iniciando Fase 2 (v3.0 - Deep Parse): Pre-procesamiento ---")
    if not os.path.exists(MAP_FILE):
        print(f"[ERROR] El archivo de mapa '{MAP_FILE}' no existe. Ejecuta la Fase 1 primero.")
        return

    with open(MAP_FILE, 'r', encoding='utf-8') as f:
        project_map = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs:
        print(f"[ERROR] No se encontró ninguna carpeta de proyecto dentro de '{SOURCE_ROOT}'."); return
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])

    for relative_path, data in project_map["artifacts"].items():
        full_path = os.path.join(tibco_project_root, relative_path)
        output_path = os.path.join(OUTPUT_DIR, relative_path + ".json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        enriched_data = None
        if data.get("type") == "process" and os.path.exists(full_path):
            print(f"Enriqueciendo: {relative_path}")
            namespaces = get_namespaces(full_path)
            if namespaces is not None:
                namespaces.update({
                    'pd': 'http://xmlns.tibco.com/bw/process/2003',
                    'xsl': 'http://www.w3.org/1999/XSL/Transform',
                    'xsd': 'http://www.w3.org/2001/XMLSchema',
                    'tib': 'http://www.tibco.com/bw/xslt/custom-functions'
                })
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