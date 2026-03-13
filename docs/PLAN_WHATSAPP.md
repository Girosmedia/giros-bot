# Plan: WhatsApp Business Webhook + Triage Agent LangGraph

> **Estado de implementación** — Última actualización: 2026-03-12
>
> | Fase | Estado | Archivos |
> |---|---|---|
> | Fase 0: Estructura carpetas | ✅ Completado | — |
> | Fase 1: Protocols + Schemas | ✅ Completado | `services/messaging.py`, `services/scheduling.py`, `services/lead_capture.py`, `schemas/whatsapp.py`, `schemas/whatsapp_state.py` |
> | Fase 2: Integraciones | ✅ Completado | `integrations/whatsapp_api.py`, `integrations/scheduling/`, `integrations/lead/postgres_lead.py` |
> | Fase 3: Tools | ✅ Completado | `tools/scheduling_tool.py`, `tools/lead_tool.py`, `tools/messaging_tool.py` |
> | Fase 4: Prompts | ✅ Completado | `prompts/whatsapp.py` |
> | Fase 5: Graph Nodes | ✅ Completado | `graph/nodes/whatsapp/` (6 nodos) |
> | Fase 6: whatsapp_graph.py | ✅ Completado | `graph/whatsapp_graph.py` |
> | Fase 7: Router + Config + Lifespan | ✅ Completado | `routers/whatsapp.py`, `config.py` MOD, `main.py` MOD, `pyproject.toml` MOD |
> | Fase 8: Tests | ✅ Completado | `tests/test_whatsapp_webhook.py`, `tests/test_whatsapp_graph.py` |
>
> **Pendiente para activar en producción:**
> - Configurar variables de entorno en `.env` (`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_TOKEN`, `WHATSAPP_VERIFY_TOKEN`, `SCHEDULING_URL`)
> - Registrar el webhook en Meta Business Manager apuntando a `GET/POST /v1/webhook/whatsapp`
> - Ejecutar `uv run pytest tests/test_whatsapp_webhook.py tests/test_whatsapp_graph.py -v`

## TL;DR
Webhook FastAPI → BackgroundTask → Grafo LangGraph conversacional → 5 agentes especializados → respuesta WhatsApp. La arquitectura está organizada en capas estrictamente desacopladas: cada capa depende solo de **abstracciones (Protocols)**, nunca de implementaciones concretas. Cambiar de proveedor de agenda, CRM o mensajería = crear una nueva clase que implemente el Protocol, cambiar 1 línea en el lifespan.

---

## Decisiones de Arquitectura (BLOQUEANTES — definen el resto)

### Modelo de Capas

```
┌──────────────────────────────────────────────────────┐
│  Capa 1: API / Webhook (FastAPI Router)              │
│  — Valida payload Meta, responde 200, dispara task   │
├──────────────────────────────────────────────────────┤
│  Capa 2: Graph Nodes / Agents (LangGraph)            │
│  — Lógica conversacional pura. Solo ve Tools y State │
├──────────────────────────────────────────────────────┤
│  Capa 3: Tools (@tool LangChain)                     │
│  — Bridge Agente → Servicio. Thin wrappers.          │
├──────────────────────────────────────────────────────┤
│  Capa 4: Services (Protocols/ABCs)                   │
│  — Contratos abstractos. Definen QUÉ hace cada capa. │
├──────────────────────────────────────────────────────┤
│  Capa 5: Integrations (implementaciones concretas)   │
│  — WhatsApp API, Google Cal, Calendly, DB, SMTP, etc │
└──────────────────────────────────────────────────────┘
```

### Principio de inyección
Los agentes/nodos **no importan ni instancian** ninguna integración concreta. Reciben los servicios vía `RunnableConfig["configurable"]` en el momento de invocación. El lifespan de FastAPI instancia las concretas y las pasa al grafo.

---

## Decisiones de Negocio Confirmadas

