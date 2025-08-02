# src/step1_discover.py (Versión 5 - Con Índice de Búsqueda)

import os
import json
import xml.etree.ElementTree as ET
import re

# --- Configuración ---
SOURCE_ROOT = "1_tibco_project_source"
OUTPUT_DIR = "2_intermediate_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "project_map.json")
VERBOSE = False  # Poner en True para depuración detallada


# --- Funciones de Ayuda ---
def get_namespaces(xml_file):
    try:
        return dict([node for _, node in ET.iterparse(xml_file, events=['start-ns'])])
    except ET.ParseError:
        return None


def get_project_relative_path(full_path, root_dir):
    return os.path.relpath(full_path, root_dir).replace('\\', '/')


# --- Funciones de Parseo de Artefactos ---
def parse_process_file(file_path, root_dir):
    if VERBOSE: print(f"\n--- Analizando en detalle (v5): {os.path.basename(file_path)} ---")
    dependencies = set()
    global_vars_refs = set()
    try:
        namespaces = get_namespaces(file_path)
        if namespaces is None: return None
        tree = ET.parse(file_path)
        root = tree.getroot()

        # 1. Búsqueda por tags específicos de TIBCO BE
        known_ref_tags = ['rspRef', 'eventRef', 'destinationRef', 'processName']
        for tag_name in known_ref_tags:
            elements = root.findall(f".//pd:{tag_name}", {'pd': 'http://xmlns.tibco.com/bw/process/2003'})
            for element in elements:
                if element.text:
                    repo_path = element.text.strip()
                    if VERBOSE: print(f"  [1] Encontrada referencia en <{tag_name}>: {repo_path}")
                    # Extraemos solo el nombre del archivo final para la búsqueda
                    base_name = os.path.basename(repo_path)
                    dependencies.add(base_name)
                    if VERBOSE: print(f"      -> Dependencia por nombre base: {base_name}")

        # 2. Análisis de Namespaces
        for prefix, uri in namespaces.items():
            if 'ontology' in uri:
                base_name = os.path.basename(uri)
                dependencies.add(base_name)
                if VERBOSE: print(f"      -> Dependencia por namespace: {base_name}")

        # 3. Búsqueda de variables globales
        xml_content = ET.tostring(root, encoding='unicode')
        var_matches = re.findall(r'%%([\w/.-]+)%%', xml_content)
        for var in var_matches:
            global_vars_refs.add(os.path.basename(var.split('/')[0]))

    except Exception as e:
        print(f"  [ERROR] Ocurrió un error inesperado procesando {file_path}. Error: {e}")
        return None

    return {
        "type": "process",
        "dependencies": sorted(list(dependencies)),
        "global_vars_refs": sorted(list(global_vars_refs))
    }


def parse_generic_artifact(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension in {".folder", ".dat"}: return None
    artifact_type_map = {
        ".sharedjdbc": "shared-jdbc", ".sharedhttp": "shared-http",
        ".sharedjms": "shared-jms", ".sharedrsp": "shared-rsp",
        ".xsd": "schema-xsd", ".wsdl": "service-wsdl",
        ".aeschema": "schema-ae", ".substvar": "global-variables"
    }
    return {"type": artifact_type_map.get(extension, "unknown")}


# --- Función Principal ---
def run_discovery_phase():
    print("--- Iniciando Fase 1 (v5 - Con Índice): Descubrimiento y Mapeo ---")
    if not os.path.isdir(SOURCE_ROOT):
        print(f"[ERROR] El directorio fuente '{SOURCE_ROOT}' no existe.");
        return

    project_map = {"artifacts": {}, "search_index": {}}  # FIX: Añadir el índice de búsqueda
    all_called_processes = set()

    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs:
        print(f"[ERROR] No se encontró ninguna carpeta de proyecto dentro de '{SOURCE_ROOT}'.");
        return
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])
    print(f"Analizando proyecto en: '{tibco_project_root}'")

    # Primera pasada: Crear el índice de búsqueda
    for dirpath, _, filenames in os.walk(tibco_project_root):
        for filename in filenames:
            relative_path = get_project_relative_path(os.path.join(dirpath, filename), tibco_project_root)
            project_map["search_index"][filename] = relative_path

    # Segunda pasada: Analizar artefactos
    for dirpath, _, filenames in os.walk(tibco_project_root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            relative_path = get_project_relative_path(full_path, tibco_project_root)

            artifact_data = None
            if filename.endswith(".process"):
                artifact_data = parse_process_file(full_path, tibco_project_root)
                if artifact_data:
                    # Resolver dependencias usando el índice
                    resolved_deps = set()
                    for dep_name in artifact_data.get("dependencies", []):
                        # Añadir extensiones comunes si no existen
                        possible_names = [dep_name]
                        if not os.path.splitext(dep_name)[1]:
                            possible_names.extend([f"{dep_name}.process", f"{dep_name}.aeschema"])

                        for name in possible_names:
                            if name in project_map["search_index"]:
                                resolved_deps.add(project_map["search_index"][name])
                                if name.endswith(".process"):
                                    all_called_processes.add(project_map["search_index"][name])
                                break  # Encontramos una coincidencia
                    artifact_data["dependencies"] = sorted(list(resolved_deps))
            else:
                artifact_data = parse_generic_artifact(full_path)

            if artifact_data:
                project_map["artifacts"][relative_path] = artifact_data

    all_processes = {path for path, data in project_map["artifacts"].items() if data.get("type") == "process"}
    entry_points = sorted(list(all_processes - all_called_processes))
    project_map["entry_points"] = entry_points

    print(f"\nAnálisis completado. Se encontraron {len(project_map['artifacts'])} artefactos relevantes.")
    print(f"Se identificaron {len(entry_points)} puntos de entrada.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(project_map, f, indent=4, ensure_ascii=False)
    print(f"\n--- Fase 1 Completada. Mapa del proyecto guardado en: '{OUTPUT_FILE}' ---")


if __name__ == "__main__":
    run_discovery_phase()