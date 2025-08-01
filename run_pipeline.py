# run_pipeline.py (Ubicado en la raíz del proyecto)

# Importa las funciones principales de cada módulo dentro de la carpeta 'src'
from src.step1_discover import run_discovery_phase
from src.step2_preprocess import run_preprocessing_phase
from src.step3_documenter import run_documentation_phase
from src.llm_client import initialize_llm


def main():
    """
    Orquesta la ejecución de todo el pipeline de 3 fases.
    """
    print("===== INICIANDO PIPELINE DE DOCUMENTACIÓN AUTOMÁTICA =====")

    # --- Fase 1: Descubrir artefactos y dependencias ---
    run_discovery_phase()

    # --- Fase 2: Enriquecer los artefactos con su estructura interna ---
    run_preprocessing_phase()

    # --- Fase 3: Generar documentación usando el LLM ---
    # Primero, inicializamos el cliente del LLM
    if initialize_llm():
        # Si la inicialización es exitosa, procedemos a documentar
        run_documentation_phase()
    else:
        print("[ERROR] El pipeline se detuvo porque el cliente LLM no pudo inicializarse.")

    print("\n===== PIPELINE COMPLETADO =====")
    print(f"Revisa la documentación generada en la carpeta: '3_output_documentation'")


if __name__ == "__main__":
    main()