- **Cotización Tendo:** Prospects que quieren **ordenar su negocio** (minimarkets, talleres, almacenes, etc.) con un SaaS de gestión. Precios abiertos: $20.000/mes. Cierre autónomo: trial 14 días.

- **Cotización Servicios (SDR):** Todos los servicios a medida de la agencia:
  - Diseño web (Landing, Ecommerce, Corporativa, Web App a medida)
  - Automatizaciones de procesos (Make, n8n, custom)
  - Gestión de RRSS
  - Identidad de marca (logo, papelería, manual de marca)
  - Diseño gráfico general
  - **CERO precios en el bot.** Actúa como SDR: recoge tipo de proyecto → presupuesto → email → pasa a directores.

- **Agenda (VIP):** La integración de agenda es **intercambiable** (Calendly, Google Cal, TidyCal, manual). El agente solo llama al `ISchedulingService` y recibe una URL/instrucción. No conoce el proveedor.

- **Lead Quality:** Calificación conversacional (2-3 preguntas) dentro del `reserva_agent`, no en triage. Evita falsos negativos en el primer mensaje.

- **PostgreSQL:** Checkpointer para historial (AsyncPostgresSaver) + tabla futura de leads.

- **thread_id:** `wa_{phone_number}` — persiste memoria entre sesiones.

---

## Fase 0: Estructura de Carpetas (define las otras fases)

```
src/giros_bot/
├── routers/
│   ├── __init__.py
│   └── whatsapp.py              # FastAPI router (Capa 1)
├── schemas/
│   ├── whatsapp.py              # Pydantic modelos Meta payload
│   └── whatsapp_state.py        # WhatsAppState TypedDict + Enums
├── services/                    # Capa 4: SOLO Protocols/ABCs
│   ├── __init__.py
│   ├── messaging.py             # IMessagingService Protocol
│   ├── scheduling.py            # ISchedulingService Protocol
│   └── lead_capture.py          # ILeadCaptureService Protocol
├── integrations/                # Capa 5: implementaciones concretas
│   ├── __init__.py
│   ├── whatsapp_api.py          # WhatsAppAPIMessaging(IMessagingService)
│   ├── scheduling/
│   │   ├── __init__.py
│   │   ├── base.py              # SchedulingResult dataclass compartido
│   │   ├── calendly.py          # CalendlyScheduler(ISchedulingService)
│   │   └── google_calendar.py   # GoogleCalScheduler(ISchedulingService) [stub]
│   └── lead/
│       ├── __init__.py
│       └── postgres_lead.py     # PostgresLeadCapture(ILeadCaptureService)
├── tools/                       # Capa 3: @tool wrappers
│   ├── __init__.py
│   ├── messaging_tool.py        # send_whatsapp_message
│   ├── scheduling_tool.py       # get_scheduling_link
│   └── lead_tool.py             # capture_lead
├── graph/
│   ├── nodes/
│   │   └── whatsapp/
│   │       ├── triage_node.py
│   │       ├── cotizacion_tendo_agent.py
│   │       ├── cotizacion_servicios_agent.py
│   │       ├── soporte_agent.py
│   │       ├── info_agent.py
│   │       └── reserva_agent.py
│   └── whatsapp_graph.py
└── prompts/
    └── whatsapp.py
```

---

## Fase 1: Abstracciones / Protocols (sin dependencias, paralelo con datos puros)

### 1a. `src/giros_bot/services/messaging.py`
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class IMessagingService(Protocol):
    async def send_text(self, recipient_id: str, text: str) -> bool: ...
    async def mark_as_read(self, message_id: str) -> bool: ...
```

### 1b. `src/giros_bot/services/scheduling.py`
```python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

@dataclass
class SchedulingResult:
    """Resultado genérico — el agente solo ve esto, nunca el proveedor."""
    available: bool
    booking_url: str    # URL directa o instrucción textual
    provider_name: str  # "Calendly" | "Google Calendar" | "Manual"
    instructions: str   # Texto amigable para el usuario final

