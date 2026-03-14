"""
Test E2E del pipeline completo — DRY RUN.

Ejecuta el grafo REAL con llamadas a LLMs reales, pero:
  - NO llama al webhook de Make.com (social_webhook_url = "")
  - NO commitea a GitHub (github_token = "")
  - Guarda la imagen generada en tests/output/ para inspección visual
  - Imprime un reporte detallado de cada nodo

Uso:
  cd /home/girosmedia/Desarrollo/giros-bot
  source .venv/bin/activate
  python tests/test_pipeline_dry_run.py [YYYY-MM-DD]

Si no se pasa fecha, usa la fecha de hoy.
"""

import asyncio
import base64
import json
import logging
import sys
import textwrap
import time
from datetime import date
from pathlib import Path

from giros_bot.schemas.state import FrontendCategory

# ── Setup logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level="INFO",
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dry_run")

# ── Output dir ───────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def separator(title: str) -> str:
    return f"\n{'='*70}\n  {title}\n{'='*70}"


async def run_dry_pipeline(target_date: str) -> dict:
    """
    Ejecuta el pipeline completo pero mockea Publisher para que
    no publique a GitHub ni dispare webhook.
    """
    # ── Mock del publisher ────────────────────────────────────────────────
    # _wrap() convierte AgentStateDict → AgentState antes de llamar al nodo,
    # así que el mock recibe AgentState directamente.
    async def mock_publisher(state):
        """Simula publisher: reemplaza placeholder pero NO commitea ni llama webhook."""
        mdx_final = state.mdx_content_body.replace(
            "__IMAGE_ALT__",
            state.image_alt or f"Imagen de portada para: {state.title}",
        )
        logger.info(
            "Publisher [DRY RUN]: MDX procesado (%d chars). Skipping GitHub + Webhook.",
            len(mdx_final),
        )

        from giros_bot.publication.services.social.watermark import apply_watermark_to_b64
        
        watermarked_b64 = state.image_bytes_b64
        if state.image_bytes_b64:
            logger.info("Publisher [DRY RUN]: Aplicando marca de agua para RRSS...")
            watermarked_b64 = await asyncio.to_thread(
                apply_watermark_to_b64,
                state.image_bytes_b64,
                "Recurso 4@2ximagoc.png"
            )

            # Guardar la version con marca de agua para el payload simulado (e impresion en tests/output)
            slug = state.slug or "test"
            watermarked_path = OUTPUT_DIR / f"{slug}_watermarked.jpg"
            watermarked_path.write_bytes(base64.b64decode(watermarked_b64))
            logger.info("Publisher [DRY RUN]: 💾 Imagen con marca de agua guardada → %s", watermarked_path)

        return {
            "mdx_content_body": mdx_final,
            "image_url_generated": f"/blog/{state.slug}.jpg",
            # Hacemos trampa en el test actualizando el output para que print_report lo muestre
             "image_bytes_b64": watermarked_b64
        }

    # Patchear publisher_node ANTES de que build_graph() lo capture con _wrap()
    import giros_bot.publication.graph as graph_module
    original_publisher = graph_module.publisher_node

    graph_module.publisher_node = mock_publisher
    try:
        compiled = graph_module.build_graph()
    finally:
        graph_module.publisher_node = original_publisher

    initial_state = {
        "target_date":       target_date,
        "content_type":      None,
        "target_category":   FrontendCategory.DISENO_WEB, # Forzamos Diseño Web para ver diversidad
        "market_context":    "",
        "internal_knowledge": "",
        "title":             "",
        "slug":              "",
        "frontend_category": None,
        "tags":              [],
        "description":       "",
        "mdx_content_body":  "",
        "social_assets":     None,
        "image_prompt":      "",
        "image_alt":         "",
        "image_url_generated": "",
        "image_bytes_b64":   "",
        "article_format":    None,
        "editorial_brief":   "",
        "hero_product":      "",
        "selling_intensity": "soft",
        "target_audience":   "",
        "pain_point":        "",
        "hook_angle":        "",
        "key_takeaway":      "",
        "quality_score":     0,
        "retry_count":       0,
        "error_message":     "",
    }

    final_state = await compiled.ainvoke(initial_state)
    return final_state


