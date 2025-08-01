# src/llm_client.py

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# FIX: La variable CONFIG_PATH se define aquí y se usará en la función de abajo
CONFIG_PATH = os.path.join("config", "llm_config.json")


def initialize_llm():
    """Carga la API key y configura la librería de Gemini."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[FATAL] La variable de entorno GEMINI_API_KEY no está configurada.")
        print("Por favor, crea un archivo .env con tu clave de API.")
        return False
    try:
        genai.configure(api_key=api_key)
        print("  -> Cliente LLM (Gemini) inicializado correctamente.")
        return True
    except Exception as e:
        print(f"[FATAL] Error al configurar la API de Gemini: {e}")
        return False


def generate_text(prompt: str) -> str:
    """
    Envía un prompt al LLM y devuelve la respuesta en texto.

    Args:
        prompt: El prompt completo a enviar al modelo.

    Returns:
        La respuesta generada por el LLM como una cadena de texto.
    """
    try:
        # FIX: Leer la configuración desde la variable CONFIG_PATH definida a nivel de módulo
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        model = genai.GenerativeModel(config['model_name'])

        generation_config = genai.types.GenerationConfig(
            temperature=config.get('temperature', 0.5)
        )

        response = model.generate_content(prompt, generation_config=generation_config)

        # FIX: Añadir una comprobación para asegurarse de que la respuesta no está vacía
        if response.parts:
            return response.text.strip()
        else:
            # A veces, el modelo puede devolver una respuesta vacía si el contenido se bloquea
            print("    [WARN] La respuesta del LLM estaba vacía. Puede que el contenido haya sido bloqueado.")
            return "Error: La respuesta del modelo estaba vacía."


    except Exception as e:
        print(f"    [ERROR] Falló la llamada a la API de Gemini: {e}")
        return f"Error al generar la documentación: {e}"