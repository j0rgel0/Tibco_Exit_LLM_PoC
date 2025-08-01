# src/1_discover_and_map.py

import os
import json
import xml.etree.ElementTree as ET
import re

# --- Configuración ---
# Define las rutas relativas al directorio raíz del proyecto 'tibco-reverse-engineer'
SOURCE_ROOT = "1_tibco_project_source"
OUTPUT_DIR = "2_intermediate_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "project_map.json")


# --- Funciones de Ayuda ---

def get_namespaces(xml_file):
    """Extrae los namespaces de un archivo XML para poder usar XPath."""
    namespaces = dict([
        node for _, node in ET.iterparse(xml_file, events=['start-ns'])
    ])
    return namespaces


def get_project_relative_path(full_path, root_dir):
    """Convierte una ruta absoluta a una ruta relativa al directorio del proyecto TIBCO."""
    return os.path.relpath(full_path, root_dir)


# --- Funciones de Parseo de Artefactos ---

def parse_process_file(file_path, root_dir):
    """
    Analiza un archivo .process para extraer sus dependencias clave.
    """
    dependencies = set()
    global_vars_refs = set()

    try:
        namespaces = get_namespaces(file_path)
        # Es crucial registrar los namespaces para que findall funcione
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)

        tree = ET.parse(file_path)
        root = tree.getroot()

        # 1. Encontrar llamadas a otros procesos (Subprocesos)
        # La actividad 'CallProcessActivity' contiene la referencia al subproceso.
        call_process_elements = root.findall(
            './/pd:activity[@type="com.tibco.pe.core.CallProcessActivity"]//pd:processName',
            namespaces
        )
        for element in call_process_elements:
            if element.text:
                # Las rutas en TIBCO usan '/', normalizamos para consistencia
                dep_path = element.text.strip().replace('\\', '/')
                if dep_path.startswith('/'):
                    dep_path = dep_path[1:]
                dependencies.add(dep_path)

        # 2. Encontrar referencias a recursos compartidos (JDBC, JMS, HTTP, etc.)
        # Estos suelen estar en el texto de elementos de configuración.
        # Buscamos cualquier texto que termine en .shared*
        for element in root.iter():
            if element.text and isinstance(element.text, str):
                # Usamos regex para encontrar patrones como /path/to/resource.sharedjdbc
                matches = re.findall(r'(/[\w/.-]+\.shared\w+)', element.text)
                for match in matches:
                    dep_path = match.strip().replace('\\', '/')
                    if dep_path.startswith('/'):
                        dep_path = dep_path[1:]
                    dependencies.add(dep_path)

        # 3. Encontrar referencias a Variables Globales (formato %%VarName%%)
        xml_content = ET.tostring(root, encoding='unicode')
        found_vars = re.findall(r'%%([\w/.-]+)%%', xml_content)
        for var in found_vars:
            # Las variables globales a menudo se agrupan por archivo .substvar
            # Aquí asumimos que el nombre de la variable puede indicar el archivo.
            # Una mejora sería mapear explícitamente los archivos de variables.
            # Por ahora, capturamos el nombre de la variable.
            var_parts = var.split('/')
            if len(var_parts) > 1:
                # Asumimos que la primera parte es el archivo de variables
                global_vars_refs.add(f"{var_parts[0]}.substvar")

    except ET.ParseError as e:
        print(f"  [ERROR] No se pudo parsear el archivo XML: {file_path}. Error: {e}")
        return None
    except Exception as e:
        print(f"  [ERROR] Ocurrió un error inesperado procesando {file_path}. Error: {e}")
        return None

    return {
        "type": "process",
        "dependencies": sorted(list(dependencies)),
        "global_vars_refs": sorted(list(global_vars_refs))
    }


def parse_generic_artifact(file_path):
    """
    Manejador genérico para artefactos que no son procesos (como .shared*, .xsd).
    Por ahora, solo registra su tipo basado en la extensión.
    """
    extension = os.path.splitext(file_path)[1].lower()
    artifact_type_map = {
        ".sharedjdbc": "shared-jdbc",
        ".sharedhttp": "shared-http",
        ".sharedjms": "shared-jms",
        ".xsd": "schema-xsd",
        ".wsdl": "service-wsdl",
        ".substvar": "global-variables"
    }
    return {
        "type": artifact_type_map.get(extension, "unknown"),
        "dependencies": [],
        "global_vars_refs": []
    }


# --- Función Principal ---

def main():
    """
    Orquesta todo el proceso de descubrimiento y mapeo.
    """
    print("--- Iniciando Fase 1: Descubrimiento y Mapeo del Proyecto TIBCO ---")

    if not os.path.isdir(SOURCE_ROOT):
        print(f"[ERROR] El directorio fuente '{SOURCE_ROOT}' no existe.")
        print("Por favor, crea la carpeta y coloca tu proyecto TIBCO dentro.")
        return

    project_map = {"artifacts": {}}
    all_called_processes = set()

    # Asumimos que hay un único proyecto dentro de SOURCE_ROOT
    project_dirs = [d for d in os.listdir(SOURCE_ROOT) if os.path.isdir(os.path.join(SOURCE_ROOT, d))]
    if not project_dirs:
        print(f"[ERROR] No se encontró ninguna carpeta de proyecto dentro de '{SOURCE_ROOT}'.")
        return

    # Usamos la primera carpeta encontrada como la raíz del proyecto TIBCO
    tibco_project_root = os.path.join(SOURCE_ROOT, project_dirs[0])
    print(f"Analizando proyecto en: '{tibco_project_root}'")

    for dirpath, _, filenames in os.walk(tibco_project_root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            relative_path = get_project_relative_path(full_path, tibco_project_root).replace('\\', '/')

            print(f"Procesando: {relative_path}")

            artifact_data = None
            if filename.endswith(".process"):
                artifact_data = parse_process_file(full_path, tibco_project_root)
                if artifact_data:
                    # Agregamos los procesos llamados a un set global para encontrar los entry points
                    for dep in artifact_data.get("dependencies", []):
                        if dep.endswith(".process"):
                            all_called_processes.add(dep)
            else:
                # Para cualquier otro archivo, usamos el manejador genérico
                artifact_data = parse_generic_artifact(full_path)

            if artifact_data:
                project_map["artifacts"][relative_path] = artifact_data

    # Identificar los puntos de entrada (procesos que no son llamados por otros)
    all_processes = {
        path for path, data in project_map["artifacts"].items()
        if data.get("type") == "process"
    }
    entry_points = sorted(list(all_processes - all_called_processes))
    project_map["entry_points"] = entry_points

    print(f"\nAnálisis completado. Se encontraron {len(project_map['artifacts'])} artefactos.")
    print(f"Se identificaron {len(entry_points)} puntos de entrada.")

    # Guardar el mapa del proyecto en un archivo JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(project_map, f, indent=4, ensure_ascii=False)

    print(f"\n--- Fase 1 Completada. Mapa del proyecto guardado en: '{OUTPUT_FILE}' ---")


if __name__ == "__main__":
    main()