@runtime_checkable
class ISchedulingService(Protocol):
    async def get_booking_url(self, context: dict) -> SchedulingResult: ...
    # context: {"lead_name", "lead_phone", "project_type"} — opcional, para pre-fill
```

### 1c. `src/giros_bot/services/lead_capture.py`
```python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

@dataclass
class LeadData:
    phone: str
    name: str
    email: str = ""
    project_type: str = ""
    budget_hint: str = ""
    service_type: str = ""  # "servicios" | "tendo" | "agenda"
    lead_quality: str = "unknown"
    notes: str = ""

@runtime_checkable
class ILeadCaptureService(Protocol):
    async def save_lead(self, lead: LeadData) -> bool: ...
```

### 1d. `src/giros_bot/schemas/whatsapp.py` — Pydantic v2 (payload Meta)
- `WhatsAppWebhookPayload`, `WhatsAppEntry`, `WhatsAppChange`, `WhatsAppValue`,
  `WhatsAppMessage`, `WhatsAppContact`, `WhatsAppTextContent`
- `@model_validator` que rechaza si `object != "whatsapp_business_account"`
- Alias con `model_config = ConfigDict(populate_by_name=True)` para `from_` (campo reservado)

### 1e. `src/giros_bot/schemas/whatsapp_state.py`
```python
class TriageIntent(str, Enum):
    COTIZACION_TENDO     = "cotizacion_tendo"
    COTIZACION_SERVICIOS = "cotizacion_servicios"
    SOPORTE              = "soporte_tecnico"
    INFO_GENERAL         = "info_general"
    AGENDAR              = "agendar_llamada"
    OUT_OF_SCOPE         = "out_of_scope"

class LeadQuality(str, Enum):
    UNKNOWN = "unknown"
    HIGH    = "high"   # → da URL de agenda
    LOW     = "low"    # → desvía a web/PDF

class WhatsAppState(TypedDict):
    messages:            Annotated[list, add_messages]
    sender_phone:        str
    sender_name:         str
    intent:              str   # TriageIntent
    lead_quality:        str   # LeadQuality
    lead_email:          str
    lead_project_type:   str   # "web_ecommerce"|"web_landing"|"web_app"|"automatizacion"|"rrss"|"identidad_marca"|"diseno"|"tendo"|""
    lead_budget_hint:    str   # "tiene_budget"|"explorando"|"sin_budget"|""
    lead_service_type:   str   # "servicios"|"tendo"|"agenda"
    response_text:       str
```

### 1f. `pyproject.toml` — Nueva dependencia
`langgraph-checkpoint-postgres>=2.0.0`

---

## Fase 2: Integraciones Concretas (implementan los Protocols)

### 2a. `src/giros_bot/integrations/whatsapp_api.py`
```python
class WhatsAppAPIMessaging:
    """Implementa IMessagingService usando Meta Graph API."""
    # En dev mode (phone_number_id vacío): loguea en lugar de llamar a Meta
    async def send_text(self, recipient_id: str, text: str) -> bool: ...
    async def mark_as_read(self, message_id: str) -> bool: ...
```

### 2b. `src/giros_bot/integrations/scheduling/base.py`
Solo el dataclass `SchedulingResult` reexportado (ya definido en service Protocol).

### 2c. `src/giros_bot/integrations/scheduling/calendly.py`
```python
class CalendlyScheduler:
    """Implementa ISchedulingService via Calendly URL estática (V1 simple)."""
    def __init__(self, calendly_url: str): ...
    async def get_booking_url(self, context: dict) -> SchedulingResult:
        # V1: retorna la URL de Calendly directamente sin prefill
        # V2 futura: API Calendly para crear single-use links con prefill
        return SchedulingResult(
            available=True,
            booking_url=self.calendly_url,
            provider_name="Calendly",
            instructions="Agenda aquí tu reunión →"
        )
```

### 2d. `src/giros_bot/integrations/scheduling/google_calendar.py`
```python
class GoogleCalendarScheduler:
    """STUB — implementar cuando se defina el proveedor."""
    async def get_booking_url(self, context: dict) -> SchedulingResult:
        raise NotImplementedError("GoogleCalendarScheduler no implementado aún")