def print_report(state: dict, elapsed: float):
    """Imprime un reporte completo y legible de la salida del pipeline."""

    print(separator("REPORTE DRY RUN — GIROS AUTOBOT"))
    print(f"  Tiempo total: {elapsed:.1f}s")
    print(f"  Fecha: {state.get('target_date')}")

    # ── SCHEDULER ────────────────────────────────────────────────────────
    print(separator("1. SCHEDULER"))
    ct = state.get("content_type")
    content_type_str = ct.value if hasattr(ct, "value") else str(ct)
    tc = state.get("target_category")
    target_cat_str = tc.value if hasattr(tc, "value") else str(tc)
    print(f"  Content Type:    {content_type_str}")
    print(f"  Target Category: {target_cat_str}")

    # ── SCOUT ────────────────────────────────────────────────────────────
    print(separator("2. SCOUT"))
    ik = state.get("internal_knowledge", "")
    mc = state.get("market_context", "")
    print(f"  Internal Knowledge ({len(ik)} chars):")
    print(textwrap.indent(textwrap.fill(ik[:500], 90), "    "))
    if len(ik) > 500:
        print(f"    ... ({len(ik) - 500} chars más)")

    print(f"\n  Market Context ({len(mc)} chars):")
    print(textwrap.indent(textwrap.fill(mc[:500], 90), "    "))
    if len(mc) > 500:
        print(f"    ... ({len(mc) - 500} chars más)")

    # Verificar atribución de fuentes
    has_kb = "[KB]" in mc
    has_tavily = "[TAVILY]" in mc
    has_inf = "[INFERENCIA]" in mc
    print(f"\n  Atribución de fuentes: [KB]={'✅' if has_kb else '❌'}  [TAVILY]={'✅' if has_tavily else '❌'}  [INFERENCIA]={'✅' if has_inf else '⚠️ (no usada)'}")

    # ── STRATEGIST ───────────────────────────────────────────────────────
    print(separator("3. STRATEGIST"))
    fc = state.get("frontend_category")
    fc_str = fc.value if hasattr(fc, "value") else str(fc)
    af = state.get("article_format")
    af_str = af.value if hasattr(af, "value") else str(af)
    print(f"  Title:           {state.get('title')}")
    print(f"  Slug:            {state.get('slug')}")
    print(f"  Category:        {fc_str}")
    print(f"  Article Format:  {af_str}")
    print(f"  Selling:         {state.get('selling_intensity', 'soft')}")
    print(f"  Tags:            {state.get('tags')}")
    print(f"  Target Audience: {state.get('target_audience')}")
    print(f"  Pain Point:      {state.get('pain_point')}")
    print(f"  Hook Angle:      {state.get('hook_angle')}")
    print(f"  Key Takeaway:    {state.get('key_takeaway')}")
    print(f"  Hero Product:    {state.get('hero_product')}")
    print(f"\n  Editorial Brief:")
    brief = state.get("editorial_brief", "")
    print(textwrap.indent(textwrap.fill(brief, 90), "    "))

    # ── WRITER ───────────────────────────────────────────────────────────
    print(separator("4. WRITER"))
    mdx = state.get("mdx_content_body", "")
    print(f"  MDX Length:      {len(mdx)} chars")
    print(f"  Description:     {state.get('description')}")

    # Checks de calidad del MDX
    checks = {
        "Frontmatter (---)": mdx.startswith("---"),
        "CTA box":           "cta-box" in mdx,
        "WhatsApp link":     "wa.me" in mdx,
        "Precio hero product": any(p in mdx for p in ["$290.000", "$180.000", "$550.000", "$19.990", "$12.990"]),
        "H2 variados":       mdx.count("## ") >= 3,
        "No 'El Problema'":  "## El Problema" not in mdx,
        "No 'La Solución'":  "## La Solución" not in mdx,
        "No frases IA":      all(f not in mdx.lower() for f in [
            "en el panorama digital", "al siguiente nivel",
            "es crucial", "es fundamental", "sin lugar a dudas",
            "en la era de la transformación",
        ]),
        "No pregunta retórica apertura": not mdx.split("---")[2].strip().startswith("¿") if mdx.count("---") >= 2 else False,
        "__IMAGE_ALT__ reemplazado": "__IMAGE_ALT__" not in mdx,
        "No tags internos [KB]/[TAVILY]": all(tag not in mdx.split("---", 2)[-1] for tag in ["[KB]", "[TAVILY]", "[INFERENCIA]"]),
    }
    print("\n  Quality Checks:")
    for check, passed in checks.items():
        print(f"    {'✅' if passed else '❌'} {check}")

    # Contar productos mencionados
    products = {
        "Pack Presencia Digital": "$290.000" in mdx,
        "Pack Identidad":        "$180.000" in mdx,
        "Pack E-commerce Pro":   "$550.000" in mdx,
        "Tendo Total":           "$19.990" in mdx,
        "Tendo Zimple":          "$12.990" in mdx,
    }
    mentioned = [p for p, v in products.items() if v]
    hero = state.get("hero_product", "")
    print(f"\n  Productos mencionados ({len(mentioned)}): {', '.join(mentioned) or 'NINGUNO'}")
    print(f"  Hero Product:    {hero}")
    if len(mentioned) > 2:
        print("  ⚠️  ALERTA: más de 2 productos con precio — puede ser catálogo")

    # Preview del MDX (inicio y final)
    print(f"\n  MDX Preview (primeros 600 chars):")
    print(textwrap.indent(mdx[:600], "    "))
    print(f"\n  MDX Final (últimos 400 chars):")
    print(textwrap.indent(mdx[-400:], "    "))

    # ── SOCIAL ───────────────────────────────────────────────────────────
    print(separator("5. SOCIAL"))
    sa = state.get("social_assets")
    if sa:
        sa_dict = sa.model_dump() if hasattr(sa, "model_dump") else sa
        for platform in ["linkedin_copy", "instagram_copy", "facebook_copy"]:
            copy = sa_dict.get(platform, "")
            label = platform.replace("_copy", "").upper()
            print(f"\n  ── {label} ({len(copy)} chars) ──")
            print(textwrap.indent(copy, "    "))

        # Coherencia: ¿los 3 hablan del mismo tema?
        brief_words = set(state.get("editorial_brief", "").lower().split())
        keyword_overlap = sum(
            1 for w in brief_words
            if len(w) > 5 and any(w in sa_dict.get(p, "").lower() for p in ["linkedin_copy", "instagram_copy", "facebook_copy"])
        )
        print(f"\n  Coherencia con brief: {keyword_overlap} keywords compartidas")
    else:
        print("  ❌ social_assets es None")

    # ── VISUAL ───────────────────────────────────────────────────────────
    print(separator("6. VISUAL"))
    print(f"  Visual Style: {state.get('visual_style', '')}")
    img_prompt = state.get("image_prompt", "")
    img_alt = state.get("image_alt", "")
    img_b64 = state.get("image_bytes_b64", "")

    print(f"  Image Alt:    {img_alt}")
    print(f"\n  Image Prompt ({len(img_prompt)} chars):")
    print(textwrap.indent(textwrap.fill(img_prompt, 90), "    "))

    # Checks visuales (V5: escenas documentales, no bodegones)
    prompt_lower = img_prompt.lower()
    visual_checks = {
        "No 'map pin'":            "map pin" not in prompt_lower,
        "No 'location pin'":       "location pin" not in prompt_lower,
        "No 'GPS'":                "gps" not in prompt_lower,
        "No text in image":        "no text" in prompt_lower,
        "No 'still-life'":         "still-life" not in prompt_lower and "still life" not in prompt_lower,
        "No 'black background'":   "black background" not in prompt_lower and "dark background" not in prompt_lower,
        "Has scene/environment":   any(w in prompt_lower for w in ["shop", "store", "kitchen", "office", "counter", "workshop", "storefront", "desk", "restaurant", "market", "studio", "salon", "local", "interior"]),
        "16:9 format":             "16:9" in img_prompt,
        "Image generated":         len(img_b64) > 100,
    }
    print("\n  Visual Checks:")
    for check, passed in visual_checks.items():
        print(f"    {'✅' if passed else '❌'} {check}")

    if img_b64:
        img_bytes = base64.b64decode(img_b64)
        slug = state.get("slug", "test")
        img_path = OUTPUT_DIR / f"{slug}.jpg"
        img_path.write_bytes(img_bytes)
        print(f"\n  💾 Imagen guardada → {img_path} ({len(img_bytes):,} bytes)")
    else:
        print("\n  ⚠️  No se generó imagen")

    # ── VALIDATOR ────────────────────────────────────────────────────────
    print(separator("7. VALIDATOR"))
    print(f"  Quality Score: {state.get('quality_score')}/10")
    print(f"  Retry Count:   {state.get('retry_count')}")
    err = state.get("error_message", "")
    if err:
        print(f"  Issues:        {err}")

    # ── MDX COMPLETO ─────────────────────────────────────────────────────
    print(separator("8. MDX COMPLETO"))
    mdx_path = OUTPUT_DIR / f"{state.get('slug', 'test')}.mdx"
    mdx_path.write_text(mdx, encoding="utf-8")
    print(f"  💾 MDX guardado → {mdx_path}")

    # ── SOCIAL COMPLETO (JSON) ───────────────────────────────────────────
    if sa:
        social_path = OUTPUT_DIR / f"{state.get('slug', 'test')}_social.json"
        sa_out = sa.model_dump() if hasattr(sa, "model_dump") else sa
        social_path.write_text(json.dumps(sa_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  💾 Social JSON → {social_path}")

    # ── RESUMEN FINAL ────────────────────────────────────────────────────
    print(separator("RESUMEN"))
    all_checks = {**checks, **visual_checks}
    passed = sum(1 for v in all_checks.values() if v)
    total = len(all_checks)
    score = state.get("quality_score", 0)
    print(f"  Checks pasados: {passed}/{total}")
    print(f"  Quality Score:  {score}/10")
    print(f"  Archivos en:    {OUTPUT_DIR}/")

    if passed == total and score >= 7:
        print("\n  🟢 PIPELINE OK — Listo para producción")
    elif passed >= total * 0.7:
        print("\n  🟡 PIPELINE ACEPTABLE — Revisar issues arriba")
    else:
        print("\n  🔴 PIPELINE CON PROBLEMAS — Revisar antes de publicar")

    return all_checks


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(f"\n🚀 Iniciando DRY RUN para {target}...")
    print(f"   (LLMs reales, sin GitHub, sin webhook)\n")

    start = time.time()
    try:
        state = await run_dry_pipeline(target)
    except Exception as e:
        logger.error("Pipeline falló: %s", e, exc_info=True)
        print(f"\n❌ Pipeline falló: {e}")
        sys.exit(1)

    elapsed = time.time() - start
    print_report(state, elapsed)


if __name__ == "__main__":
    asyncio.run(main())
