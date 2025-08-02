# src/step5_build_html.py (Versión 4.1 - Corrección de Codec)

import os, json, markdown2, re
from datetime import datetime

OUTPUT_DOCS_DIR = "3_output_documentation"
TEMPLATE_PATH = "template.html"
FINAL_HTML_PATH = os.path.join(OUTPUT_DOCS_DIR, "TIBCO_Migration_Specification.html")
PROJECT_TITLE = "Especificación de Migración de TIBCO"
PREPROCESSED_DIR = os.path.join("2_intermediate_data", "preprocessed")
MAP_FILE = os.path.join("2_intermediate_data", "project_map.json")


def create_anchor_id(filepath):
    return os.path.splitext(filepath)[0].replace('/', '_').replace('\\', '_').replace('.', '_')


def generate_mermaid_for_process(process_data):
    # ... (Esta función no necesita cambios) ...
    if not process_data or process_data.get("type") != "process": return ""
    print(f"    -> Generando diagrama para: {process_data.get('name')}")

    def clean_id(name):
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)

    mermaid_code = ["graph TD"]
    nodes = {}
    starter_name = process_data.get("starter", {}).get("name", "Start")
    nodes[starter_name] = f'{clean_id(starter_name)}["🏁 {starter_name}"]'
    for act in process_data.get("activities", []):
        nodes[act.get("name")] = f'{clean_id(act.get("name"))}["📄 {act.get("name")}"]'
    for t in process_data.get("transitions", []):
        if t.get("to") == "End":
            nodes["End"] = f'{clean_id("End")}("🏁 End")';
            break
    for node_def in nodes.values(): mermaid_code.append(f"    {node_def}")
    for t in process_data.get("transitions", []):
        from_node, to_node = t.get("from"), t.get("to")
        if from_node in nodes and to_node in nodes:
            link_style = "-- Error -->" if t.get("condition") == "error" else "-->"
            mermaid_code.append(f"    {clean_id(from_node)} {link_style} {clean_id(to_node)}")
    return f'<h3>Diagrama de Flujo de Actividades</h3>\n<div class="mermaid">\n{"\n".join(mermaid_code)}\n</div>'


def get_ordered_markdown_files(project_map):
    # ... (Esta función no necesita cambios) ...
    print("  -> Ordenando documentos según el flujo de ejecución...")
    all_md_paths = {os.path.join(root, file) for root, _, files in os.walk(OUTPUT_DOCS_DIR) for file in files if
                    file.endswith(".md")}
    ordered_files, processed_paths = [], set()
    readme_path = os.path.join(OUTPUT_DOCS_DIR, "README.md")
    if readme_path in all_md_paths:
        ordered_files.append(readme_path);
        processed_paths.add(readme_path)
    queue = list(project_map.get("entry_points", []))
    bfs_processed = set()
    while queue:
        process_path = queue.pop(0)
        if process_path in bfs_processed: continue
        bfs_processed.add(process_path)
        md_path = os.path.join(OUTPUT_DOCS_DIR, process_path.replace('.process', '.md'))
        if md_path in all_md_paths and md_path not in processed_paths:
            ordered_files.append(md_path);
            processed_paths.add(md_path)
        for dep_path in project_map.get("artifacts", {}).get(process_path, {}).get("dependencies", []):
            if dep_path.endswith(".process"): queue.append(dep_path)
    ordered_files.extend(sorted(list(all_md_paths - processed_paths)))
    return ordered_files


def run_html_build_phase():
    print("\n--- Iniciando Fase 5 (Build HTML Ordenado): Creando Documento Final ---")
    if not os.path.isdir(OUTPUT_DOCS_DIR): print(f"[ERROR] Directorio de documentación no encontrado."); return
    try:
        # FIX: Añadir encoding='utf-8'
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            project_map = json.load(f)
    except FileNotFoundError:
        print(f"[FATAL] Mapa del proyecto no encontrado."); return

    ordered_md_files = get_ordered_markdown_files(project_map)
    if not ordered_md_files: print("[WARN] No se encontraron archivos .md para construir."); return

    toc_html_parts, content_html_parts = [], []
    print("  -> Procesando archivos y generando diagramas en orden de flujo...")
    for md_path in ordered_md_files:
        relative_path = os.path.relpath(md_path, OUTPUT_DOCS_DIR).replace('\\', '/')
        anchor_id = create_anchor_id(relative_path)
        title = "Visión General del Proyecto" if relative_path == "README.md" else relative_path
        toc_html_parts.append(f'<li><a href="#{anchor_id}">{title}</a></li>')

        # FIX: Añadir encoding='utf-8'
        with open(md_path, 'r', encoding='utf-8') as f:
            html_content = markdown2.markdown(f.read(), extras=["tables", "fenced-code-blocks", "header-ids"])

        diagram_html = ""
        if relative_path.endswith(".process.md"):
            json_path = os.path.join(PREPROCESSED_DIR, relative_path.replace('.md', '.json'))
            if os.path.exists(json_path):
                try:
                    # FIX: Añadir encoding='utf-8'
                    with open(json_path, 'r', encoding='utf-8') as f:
                        process_data = json.load(f)
                    diagram_html = generate_mermaid_for_process(process_data)
                except (json.JSONDecodeError, FileNotFoundError):
                    print(f"    [WARN] No se pudo leer JSON para diagrama de: {relative_path}")

        content_html_parts.append(
            f'<section id="{anchor_id}" class="document-part">\n{diagram_html}\n{html_content}\n</section>')

    print("  -> Ensamblando el archivo HTML final...")
    try:
        # FIX: Añadir encoding='utf-8'
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = f.read()
        final_html = template.replace("{{TITLE}}", PROJECT_TITLE)
        final_html = final_html.replace("{{TOC}}", "\n".join(toc_html_parts))
        final_html = final_html.replace("{{CONTENT}}", "\n".join(content_html_parts))
        final_html = final_html.replace("{{GENERATION_DATE}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(FINAL_HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"    -> Documento HTML final guardado en: {FINAL_HTML_PATH}")
    except Exception as e:
        print(f"    [ERROR] Falló la construcción del HTML: {e}")