```

### 2e. `src/giros_bot/integrations/lead/postgres_lead.py`
```python
class PostgresLeadCapture:
    """Guarda leads en tabla whatsapp_leads de PostgreSQL."""
    async def save_lead(self, lead: LeadData) -> bool: ...
```
- Tabla `whatsapp_leads`: id, phone, name, email, project_type, budget_hint, service_type, lead_quality, notes, created_at
- Usa el mismo pool async del proyecto (asyncpg engine existente)

---

## Fase 3: Tools (@tool — bridge Agente → Servicio)

Los tools reciben los servicios desde `RunnableConfig["configurable"]`:

### 3a. `src/giros_bot/tools/scheduling_tool.py`
```python
@tool
async def get_scheduling_link(
    lead_name: str,
    project_type: str,
    config: RunnableConfig,
) -> str:
    """Obtiene el link/instrucción de agenda según el proveedor configurado."""
    scheduling_service: ISchedulingService = config["configurable"]["scheduling_service"]
    result = await scheduling_service.get_booking_url({...})
    return f"{result.instructions} {result.booking_url}"
```

### 3b. `src/giros_bot/tools/lead_tool.py`
```python
@tool
async def capture_lead(
    phone: str, name: str, email: str,
    project_type: str, budget_hint: str,
    service_type: str, lead_quality: str,
    config: RunnableConfig,
) -> str:
    """Persiste el lead en el sistema de captura configurado."""
    lead_service: ILeadCaptureService = config["configurable"]["lead_service"]
    ...
```

### 3c. `src/giros_bot/tools/messaging_tool.py`
Solo usado en testing. En producción, el `send_text` lo llama el route handler directamente (no el agente).

---

## Fase 4: Prompts (6 system prompts)

`src/giros_bot/prompts/whatsapp.py`

**TRIAGE_PROMPT:** Clasifica uno de 6 intents. JSON `{intent, quick_ack}`. Regla: si el mensaje menciona "ordenar", "gestionar", "stock", "fiados", "cuentas" → `cotizacion_tendo`. Si menciona "web", "app", "logo", "marca", "automatizar", "redes", "diseño" → `cotizacion_servicios`.

**COTIZACION_TENDO_PROMPT** 🟢
- Contexto: Tendo ayuda a Pymes a ordenar su negocio (stock, fiados, caja, reportes)
- Precio: $20.000 CLP/mes — decirlo si preguntan
- Objetivo: cerrar trial 14 días — "¿Lo probamos esta semana? Sin tarjeta."
- Usar `capture_lead` tool al cerrar

**COTIZACION_SERVICIOS_PROMPT** 🛑 SDR mode
- Servicios disponibles (mencionables): web estática, landing, ecommerce, web app a medida, automatizaciones (Make/n8n/custom), gestión RRSS, identidad de marca (logo+manual), diseño gráfico
- **PROHIBIDO: cualquier precio, rango de UF o estimación temporal**
- Flujo obligatorio: tipo de proyecto → presupuesto asignado → email de contacto
- Al obtener email: usar `capture_lead` tool y finalizar con mensaje fijo de Socios Directores
- `lead_project_type` mapea a: web_landing | web_ecommerce | web_app | automatizacion | rrss | identidad_marca | diseno | otro

**SOPORTE_PROMPT:** empático, recopila síntoma, usa `capture_lead` si detecta oportunidad de venta

**INFO_GENERAL_PROMPT:** marketing digital Chile + servicios Giros, siempre CTA suave

**AGENDAR_PROMPT** 📅 VIP
- 2-3 preguntas de calificación ANTES de revelar agenda
- Si HIGH: usar `get_scheduling_link` tool → da URL al usuario
- Si LOW: desvía amablemente, actualiza `lead_quality = "low"`
- Al final: usar `capture_lead` tool independiente del outcome

---

## Fase 5: Graph Nodes

`src/giros_bot/graph/nodes/whatsapp/`

Cada agente:
- Recibe `state: WhatsAppState` + `config: RunnableConfig`
- LLM: `ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite")` (consistente con el resto)
- Tiene tools disponibles relevantes: solo los que necesita
- Retorna `dict` con campos actualizados de estado

