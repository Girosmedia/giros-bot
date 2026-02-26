"""
Tavily Search Tool — Búsqueda web para el Scout_Agent.

Genera contexto de mercado fresco (tendencias, noticias, datos chilenos)
en base a la categoría del artículo del día.

Diseño: fallback graceful — si Tavily falla por cualquier motivo
(API key ausente, red, rate limit), retorna string vacío sin romper el pipeline.
"""

import logging

logger = logging.getLogger(__name__)

# Queries por categoría: buscan contexto chileno relevante y tendencias actuales
CATEGORY_QUERIES: dict[str, list[str]] = {
    "Diseño Web": [
        "velocidad web móvil Chile 2025 2026 Pymes rendimiento",
        "tendencias diseño web experiencia usuario Chile pequeñas empresas",
    ],
    "E-commerce": [
        "e-commerce Chile 2025 2026 facturación electrónica SII Pymes",
        "tiendas online Chile crecimiento ventas digitales tendencias",
    ],
    "SEO Local": [
        "SEO local Chile 2025 2026 Google Maps negocios búsquedas locales",
        "posicionamiento web local Santiago comunas pequeñas empresas Chile",
    ],
    "Marketing Digital": [
        "marketing digital Chile 2025 2026 redes sociales Pymes estrategia",
        "publicidad digital pequeñas empresas Chile tendencias Instagram Facebook",
    ],
    "Presencia Digital": [
        "presencia digital Pymes Chile 2025 2026 sitio web visibilidad online",
        "digitalización pequeñas empresas Chile barreras soluciones",
    ],
    "Casos de Éxito": [
        "transformación digital Pymes Chile casos éxito resultados 2025 2026",
        "empresas chilenas crecimiento digital ejemplos agencia web",
    ],
}

FALLBACK_QUERIES = [
    "marketing digital Chile Pymes 2026 tendencias",
    "digitalización negocios Chile pequeñas empresas",
]


async def search_market_context(target_category: str, api_key: str) -> str:
    """
    Realiza 2 búsquedas Tavily para la categoría dada.
    Retorna un string con los snippets concatenados.
    Si falla, retorna "" para que el Scout use el fallback LLM.
    """
    if not api_key:
        logger.warning("Tavily: TAVILY_API_KEY no configurada. Usando fallback LLM.")
        return ""

    try:
        from tavily import AsyncTavilyClient  # import lazy para no romper si no está instalado

        client = AsyncTavilyClient(api_key=api_key)
        queries = CATEGORY_QUERIES.get(target_category, FALLBACK_QUERIES)

        results_text: list[str] = []
        for query in queries:
            try:
                response = await client.search(
                    query=query,
                    search_depth="basic",
                    max_results=3,
                    include_answer=True,
                )
                # Incluir el answer resumido si existe
                if response.get("answer"):
                    results_text.append(f"Resumen: {response['answer']}")
                # Incluir snippets de resultados
                for result in response.get("results", []):
                    content = result.get("content", "").strip()
                    if content:
                        results_text.append(f"- {content[:300]}")
            except Exception as e:
                logger.warning("Tavily: query '%s' falló — %s", query, e)
                continue

        if not results_text:
            return ""

        combined = "\n".join(results_text)
        logger.info(
            "Tavily: %d snippets obtenidos para categoría '%s' (%d chars)",
            len(results_text), target_category, len(combined),
        )
        return combined

    except ImportError:
        logger.warning("Tavily: librería no encontrada. Usando fallback LLM.")
        return ""
    except Exception as e:
        logger.warning("Tavily: error inesperado — %s. Usando fallback LLM.", e)
        return ""
