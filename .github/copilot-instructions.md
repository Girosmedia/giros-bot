# Role: Senior AI Backend Engineer — Giros Autobot V1.0
You are building **giros-bot**, el sistema de generación de contenido automatizado (Blog & RRSS Omnicanal) para **Giros Media SpA** (Santiago, Chile).

---

## 1. STACK TECNOLÓGICO

| Capa | Tecnología | Versión |
|---|---|---|
| **Runtime** | Python | 3.12+ |
| **Gestor de entorno** | uv | latest |
| **Framework API** | FastAPI | 0.115+ |
| **Servidor ASGI** | Uvicorn | 0.32+ |
| **Orquestación IA** | LangGraph | 0.3+ |
| **Abstracciones LLM** | LangChain Core | 1.x |
| **LLM Principal** | Google Gemini Flash Lite (latest) | `langchain-google-genai` |
| **Validación** | Pydantic | v2 (obligatorio) |
| **Vector Store** | ChromaDB | latest |
| **GitHub Integration** | PyGithub | latest |
| **HTTP Client** | httpx | latest |
| **Testing** | pytest + pytest-asyncio | latest |
| **Linting/Format** | ruff | latest |

---

## 2. ARQUITECTURA DEL PROYECTO

```
giros-bot/
├── .github/
│   ├── copilot-instructions.md  # Este archivo
│   └── context.md               # Especificación técnica master
├── content_example/             # Ejemplos MDX de referencia
├── knowledge_base/              # Documentos RAG (.md)
│   ├── 00_CEREBRO_GIROS_MEDIA.md
│   └── 00_CEREBRO_TENDO_SAAS.md
├── src/
│   └── giros_bot/
│       ├── __init__.py
│       ├── main.py              # FastAPI entrypoint
│       ├── config.py            # Settings (pydantic-settings)
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── state.py         # AgentState (Pydantic v2)
│       │   ├── graph.py         # Compilación del StateGraph
│       │   └── nodes/
│       │       ├── __init__.py
│       │       ├── scheduler.py     # Scheduler_Node
│       │       ├── scout.py         # Scout_Agent (RAG)
│       │       ├── strategist.py    # Strategist_Agent (Router)
│       │       ├── writer.py        # Writer_Agent (MDX)
│       │       ├── social.py        # Social_Agent (Omnicanal)
│       │       ├── visual.py        # Visual_Agent (prompt imagen)
│       │       ├── validator.py     # Validator_Agent
│       │       └── publisher.py     # Publisher_Agent (GitHub + Webhook)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── github_tool.py   # PyGithub wrapper
│       │   ├── webhook_tool.py  # Dispatcher RRSS
│       │   └── rag_tool.py      # ChromaDB retriever
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── state.py         # AgentState completo
│       │   └── frontend.py      # Mirror de types.ts del frontend
│       └── prompts/
│           ├── __init__.py
│           ├── system.py        # Identity / System prompt global
│           ├── writer.py        # Prompts del Writer_Agent
│           └── social.py        # Prompts del Social_Agent
├── tests/
│   ├── __init__.py
│   ├── test_graph.py
│   ├── test_nodes.py
│   └── test_schemas.py
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 3. MODELOS DE DATOS CANÓNICOS

### AgentState (viaja por todos los nodos de LangGraph)

```python
# src/giros_bot/schemas/state.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class ContentType(str, Enum):
    CONSEJO = "Consejo"
    VENTA = "Venta"

class FrontendCategory(str, Enum):
    """Debe coincidir EXACTAMENTE con BlogCategory en types.ts del frontend."""
    PRESENCIA    = "Presencia Digital"
    ECOMMERCE    = "E-commerce"
    SEO_LOCAL    = "SEO Local"
    MARKETING    = "Marketing Digital"
    DISENO_WEB   = "Diseño Web"
    CASOS_EXITO  = "Casos de Éxito"

class SocialAssets(BaseModel):
    linkedin_copy:   str
    instagram_copy:  str
    facebook_copy:   str
    short_url:       str  # Placeholder para link post

class AgentState(BaseModel):
    # Contexto inicial
    target_date:        str             = Field(..., description="YYYY-MM-DD")
    content_type:       Optional[ContentType] = None

    # Investigación (Scout)
    market_context:     str = ""
    internal_knowledge: str = ""

    # Generación web (Writer)
    title:              str = ""
    slug:               str = ""
    frontend_category:  Optional[FrontendCategory] = None
    tags:               list[str] = Field(default_factory=list)
    description:        str = ""
    mdx_content_body:   str = ""

    # Generación social (Social_Agent)
    social_assets:      Optional[SocialAssets] = None

    # Visual (Visual_Agent)
    image_prompt:           str = ""
    image_alt:              str = ""
    image_url_generated:    str = ""

    # Control de calidad
    quality_score:  int = 0
    retry_count:    int = 0
    error_message:  str = ""
```

### Frontmatter MDX (output final)

```python
# src/giros_bot/schemas/frontend.py
from pydantic import BaseModel, Field
from typing import Optional
from .state import FrontendCategory

class PostFrontmatter(BaseModel):
    """Mirror de PostFrontmatter interface en el frontend Next.js."""
    title:       str
    description: str
    date:        str              = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    category:    FrontendCategory
    tags:        list[str]
    image:       Optional[str] = None
    imageAlt:    Optional[str] = None
    author:      str          = "Equipo Giros Media"
    authorRole:  Optional[str] = "Especialistas en Presencia Digital"
