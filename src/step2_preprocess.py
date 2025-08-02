# src/step2_preprocess.py (Versión 6.1 - Captura de Esquemas Internos)

import os, json
from lxml import etree as ET

# --- Configuración ---
SOURCE_ROOT = "1_tibco_project_source"
INTERMEDIATE_DIR = "2_intermediate_data"
MAP_FILE = os.path.join(INTERMEDIATE_DIR, "project_map.json")
OUTPUT_DIR = os.path.join(INTERMEDIATE_DIR, "preprocessed")


# --- Funciones de Ayuda ---
def get_text(element, query, namespaces, default=None):
    if element is None: return default
    node = element.find(query, namespaces)
    return node.text if node is not None else default


def element_to_string(element):
    if element is None: return "No definido"
    for elem in element.getiterator():
        if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]
    ET.indent(element, space="  ")
    return ET.tostring(element, pretty_print=True, encoding='unicode')


def parse_xslt_logic(element, namespaces):
    if element is None: return None
    choose_node = element.find('xsl:choose', namespaces)
    if choose_node is not None:
        logic = {"type": "conditional", "conditions": []}
        for when_node in choose_node.findall('xsl:when', namespaces):
            value_node = when_node.find('.//xsl:value-of', namespaces)
            logic["conditions"].append({
                "if": when_node.get("test"),
                "then": value_node.get('select') if value_node is not None else "N/A"
            })
        otherwise_node = choose_node.find('xsl:otherwise', namespaces)
        if otherwise_node is not None:
            value_node = otherwise_node.find('.//xsl:value-of', namespaces)
            logic["conditions"].append({
                "if": "otherwise",
                "then": value_node.get('select') if value_node is not None else "N/A"
            })
        return logic
    value_of_node = element.find('.//xsl:value-of', namespaces)
    if value_of_node is not None:
        return {"type": "direct", "source": value_of_node.get('select')}
    copy_of_node = element.find('.//xsl:copy-of', namespaces)
    if copy_of_node is not None:
        return {"type": "copy", "source": copy_of_node.get('select')}
    return {"type": "unknown"}


# --- Funciones de Análisis Semántico ---
def analyze_process_metadata(root, namespaces):
    metadata = {"paradigm": "Subproceso", "style": "N/A", "pattern": "N/A"}
    starter = root.find('pd:starter', namespaces)
    if starter is None: return metadata
    starter_type = get_text(starter, 'pd:type', namespaces, "")
    if "HTTPEventSource" in starter_type:
        metadata["paradigm"] = "Servicio Web";
        metadata["style"] = "REST"
        response_activity = root.find('.//pd:activity[pd:type="com.tibco.plugin.http.HTTPResponseActivity"]',
                                      namespaces)
        metadata[
            "pattern"] = "Síncrono (Request-Reply)" if response_activity is not None else "Asíncrono (Fire-and-Forget)"
    elif "SOAPEventSource" in starter_type:
        metadata["paradigm"] = "Servicio Web";
        metadata["style"] = "SOAP";
        metadata["pattern"] = "Síncrono (Request-Reply)"
    elif "TimerEventSource" in starter_type:
        metadata["paradigm"] = "Proceso Programado (Batch)";
        metadata["pattern"] = "Asíncrono"
    elif "JMSEventSource" in starter_type:
        metadata["paradigm"] = "Consumidor de Mensajes";
        metadata["pattern"] = "Asíncrono"
    return metadata


# --- Funciones de Enriquecimiento ---
def enrich_process(file_path, data, namespaces):
    parser = ET.XMLParser(recover=True)
    tree = ET.parse(file_path, parser)
    root = tree.getroot()

    data['metadata'] = analyze_process_metadata(root, namespaces)
    data['name'] = get_text(root, 'pd:name', namespaces)
    data['input_schema_xml'] = element_to_string(root.find('pd:startType', namespaces))
    data['output_schema_xml'] = element_to_string(root.find('pd:endType', namespaces))

    data['process_variables'] = []
    variables_element = root.find('pd:processVariables', namespaces)
    if variables_element is not None:
        for var_container in variables_element:
            var_def = var_container.find('.//xsd:element', namespaces)
            if var_def is not None:
                data['process_variables'].append(
                    {"name": var_def.get("name"), "schema_xml": element_to_string(var_def)})

    data['activities'] = []
    for act in root.findall('.//pd:activity', namespaces):
        config_element = act.find('config')
        config_data = {c.tag.split('}')[-1]: c.text for c in config_element} if config_element is not None else {}

        input_bindings = act.find('pd:inputBindings', namespaces)
        mappings = []
        input_schema = None
        if input_bindings is not None and len(list(input_bindings)) > 0:
            payload_root = list(input_bindings)[0]
            input_schema = element_to_string(payload_root)  # Captura el esquema de entrada de la actividad
            for field in payload_root:
                mappings.append({
                    "target_field": field.tag.split('}')[-1],
                    "mapping_logic": parse_xslt_logic(field, namespaces)
                })

        data['activities'].append({
            "name": act.get('name'), "type": get_text(act, 'pd:type', namespaces),
            "config": config_data, "input_bindings": mappings,
            "activity_input_schema_xml": input_schema
        })

    data['transitions'] = [{"from": get_text(t, 'pd:from', namespaces), "to": get_text(t, 'pd:to', namespaces),
                            "condition": get_text(t, 'pd:conditionType', namespaces)} for t in
                           root.findall('pd:transition', namespaces)]
    return data


