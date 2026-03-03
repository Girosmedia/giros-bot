"""
Tavily Search Tool — Herramienta de investigación dinámica para agentes de IA.
Permite que el LLM realice búsquedas web precisas para obtener datos y tendencias.
"""

import logging
from typing import Optional
from langchain_core.tools import tool
from giros_bot.config import settings

logger = logging.getLogger(__name__)

@tool
async def search_web(query: str, search_depth: str = "basic", max_results: int = 5) -> str:
    """
    Realiza una búsqueda en internet para obtener información actualizada, tendencias o datos.
    Úsala cuando necesites investigar un tema, validar un dato o buscar inspiración para Pymes en Chile.
    """
    api_key = settings.tavily_api_key
    if not api_key:
        logger.warning("Tavily: API_KEY no configurada.")
        return "Error: No hay API Key para realizar la búsqueda."

    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=api_key)
        
        logger.info("Ejecutando búsqueda Tavily: '%s'", query)
        
        response = await client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=True,
        )
        
        results_text = []
        if response.get("answer"):
            results_text.append(f"Resumen de la búsqueda: {response['answer']}\n")
            
        for result in response.get("results", []):
            title = result.get("title", "Sin título")
            content = result.get("content", "Sin contenido")
            url = result.get("url", "#")
            results_text.append(f"### {title}\n{content}\nFuente: {url}\n")
            
        if not results_text:
            return "No se encontraron resultados relevantes para esta búsqueda."
            
        return "\n".join(results_text)

    except Exception as e:
        logger.error("Error en búsqueda Tavily: %s", e)
        return f"Error al realizar la búsqueda: {str(e)}"