**triage_node** → `Command(goto=intent)` sin tools
**cotizacion_tendo_agent** → tools: `capture_lead`
**cotizacion_servicios_agent** → tools: `capture_lead`
**soporte_agent** → tools: `capture_lead` (opcional)
**info_agent** → sin tools
**reserva_agent** → tools: `get_scheduling_link`, `capture_lead`

---

## Fase 6: whatsapp_graph.py

```python
def build_whatsapp_graph(
    checkpointer: AsyncPostgresSaver,
    scheduling_service: ISchedulingService,
    lead_service: ILeadCaptureService,
) -> CompiledStateGraph:
```

- Los servicios se inyectan en `graph.ainvoke(..., config={"configurable": {"scheduling_service": ..., "lead_service": ...}})`
- Esto permite mocks en tests sin modificar ningún agente

---

## Fase 7: API Route + Lifespan

### 7a. `src/giros_bot/routers/whatsapp.py`
- `GET /v1/webhook/whatsapp` → challenge Meta
- `POST /v1/webhook/whatsapp` → BackgroundTask, 200 < 200ms
- Anti-duplicados: `set` en `app.state` (simple para MVP)

### 7b. `src/giros_bot/main.py` lifespan actualizado
```python
# Instanciar integraciones CONCRETAS aquí (único lugar donde se eligen proveedores)
app.state.messaging_service  = WhatsAppAPIMessaging(settings)
app.state.scheduling_service = CalendlyScheduler(settings.scheduling_url)
# Para cambiar a Google Calendar el día de mañana:
# app.state.scheduling_service = GoogleCalendarScheduler(settings)
app.state.lead_service       = PostgresLeadCapture(engine)
app.state.whatsapp_graph     = build_whatsapp_graph(checkpointer, ...)
```

### 7c. `config.py` — variables nuevas
- `whatsapp_phone_number_id`, `whatsapp_verify_token`, `whatsapp_api_token`, `whatsapp_api_version`
- `scheduling_url: str = ""`  — URL de agenda (Calendly, Google Cal appts, etc.) — **proveedor-agnóstico**
- `scheduling_provider: str = "calendly"`  — para elegir impl concreta en lifespan
- `lead_notification_email: str = ""`  — placeholder próxima iteración

---

## Fase 8: Tests

### 8a. `tests/test_whatsapp_webhook.py`
- Challenge GET correcto/incorrecto
- POST 200 inmediato
- Deduplicación

### 8b. `tests/test_whatsapp_graph.py`
- `triage_node` clasifica correctamente todos los intents
- `cotizacion_servicios_agent` NO genera precio en ninguna respuesta
- `cotizacion_tendo_agent` SÍ menciona $20.000
- `reserva_agent` con mock `ISchedulingService` — no acoplar test al provider real
- Multi-turno: el bot recuerda el nombre del mensaje anterior

### 8c. Mock services para tests
```python
class MockSchedulingService:
    async def get_booking_url(self, context: dict) -> SchedulingResult:
        return SchedulingResult(True, "https://mock.url", "Mock", "Agenda aquí →")

class MockLeadCaptureService:
    saved_leads: list[LeadData] = []
    async def save_lead(self, lead: LeadData) -> bool:
        self.saved_leads.append(lead); return True
```

---

## Archivos a crear/modificar (31 archivos)

