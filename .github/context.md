# 🏗️ ESPECIFICACIÓN TÉCNICA: GIROS-AUTOBOT V1.0 (MASTER)
> **Proyecto:** Sistema de Generación de Contenido Automatizado (Blog & RRSS Omnicanal)
> **Entidad:** Giros Media SpA (Chile)
> **Stack:** Python 3.12+, FastAPI, LangGraph v1, gemini, GitHub API.


---

## 1. VISIÓN GENERAL
Construir un backend autónomo basado en **LangGraph** que actúe como una "Agencia de Marketing Digital" virtual. El sistema debe:
1.  **Elegir un tema** basado en una estrategia de calendario (Consejo vs. Venta).
2.  **Investigar** contexto chileno (SII, Mercado, Noticias) y cruzarlo con nuestra base de conocimiento (`.md` files).
3.  **Redactar** artículos en formato `.mdx` compatibles estrictamente con el frontend Next.js actual.
4.  **Generar** assets visuales (Prompts para DALL-E/Stability).
5.  **Adaptar** el mensaje para LinkedIn, Instagram y Facebook (Omnicanalidad).
6.  **Desplegar** vía Pull Request a GitHub (Web) y Webhook a Redes Sociales.

---

## 2. ARQUITECTURA DEL FLUJO (LANGGRAPH)

El grafo utiliza un **Router Condicional** para determinar la intención del día y un ciclo de validación.

### 🧩 Nodos del Grafo
1.  **`Scheduler_Node`:** Determina la fecha actual y aplica las reglas de negocio (ver sección 3).
2.  **`Scout_Agent` (RAG):** Busca información relevante en los documentos de contexto (`CEREBRO_GIROS_MEDIA.md`, `CEREBRO_TENDO_SAAS.md`) y simula búsqueda de datos externos.
3.  **`Strategist_Agent` (Router):** Decide el enfoque, el tono y la categoría del blog.
4.  **`Writer_Agent`:** Genera el cuerpo del artículo en Markdown (MDX) y el Frontmatter YAML.
5.  **`Social_Agent`:** Toma el artículo base y genera 3 versiones del copy (LinkedIn, IG, FB).
6.  **`Visual_Agent`:** Genera el prompt para la imagen destacada y el `alt text`.
7.  **`Validator_Agent`:** Revisa que el MDX cumpla con los esquemas (Typescript interfaces). Si falla, devuelve al Writer.
8.  **`Publisher_Agent`:**
    * Ejecuta commit a GitHub (`/content/blog`).
    * Dispara Webhook con el payload social.

---

## 3. LÓGICA DE NEGOCIO (EL "ROUTER")

El sistema debe balancear entre **Autoridad (Consejos)** y **Conversión (Ventas)**.

### Regla de Distribución Semanal
* **Lunes / Miércoles / Viernes:** Rama **CONSEJO** (Aportar valor, Educación, Soft Sell al final).
* **Martes / Jueves:** Rama **VENTA** (Hard Sell, Oferta directa de Packs o Tendo).

### Mapeo de Categorías (Internal Logic -> Frontend Types)
Es **CRÍTICO** respetar los tipos de TypeScript del frontend.

| Intención del Bot (Backend) | Tópico Interno | **BlogCategory (Frontend TS)** | Producto Asociado |
| :--- | :--- | :--- | :--- |
| **Consejo** | Finanzas / Gestión / Tendo / SII | `E-commerce` | SaaS Tendo (Plan Total) |
| **Consejo** | Tecnología / Velocidad / Next.js | `Diseño Web` | Pack Presencia Digital |
| **Consejo** | Branding / Imprenta / Físico | `Marketing Digital` | Pack Identidad & Impresión |
| **Consejo** | SEO Local / Google Maps / Barrio | `SEO Local` | Pack Presencia Digital |
| **Venta** | Casos de éxito / Testimonios | `Casos de Éxito` | Cualquiera |
| **Venta** | Oferta Directa / CyberDay / Promos | `Presencia Digital` | Combos (Hybrid) |

---

## 4. MODELOS DE DATOS (SCHEMAS)

### A. Backend State (Pydantic)
Este es el estado que viaja a través de los nodos de LangGraph.

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional

class ContentType(str, Enum):
    CONSEJO = "Consejo"
    VENTA = "Venta"

# Debe coincidir EXACTAMENTE con types.ts
class FrontendCategory(str, Enum):
    PRESENCIA = 'Presencia Digital'
    ECOMMERCE = 'E-commerce'
    SEO_LOCAL = 'SEO Local'
    MARKETING = 'Marketing Digital'
    DISENO_WEB = 'Diseño Web'
    CASOS_EXITO = 'Casos de Éxito'