# ... (El resto de las funciones de enriquecimiento y la función principal no cambian) ...
def enrich_schema_ae(file_path, data, namespaces):
    parser = ET.XMLParser(recover=True)
    tree = ET.parse(file_path, parser)
    data['classes'] = []
    for class_elem in tree.findall('.//class', namespaces):
        class_info = {"name": class_elem.get('name'), "attributes": []}
        superclass = class_elem.find('superclass', namespaces)
        if superclass is not None: class_info['superclass'] = superclass.get('isRef')
        for attr in class_elem.findall('attribute', namespaces):
            attr_type = attr.find('attributeType', namespaces)
            class_info['attributes'].append({
                "name": get_text(attr, 'name', namespaces),
                "type": attr_type.get('isRef') if attr_type is not None else "N/A"
            })
        data['classes'].append(class_info)
    return data


def enrich_global_variables(file_path, data, namespaces):
    parser = ET.XMLParser(recover=True)
    tree = ET.parse(file_path, parser)
    data['variables'] = []
    for var in tree.findall('.//globalVariable', namespaces):
        data['variables'].append({
            "name": get_text(var, 'name', namespaces),
            "value": get_text(var, 'value', namespaces),
            "type": get_text(var, 'type', namespaces)
        })
    return data


def enrich_shared_http(file_path, data, namespaces):
    parser = ET.XMLParser(recover=True)
    tree = ET.parse(file_path, parser)
    data['host'] = get_text(tree, './/Host', namespaces)
    data['port'] = get_text(tree, './/Port', namespaces)
    return data


def enrich_shared_parse(file_path, data, namespaces):
    parser = ET.XMLParser(recover=True)
    tree = ET.parse(file_path, parser)
    data['format_type'] = get_text(tree, './/FormatType', namespaces)
    data['column_separator'] = get_text(tree, './/ColumnSeparator', namespaces)
    data['line_separator'] = get_text(tree, './/LineSeparator', namespaces)
    data['schema_xml'] = element_to_string(tree.find('.//DataFormat', namespaces))
    return data


def run_preprocessing_phase():
    print("--- Iniciando Fase 2 (v6.1 - Captura de Esquemas Internos): Pre-procesamiento ---")
    if not os.path.exists(MAP_FILE): print(f"[ERROR] Mapa no encontrado."); return
    with open(MAP_FILE, 'r') as f:
        project_map = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs: print(f"[ERROR] No se encontró proyecto TIBCO."); return
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])

    enricher_map = {
        "process": enrich_process, "schema-ae": enrich_schema_ae,
        "global-variables": enrich_global_variables, "shared-http": enrich_shared_http,
        "shared-parse": enrich_shared_parse
    }

    for relative_path, data in project_map["artifacts"].items():
        full_path = os.path.join(tibco_project_root, relative_path)
        output_path = os.path.join(OUTPUT_DIR, relative_path + ".json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if os.path.exists(full_path):
            artifact_type = data.get("type")
            if artifact_type in enricher_map:
                print(f"Enriqueciendo ({artifact_type}): {relative_path}")
                namespaces = {'pd': 'http://xmlns.tibco.com/bw/process/2003',
                              'xsl': 'http://www.w3.org/1999/XSL/Transform', 'xsd': 'http://www.w3.org/2001/XMLSchema'}
                try:
                    enriched_data = enricher_map[artifact_type](full_path, data.copy(), namespaces)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(enriched_data, f, indent=2)
                except Exception as e:
                    print(f"    [WARN] Falló el enriquecimiento para {relative_path}: {e}")