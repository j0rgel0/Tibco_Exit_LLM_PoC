# src/step1_discover.py (Versión 6 - Exhaustiva)

import os, json, re

SOURCE_ROOT = "1_tibco_project_source"
OUTPUT_DIR = "2_intermediate_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "project_map.json")


def get_project_relative_path(full_path, root_dir):
    return os.path.relpath(full_path, root_dir).replace('\\', '/')


def parse_process_file(file_path):
    dependencies = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            xml_content = f.read()

        repo_paths = re.findall(r'>/([\w/.-]+)</', xml_content)
        for path in repo_paths:
            dependencies.add(os.path.basename(path))

        global_vars = re.findall(r'%%([\w/.-]+)%%', xml_content)
        for var in global_vars:
            dependencies.add(os.path.basename(var.split('/')[0]) + ".substvar")

    except Exception as e:
        print(f"  [ERROR] Ocurrió un error procesando {file_path}. Error: {e}")
        return None
    return {"dependencies": sorted(list(dependencies))}


def parse_generic_artifact(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension in {".folder", ".dat", ".repository"}: return None
    artifact_type_map = {
        ".process": "process", ".sharedhttp": "shared-http",
        ".sharedparse": "shared-parse", ".xsd": "schema-xsd",
        ".aeschema": "schema-ae", ".substvar": "global-variables"
    }
    return {"type": artifact_type_map.get(extension, "unknown")}


def run_discovery_phase():
    print("--- Iniciando Fase 1 (v6 - Exhaustiva): Descubrimiento y Mapeo ---")
    if not os.path.isdir(SOURCE_ROOT):
        print(f"[ERROR] Directorio fuente '{SOURCE_ROOT}' no encontrado.");
        return

    project_map = {"artifacts": {}, "search_index": {}}
    all_called_processes = set()

    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs:
        print(f"[ERROR] No se encontró ninguna carpeta de proyecto TIBCO en '{SOURCE_ROOT}'.");
        return
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])
    print(f"Analizando proyecto en: '{tibco_project_root}'")

    for dirpath, _, filenames in os.walk(tibco_project_root):
        for filename in filenames:
            relative_path = get_project_relative_path(os.path.join(dirpath, filename), tibco_project_root)
            project_map["search_index"][filename] = relative_path

    for filename, relative_path in list(project_map["search_index"].items()):
        full_path = os.path.join(tibco_project_root, relative_path)
        artifact_data = parse_generic_artifact(full_path)
        if artifact_data:
            if artifact_data["type"] == "process":
                process_details = parse_process_file(full_path)
                if process_details:
                    resolved_deps = set()
                    for dep_name in process_details.get("dependencies", []):
                        if dep_name in project_map["search_index"]:
                            resolved_path = project_map["search_index"][dep_name]
                            resolved_deps.add(resolved_path)
                            if resolved_path.endswith(".process"):
                                all_called_processes.add(resolved_path)
                    artifact_data["dependencies"] = sorted(list(resolved_deps))
            project_map["artifacts"][relative_path] = artifact_data

    all_processes = {path for path, data in project_map["artifacts"].items() if data.get("type") == "process"}
    entry_points = sorted(list(all_processes - all_called_processes))
    project_map["entry_points"] = entry_points
    del project_map["search_index"]

    print(f"\nAnálisis completado. Se encontraron {len(project_map['artifacts'])} artefactos relevantes.")
    print(f"Se identificaron {len(entry_points)} puntos de entrada.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(project_map, f, indent=2)
    print(f"\n--- Fase 1 Completada. Mapa del proyecto guardado en: '{OUTPUT_FILE}' ---")