```

---

## 4. LÓGICA DE NEGOCIO (ROUTER)

### Distribución semanal
| Día | Rama | Tipo de venta |
|---|---|---|
| Lunes / Miércoles / Viernes | `CONSEJO` | Soft Sell al cierre |
| Martes / Jueves | `VENTA` | Hard Sell, oferta directa |

### Mapeo Tópico → Categoría Frontend
| Tópico Interno | `FrontendCategory` | Producto |
|---|---|---|
| Finanzas / Gestión / SII | `E-commerce` | Tendo SaaS |
| Tecnología / Velocidad / Web | `Diseño Web` | Pack Presencia Digital |
| Branding / Imprenta / Físico | `Marketing Digital` | Pack Identidad & Impresión |
| SEO Local / Google Maps | `SEO Local` | Pack Presencia Digital |
| Casos de éxito / Testimonios | `Casos de Éxito` | Cualquiera |
| Oferta Directa / Promos | `Presencia Digital` | Combos Hybrid |

### Precios canónicos (NO inventar)
| Producto | Precio |
|---|---|
| Sitio Web estándar | $290.000 CLP |
| Tendo SaaS / mes | $20.000 CLP |

---

## 5. NODOS DEL GRAFO (RESPONSABILIDADES)

| Nodo | Responsabilidad |
|---|---|
| `Scheduler_Node` | Fecha actual → `ContentType` (CONSEJO/VENTA) según día de la semana |
| `Scout_Agent` | RAG sobre knowledge_base/ + contexto chileno simulado → `market_context`, `internal_knowledge` |
| `Strategist_Agent` | Selecciona tópico, categoría, slug y tags → enruta al Writer |
| `Writer_Agent` | Genera frontmatter YAML + cuerpo MDX completo |
| `Social_Agent` | Del artículo base, genera LinkedIn + Instagram + Facebook copy |
| `Visual_Agent` | Genera prompt DALL-E/Stability + `imageAlt` |
| `Validator_Agent` | Valida MDX contra `PostFrontmatter`. Si `quality_score < 7` → retry al Writer (max 2 veces) |
| `Publisher_Agent` | Commit a GitHub (`/content/blog/`) + POST webhook RRSS |

---

## 6. CONVENCIONES DE CÓDIGO

1. **Pydantic v2 siempre.** Usar `model_validator`, `field_validator`, `model_dump()` (no `.dict()`).
2. **LangGraph StateGraph** con `TypedDict` o `BaseModel` como estado. Nodos son funciones `async def node(state: AgentState) -> dict`.
3. **LLM:** `ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.7)` de `langchain-google-genai`.
4. **Prompts:** ChatPromptTemplate con `SystemMessage` + `HumanMessage`. Prompt de identidad siempre como system.
5. **RAG simplificado:** Pasar el `.md` completo en contexto al LLM (no vector store en MVP). ChromaDB para V2.
6. **GitHub:** Usar `PyGithub`. Ruta de commit: `content/blog/{YYYY-MM}-{slug}.mdx`.
7. **Webhook RRSS:** POST a URL configurada con payload `{ social_assets, image_url, post_url }`.
8. **Variables de entorno:** Todas gestionadas con `pydantic-settings` desde `.env`. Nunca hardcodear keys.
9. **Async everywhere:** FastAPI + LangGraph son async. Preferir `async def` en todos los nodos.
10. **Ruff** para linting y formato. Sin Black ni Flake8.

---

## 7. SYSTEM PROMPT (IDENTIDAD DEL BOT)

```
Eres el Director de Estrategia de Giros Media SpA en Chile.
Tu tono es pragmático, directo, afilado y experto ("Chileno de negocios").
No usas relleno, ni emojis excesivos (salvo en Instagram), ni palabras de moda vacías.
Entiendes que el cliente Pyme chileno valora el tiempo y el dinero.
Tu objetivo es posicionar a la agencia como una autoridad técnica y comercial.
Siempre menciona el contexto chileno: Pesos CLP, UF, comunas, SII.
```

---

## 8. FORMATO MDX DE REFERENCIA

El output del Writer_Agent debe seguir exactamente este patrón (ver `/content_example/`):

```mdx
---
title: "Título del artículo"
description: "Descripción SEO de 150-160 caracteres"
date: "YYYY-MM-DD"
category: "Diseño Web"  # Uno de FrontendCategory
tags: ["tag1", "tag2", "tag3", "tag4", "tag5"]
image: "/blog/{slug}.jpg"
imageAlt: "Descripción accesible de la imagen"
author: "Equipo Giros Media"
authorRole: "Especialistas en Presencia Digital"
---

Párrafo introductorio que engancha al lector con una pregunta o dato impactante.

## H2 Principal

Contenido con **negritas** para énfasis. Listas con `-`.

### H3 Subsección

Desarrollo...

## Cierre (Soft o Hard Sell según ContentType)

[CTA apropiado]
```

---

## 9. VARIABLES DE ENTORNO REQUERIDAS

```env
# LLM
GOOGLE_API_KEY=

# GitHub
GITHUB_TOKEN=
GITHUB_REPO_OWNER=girosmedia
GITHUB_REPO_NAME=girosmedia-web-new

# Webhooks RRSS
SOCIAL_WEBHOOK_URL=

# App
APP_ENV=development  # development | production
LOG_LEVEL=INFO
```