| Archivo | Op |
|---|---|
| `src/giros_bot/config.py` | MOD |
| `src/giros_bot/main.py` | MOD |
| `pyproject.toml` | MOD |
| `.env.example` | MOD |
| `src/giros_bot/routers/__init__.py` | CREAR |
| `src/giros_bot/routers/whatsapp.py` | CREAR |
| `src/giros_bot/schemas/whatsapp.py` | CREAR |
| `src/giros_bot/schemas/whatsapp_state.py` | CREAR |
| `src/giros_bot/services/messaging.py` | CREAR |
| `src/giros_bot/services/scheduling.py` | CREAR |
| `src/giros_bot/services/lead_capture.py` | CREAR |
| `src/giros_bot/integrations/__init__.py` | CREAR |
| `src/giros_bot/integrations/whatsapp_api.py` | CREAR |
| `src/giros_bot/integrations/scheduling/__init__.py` | CREAR |
| `src/giros_bot/integrations/scheduling/base.py` | CREAR |
| `src/giros_bot/integrations/scheduling/calendly.py` | CREAR |
| `src/giros_bot/integrations/scheduling/google_calendar.py` | CREAR (stub) |
| `src/giros_bot/integrations/lead/__init__.py` | CREAR |
| `src/giros_bot/integrations/lead/postgres_lead.py` | CREAR |
| `src/giros_bot/tools/messaging_tool.py` | CREAR |
| `src/giros_bot/tools/scheduling_tool.py` | CREAR |
| `src/giros_bot/tools/lead_tool.py` | CREAR |
| `src/giros_bot/prompts/whatsapp.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/__init__.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/triage_node.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/cotizacion_tendo_agent.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/cotizacion_servicios_agent.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/soporte_agent.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/info_agent.py` | CREAR |
| `src/giros_bot/graph/nodes/whatsapp/reserva_agent.py` | CREAR |
| `src/giros_bot/graph/whatsapp_graph.py` | CREAR |
| `tests/test_whatsapp_webhook.py` | CREAR |
| `tests/test_whatsapp_graph.py` | CREAR |

---

## Verificación
1. `GET /v1/webhook/whatsapp?hub.mode=subscribe&hub.challenge=TEST&hub.verify_token=...` → `TEST`
2. `POST /v1/webhook/whatsapp` (payload Meta de prueba) → 200 OK < 200ms
3. "cuánto vale una web" → NO hay precio, recoge email, loguea lead en DB
4. "necesito Tendo para mi almacén" → da $20.000/mes, empuja trial
5. "quiero reunirme" → 2 preguntas → HIGH → URL de agenda del proveedor configurado
6. Cambiar `scheduling_provider = "google_calendar"` en config → todo funciona sin tocar agentes
7. `pytest tests/test_whatsapp_webhook.py tests/test_whatsapp_graph.py` → verde
8. `ruff check src/` → sin errores

---

## Scope excluido MVP
- Audio/imagen/video en WhatsApp (solo texto)
- Panel admin conversaciones
- Templates HSM outbound proactivos
- Notificación automática de leads (email/Slack) — var de config placeholder lista
- Rate limiting por usuario
- Tabla `whatsapp_leads` en scripts de migración existentes (se crea al vuelo en lifespan)

---

## Decisiones Confirmadas
- **5 agentes especializados:** Cotización Tendo (precios abiertos + trial), Cotización Servicios (SDR sin precios), Soporte Técnico, Info General, Agendar (VIP con calificación)
- **Regla de negocio crítica:** El bot NO suelta precios de servicios web/diseño. Actúa como SDR y pasa el lead calificado al equipo directivo.
- **Precios abiertos solo en Tendo SaaS:** $20.000 CLP/mes, trial 14 días, cierre autónomo.
- **Agendar = filtro de calidad:** El reserva_agent hace 2-3 preguntas de calificación ANTES de revelar el Calendly. Leads de bajo nivel → derivados a web/PDF.
- **Checkpointer:** AsyncPostgresSaver (PostgreSQL existente)
- **Credenciales:** Plan incluye mock/fallback para dev sin credentials reales
- **Scope del bot:** Servicios Giros Media + consultas generales de marketing digital
- **thread_id:** Número de teléfono del remitente (único por usuario, persiste entre sesiones)