class SocialAssets(BaseModel):
    linkedin_copy: str
    instagram_copy: str
    facebook_copy: str
    short_url: str # Placeholder para link

class AgentState(BaseModel):
    # Contexto Inicial
    target_date: str
    content_type: ContentType
    
    # Investigación
    market_context: str
    internal_knowledge: str
    
    # Generación Web
    title: str
    slug: str
    frontend_category: FrontendCategory
    tags: List[str]
    description: str
    mdx_content_body: str
    
    # Generación Social (Nuevo)
    social_assets: SocialAssets
    
    # Visual
    image_prompt: str
    image_alt: str
    image_url_generated: str
    
    # Control
    quality_score: int
    retry_count: int
```

### B. Frontend Interface (Reference)
El output final (`.mdx`) debe cumplir estrictamente con esta interfaz:

```typescript
export type BlogCategory =
  | 'Presencia Digital'
  | 'E-commerce'
  | 'SEO Local'
  | 'Marketing Digital'
  | 'Diseño Web'
  | 'Casos de Éxito';

export interface PostFrontmatter {
  title: string;
  description: string;
  date: string; // YYYY-MM-DD
  category: BlogCategory;
  tags: string[];
  image?: string;
  imageAlt?: string;
  author: string; // Default: "Equipo Giros Media"
  authorRole?: string;
}
```

---

## 5. PROMPTS & INSTRUCCIONES DE AGENTES

### A. Identidad General (System Prompt)
> "Eres el Director de Estrategia de Giros Media SpA en Chile. Tu tono es pragmático, directo, afilado y experto ('Chileno de negocios'). No usas relleno, ni emojis excesivos (salvo en Instagram), ni palabras de moda vacías. Entiendes que el cliente Pyme valora el tiempo y el dinero. Tu objetivo es posicionar a la agencia como una autoridad técnica y comercial."

### B. Instrucciones para `Writer_Agent` (Web)
1.  **Estructura MDX:** Frontmatter YAML válido + Contenido Markdown.
2.  **Formato:** H2 (`##`), H3 (`###`), Negritas (`**`).
3.  **Cierre:** Si es Consejo, usa un Soft Sell. Si es Venta, usa un Hard Sell.
4.  **Localización:** Menciona siempre el contexto chileno (Pesos, UF, Comunas, SII).

### C. Instrucciones para `Social_Agent` (Omnicanal)
Debe generar 3 versiones distintas del mismo contenido:

1.  **LinkedIn:** Tono profesional, liderazgo de pensamiento. Sin emojis de "cohete". Estructura: Gancho -> Reflexión -> Pregunta abierta.
2.  **Instagram:** Tono visual y cercano. Uso de emojis permitido. Incluir 5 hashtags locales (ej: #PymesChile #Conchali #Emprendedores). Llamado a la acción: "Link en bio".
3.  **Facebook:** Tono comunitario/vecinal. Enfocado en el beneficio directo ("Vende más", "Ordena tu caja"). Llamado a la acción: Link directo al post.

---

## 6. REQUERIMIENTOS DE IMPLEMENTACIÓN

1.  **RAG System:**
    * Vector Store (ChromaDB/FAISS) cargado con `00_CEREBRO_GIROS_MEDIA.md` y `00_CEREBRO_TENDO_SAAS.md`.
    * Strict Retrieval: El bot no puede inventar precios. Debe citar los del documento. Aunque no es critico que se cargue desde una vector store, podemos simplemente pasar el .md en el contexto al LLM.
2.  **GitHub Integration (Web):**
    * Librería: `PyGithub`.
    * Ruta: `/content/blog/{YYYY-MM}-{slug}.mdx`.
3.  **Social Distribution (Webhook):**
    * En lugar de integrar APIs de Meta directamente, enviar un JSON a un Webhook (Desarrollo propio o usr alternativas gratis)
    * Payload: `{ "social_assets": {...}, "image_url": "...", "post_url": "..." }`.
4.  **Generación de Imágenes:**
    * NANO BANANA.
    * Prompt Style: "Minimalist, corporate Memphis style, isometric 3D, tech colors (blue/purple), professional".

## 7. CRITERIOS DE ACEPTACIÓN
* El sistema genera un archivo `.mdx` que compila en Next.js sin errores de tipo.
* Se genera un JSON con los copies para 3 redes sociales diferenciadas.
* El contenido de "Venta" menciona los precios correctos (Web $290k, Tendo $20k).
* El contenido de "Consejo" aporta valor real antes de vender.