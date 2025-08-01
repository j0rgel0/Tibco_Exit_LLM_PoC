# src/step1_discover.py
# (Anteriormente step1_discover.py, refactorizado para ser importable)

import os
import json
import xml.etree.ElementTree as ET
import re

# --- Configuración ---
SOURCE_ROOT = "1_tibco_project_source"
OUTPUT_DIR = "../2_intermediate_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "project_map.json")
VERBOSE = True


# --- Funciones de Ayuda ---
def get_namespaces(xml_file):
    try:
        return dict([node for _, node in ET.iterparse(xml_file, events=['start-ns'])])
    except ET.ParseError:
        return None


def get_project_relative_path(full_path, root_dir):
    return os.path.relpath(full_path, root_dir)


# --- Funciones de Parseo de Artefactos ---
def parse_process_file(file_path, root_dir):
    if VERBOSE: print(f"\n--- Analizando en detalle (v4): {os.path.basename(file_path)} ---")

    dependencies = set()
    global_vars_refs = set()

    try:
        namespaces = get_namespaces(file_path)
        if namespaces is None: return None

        tree = ET.parse(file_path)
        root = tree.getroot()

        # 1. Búsqueda por tags específicos de TIBCO BE
        known_ref_tags = ['rspRef', 'eventRef', 'destinationRef']
        for tag_name in known_ref_tags:
            # Busca en cualquier namespace
            elements = root.findall(f".//{{{namespaces.get('pd', '')}}}{tag_name}")
            if not elements: elements = root.findall(f".//{tag_name}")

            for element in elements:
                if element.text:
                    repo_path = element.text.strip()
                    if VERBOSE: print(f"  [1] Encontrada referencia en <{tag_name}>: {repo_path}")
                    filename = repo_path.lstrip('/')
                    if not os.path.splitext(filename)[1]:
                        filename += ".aeschema"
                    dependencies.add(filename)
                    if VERBOSE: print(f"      -> Dependencia inferida: {filename}")

        # 2. Análisis de Namespaces para dependencias de esquemas
        for prefix, uri in namespaces.items():
            if 'ontology' in uri:
                if VERBOSE: print(f"  [2] Encontrado namespace de ontología: {uri}")
                parts = uri.split('/ontology/')
                if len(parts) > 1:
                    schema_path = parts[1] + ".aeschema"
                    dependencies.add(schema_path)
                    if VERBOSE: print(f"      -> Dependencia de esquema inferida: {schema_path}")

        # 3. Búsqueda genérica de variables globales
        xml_content = ET.tostring(root, encoding='unicode')
        var_matches = re.findall(r'%%([\w/.-]+)%%', xml_content)
        for var in var_matches:
            var_parts = var.split('/')
            if len(var_parts) > 1:
                ref_file = f"{var_parts[0]}.substvar"
                if ref_file not in global_vars_refs:
                    global_vars_refs.add(ref_file)
                    if VERBOSE: print(f"  [3] Referencia a variable global encontrada: {ref_file}")

    except Exception as e:
        print(f"  [ERROR] Ocurrió un error inesperado procesando {file_path}. Error: {e}")
        return None

    if VERBOSE: print("--- Fin del análisis detallado ---")
    return {
        "type": "process",
        "dependencies": sorted(list(dependencies)),
        "global_vars_refs": sorted(list(global_vars_refs))
    }


def parse_generic_artifact(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension in {".folder", ".dat"}:
        return None

    artifact_type_map = {
        ".sharedjdbc": "shared-jdbc", ".sharedhttp": "shared-http",
        ".sharedjms": "shared-jms", ".sharedrsp": "shared-rsp",
        ".xsd": "schema-xsd", ".wsdl": "service-wsdl",
        ".aeschema": "schema-ae", ".substvar": "global-variables"
    }
    return {"type": artifact_type_map.get(extension, "unknown"), "dependencies": [], "global_vars_refs": []}


# --- Función Principal ---
def run_discovery_phase():
    print("--- Iniciando Fase 1 (Versión 4 - Final): Descubrimiento y Mapeo ---")

    if not os.path.isdir(SOURCE_ROOT):
        print(f"[ERROR] El directorio fuente '{SOURCE_ROOT}' no existe.")
        return

    project_map = {"artifacts": {}}
    all_called_processes = set()

    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs:
        print(f"[ERROR] No se encontró ninguna carpeta de proyecto dentro de '{SOURCE_ROOT}'.")
        return

    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])
    print(f"Analizando proyecto en: '{tibco_project_root}'")

    for dirpath, _, filenames in os.walk(tibco_project_root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            relative_path = get_project_relative_path(full_path, tibco_project_root).replace('\\', '/')

            artifact_data = None
            if filename.endswith(".process"):
                artifact_data = parse_process_file(full_path, tibco_project_root)
                if artifact_data:
                    for dep in artifact_data.get("dependencies", []):
                        if dep.endswith(".process"):
                            all_called_processes.add(dep)
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