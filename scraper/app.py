# GEIS · Módulo Radar — microservicio scraper de Google Maps
# Implementación del provider `places` del ecosistema (ver docs/ECOSISTEMA-FUSION.md §3).
# Flask + Playwright (local), Apify (nube) o demo (datos de ejemplo), MISMO
# contrato REST. El backend se elige por request leyendo la tabla
# `prod.providers` de Postgres (name='scraper'): mode=local -> Playwright;
# mode=cloud/provider=apify -> actor apify/google-maps-scraper. Sin reiniciar
# nada: se cambia en el dashboard (Sistema -> Proveedores). Uso responsable:
# delays aleatorios, máx. 3 páginas por búsqueda y volúmenes modestos.
#
# Fixes portados de biokool-radar (ver docs/MODULO-RADAR.md §scraper):
# - _SCRAPE_LOCK: los scrapes de Playwright van SERIALIZADOS (chromium pesa
#   ~1-2 GB por instancia; en paralelo se comen la RAM y mueren a medias).
# - _limpiar_chromiums_zombis(): pkill de chromes huérfanos tras cada scrape.
# - Modo demo: datos de ejemplo para probar el embudo sin tocar Google Maps.
# - Espera explícita del feed (25 s) y del h1 de cada ficha (15 s).
# - Coordenadas preferentemente del href (!3d..!4d..), no de page.url.
# - texto() limpia iconos Private Use Area y saltos de línea de Maps.
from flask import Flask, request, jsonify
import os
import random
import re
import subprocess
import time
import threading
from urllib.parse import urlparse
import requests as http_requests
from playwright.sync_api import sync_playwright

try:
    import psycopg
    _PG = True
except Exception:
    _PG = False

app = Flask(__name__)

# Serializa los scrapes de Playwright: chromium pesa ~1-2 GB por navegador y
# los procesos quedan zombies si algo muere a mitad. Un solo scrape a la vez.
_SCRAPE_LOCK = threading.Lock()


def _limpiar_chromiums_zombis():
    """Mata chromes huérfanos (no deberían existir con el lock, pero por si acaso)."""
    try:
        subprocess.run(["pkill", "-9", "-f", "chromium"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Caché corto del modo del provider (60s) para no golpear Postgres en cada request
_prov_cache = {"ts": 0, "mode": "local", "provider": "local"}

# Datos de ejemplo para el backend 'demo' (pruebas sin tocar Google Maps).
# Mismo esquema de salida que scrape_local/scrape_apify.
_DEMO_SEED = {
    "bodegas": [
        ("Bodega Industrial Toluca", "Av. Independencia 120, Toluca, Edo. Méx.", 19.28, -99.65),
        ("Bodega Logística Lerma", "Blvd. Vicente Villafaña 45, Lerma, Edo. Méx.", 19.41, -99.48),
        ("Centro de Distribución Mexiquense", "Carr. México-Toluca km 42, Edo. Méx.", 19.35, -99.55),
    ],
    "centros logísticos": [
        ("Centro Logístico Querétaro", "Autopista México-Querétaro km 200, Qro.", 20.68, -100.38),
        ("Nave Industrial Apodaca", "Parque Industrial Apodaca, N.L.", 25.78, -100.19),
        ("Plataforma de Distribución CDMX", "Calz. de los Misterios 500, CDMX", 19.44, -99.12),
    ],
    "plantas industriales": [
        ("Planta Manufacturera Querétaro", "Parque Tecnológico Qro., Qro.", 20.73, -100.27),
        ("Planta de Envasado Toluca", "Zona Industrial Toluca, Edo. Méx.", 19.30, -99.60),
        ("Complejo Industrial Monterrey", "Apodaca, N.L.", 25.80, -100.20),
    ],
}
# Direcciones/web/teléfonos ficticios pero realistas para demostración.
_DEMO_DETAIL = [
    ("+52 722 123 4567", "https://www.ejemplo-empresa.mx", 4.3),
    ("+52 55 9876 5432", "https://www.ejemplo-industrial.com", 4.7),
    ("+52 442 111 2233", "https://www.ejemplo-logistica.mx", 4.1),
]


def _db():
    """Conexión a la base GEIS. Prioridad: DATABASE_URL del entorno;
    si no existe, variables PG* sueltas (defaults del compose GEIS)."""
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # Formato: postgresql+psycopg2://user:pass@host:port/db
        u = urlparse(url.replace("+psycopg2", ""))
        return psycopg.connect(
            host=u.hostname or "db",
            port=u.port or 5432,
            user=u.username or "geis",
            password=u.password or "",
            dbname=(u.path or "/geis").lstrip("/"),
            connect_timeout=5,
        )
    return psycopg.connect(
        host=os.environ.get("PGHOST", "db"),
        user=os.environ.get("PGUSER", "geis"),
        password=os.environ.get("PGPASSWORD", ""),
        dbname=os.environ.get("PGDATABASE", "geis"),
        connect_timeout=5,
    )


def guardar_en_staging(resultados, query, location):
    """Escritura directa a stg.leads_raw (opt-in vía "guardar": true).
    El flujo normal es n8n 01 -> INSERT; esto es un atajo para pruebas o
    para usar el scraper sin n8n."""
    insertados = 0
    with _db() as c:
        for r in resultados:
            if not r.get("nombre"):
                continue
            lat, lng = r.get("lat"), r.get("lng")
            c.execute(
                "INSERT INTO stg.leads_raw (nombre, giro, direccion, geom, telefono, web, rating, fuente, query) "
                "VALUES (%s, %s, %s, "
                "CASE WHEN %s::float IS NULL OR %s::float IS NULL THEN NULL "
                "ELSE ST_SetSRID(ST_MakePoint(%s::float, %s::float), 4326) END, "
                "%s, %s, %s, 'google_maps', %s)",
                (r.get("nombre"), query, r.get("direccion"), lng, lat, lng, lat,
                 r.get("telefono"), r.get("web"), r.get("rating"),
                 (query + " " + location).strip()),
            )
            insertados += 1
    return insertados


def resolver_backend():
    """Lee prod.providers(name='scraper'). Devuelve (mode, provider). Default: local."""
    if time.time() - _prov_cache["ts"] < 60:
        return _prov_cache["mode"], _prov_cache["provider"]
    mode, provider = "local", "local"
    if _PG:
        try:
            with _db() as c:
                row = c.execute(
                    "SELECT mode, provider FROM prod.providers WHERE name='scraper'"
                ).fetchone()
                if row:
                    mode, provider = row[0], row[1]
        except Exception:
            pass
    # Override por env (útil en pruebas)
    if os.environ.get("SCRAPER_PROVIDER") in ("local", "apify", "demo"):
        provider = os.environ["SCRAPER_PROVIDER"]
        mode = "cloud" if provider == "apify" else "local"
    _prov_cache.update(ts=time.time(), mode=mode, provider=provider)
    return mode, provider


def scrape_demo(query, location, max_results):
    """Backend demo: datos de ejemplo con el mismo contrato de salida.
    Sirve para probar el embudo completo sin depender de Google Maps."""
    seed = _DEMO_SEED.get(query.lower().strip())
    if not seed:
        # Fallback: combina todas las semillas si el query no está en la lista
        seed = [item for lst in _DEMO_SEED.values() for item in lst]
    out = []
    for i, (nombre, direccion, lat, lng) in enumerate(seed[:max_results]):
        tel, web, rating = _DEMO_DETAIL[i % len(_DEMO_DETAIL)]
        out.append({
            "nombre": nombre, "direccion": direccion, "telefono": tel,
            "web": web, "rating": rating, "lat": lat, "lng": lng,
            "url": f"https://maps.example.com/place/{nombre.lower().replace(' ', '-')}",
        })
    return out


def scrape_apify(query, location, max_results):
    """Backend nube: actor apify/google-maps-scraper. Mismo esquema de salida."""
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        raise RuntimeError("APIFY_TOKEN no configurado en el .env")
    search = (query + " " + location).strip()
    run = http_requests.post(
        "https://api.apify.com/v2/acts/apify~google-maps-scraper/runs",
        params={"token": token},
        json={"searchStringsArray": [search],
              "maxCrawledPlacesPerSearch": max_results,
              "language": "es", "countryCode": "mx"},
        timeout=30,
    )
    run.raise_for_status()
    run_id = run.json()["data"]["id"]
    # Poll hasta terminar (máx ~4 min)
    for _ in range(48):
        time.sleep(5)
        st = http_requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            params={"token": token}, timeout=30).json()["data"]["status"]
        if st in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            break
    if st != "SUCCEEDED":
        raise RuntimeError("Apify run terminó en estado: " + st)
    ds = run.json()["data"]["defaultDatasetId"]
    items = http_requests.get(
        f"https://api.apify.com/v2/datasets/{ds}/items",
        params={"token": token, "limit": max_results}, timeout=60).json()
    out = []
    for it in items if isinstance(items, list) else []:
        loc = it.get("location") or {}
        out.append({
            "nombre": it.get("title"), "direccion": it.get("address"),
            "telefono": it.get("phone"), "web": it.get("website"),
            "rating": it.get("totalScore") or it.get("stars"),
            "lat": loc.get("lat"), "lng": loc.get("lng"),
            "url": it.get("url"),
        })
    return out


def scrape_local(query, location, max_results):
    resultados, vistos = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=UA, locale="es-MX")
        try:
            q = (query + " " + location).strip().replace(" ", "+")
            page.goto("https://www.google.com/maps/search/" + q,
                      wait_until="domcontentloaded", timeout=60000)
            pausa()
            # Cierra SOLO el banner de consentimiento de cookies si aparece.
            # (No usar button[aria-label='Cerrar']: en Maps ese botón cierra
            # el panel lateral de resultados y deja la búsqueda vacía.)
            for sel in ["button:has-text('Aceptar todo')",
                        "button:has-text('Accept all')",
                        "form[action*='consent'] button"]:
                try:
                    b = page.query_selector(sel)
                    if b:
                        b.click()
                        pausa(1, 2)
                        break
                except Exception:
                    pass
            # Espera explícita al feed de resultados (máx 25 s)
            try:
                page.wait_for_selector('div[role="feed"]', timeout=25000)
            except Exception:
                pass
            # Hasta 3 "páginas": scrollea el feed y recolecta enlaces
            enlaces = []
            for _ in range(3):
                feed = page.query_selector('div[role="feed"]')
                if feed:
                    for _ in range(6):
                        try:
                            feed.evaluate("e => e.scrollBy(0, e.scrollHeight)")
                        except Exception:
                            break
                        pausa(1.5, 3)
                enlaces = page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
                if len(enlaces) >= max_results:
                    break
                pausa(2, 4)
            # Recolecta hrefs como strings ANTES de navegar: al hacer page.goto
            # a la primera ficha, los ElementHandle del feed quedan obsoletos
            # ("Execution context was destroyed") y la corrida se queda en 1.
            hrefs = []
            for a in enlaces[:max_results]:
                try:
                    h = a.get_attribute("href")
                    if h and h not in vistos:
                        vistos.add(h)
                        hrefs.append(h)
                except Exception:
                    continue
            # Visita cada ficha y extrae datos (best-effort)
            for href in hrefs:
                try:
                    page.goto(href, wait_until="domcontentloaded", timeout=45000)
                    try:
                        page.wait_for_selector("h1", timeout=15000)
                    except Exception:
                        pass
                    pausa()
                    nombre = texto(page.query_selector("h1"))
                    direccion = ""
                    d = page.query_selector('button[data-item-id="address"]')
                    if d:
                        direccion = texto(d)
                    telefono = ""
                    t = page.query_selector('button[data-item-id*="phone:tel:"]')
                    if t:
                        telefono = texto(t)
                        if not telefono:
                            m = re.search(r"tel:([\+\d\-\s\(\)]+)",
                                          t.get_attribute("data-item-id") or "")
                            if m:
                                telefono = m.group(1).strip()
                    web = ""
                    w = page.query_selector('a[data-item-id="authority"]')
                    if w:
                        web = w.get_attribute("href") or ""
                    rating = None
                    r_el = page.query_selector('div[aria-label*="estrellas"]')
                    if r_el:
                        m = re.search(r"([\d,\.]+)\s",
                                      r_el.get_attribute("aria-label") or "")
                        if m:
                            rating = float(m.group(1).replace(",", "."))
                    lat = lng = None
                    # 1) Del propio href: ...!3d19.2925!4d-99.6367 (siempre presente)
                    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", href)
                    if m:
                        lat, lng = float(m.group(1)), float(m.group(2))
                    else:
                        # 2) De la URL cargada: .../@lat,lng,zz
                        m2 = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", page.url)
                        if m2:
                            lat, lng = float(m2.group(1)), float(m2.group(2))
                    resultados.append({
                        "nombre": nombre, "direccion": direccion,
                        "telefono": telefono, "web": web, "rating": rating,
                        "lat": lat, "lng": lng, "url": href,
                    })
                except Exception:
                    continue  # una ficha fallida no tumba la corrida
        finally:
            browser.close()
    return resultados


def pausa(a=2.0, b=5.0):
    """Delay aleatorio entre acciones para parecer menos robot."""
    time.sleep(random.uniform(a, b))


_PUA = re.compile(r"[\uE000-\uF8FF\uFE0F\u200B\u00AD]")


def texto(el):
    try:
        # Google Maps incrusta iconos (Private Use Area U+E000–U+F8FF) y saltos
        # de línea; sin quitarlos terminan "pegados" al dato real.
        return _PUA.sub("", (el.inner_text() or "").replace("\n", " ")).strip()
    except Exception:
        return ""


@app.get("/health")
def health():
    mode, provider = resolver_backend()
    if provider == "demo":
        mode = "demo"
    return jsonify(ok=True, servicio="scraper", mode=mode, provider=provider,
                   apify_token=bool(os.environ.get("APIFY_TOKEN")))


@app.post("/scrape")
def scrape():
    data = request.get_json(force=True, silent=True) or {}
    query = str(data.get("query", "")).strip()
    location = str(data.get("location", "")).strip()
    try:
        max_results = max(1, min(int(data.get("max_results", 40) or 40), 60))
    except (TypeError, ValueError):
        max_results = 40
    if not query:
        return jsonify(ok=False, error="query requerido"), 400

    # Modo demo: si el request lo pide, el provider (DB/env) es demo o el
    # env lo fuerza, usa datos de ejemplo. Sirve para probar el embudo.
    mode, provider = resolver_backend()
    force_demo = bool(data.get("demo")) or provider == "demo" or \
        os.environ.get("SCRAPER_PROVIDER") == "demo"
    if force_demo:
        resultados = scrape_demo(query, location, max_results)
        return jsonify(ok=True, query=query, location=location, backend="demo",
                       count=len(resultados), results=resultados)

    # Backend intercambiable: mismo contrato REST, distinta fuente.
    try:
        if mode == "cloud" and provider == "apify":
            resultados = scrape_apify(query, location, max_results)
            backend = "apify"
        else:
            with _SCRAPE_LOCK:
                try:
                    resultados = scrape_local(query, location, max_results)
                    backend = "local-playwright"
                except Exception as e:
                    _limpiar_chromiums_zombis()
                    return jsonify(ok=False, error=str(e), backend=provider), 502
                finally:
                    _limpiar_chromiums_zombis()
    except Exception as e:
        return jsonify(ok=False, error=str(e), backend=provider), 502
    # Escritura opt-in a staging (el flujo normal es n8n 01 -> stg.leads_raw).
    guardados = 0
    if data.get("guardar") is True:
        try:
            guardados = guardar_en_staging(resultados, query, location)
        except Exception as e:
            return jsonify(ok=True, query=query, location=location, backend=backend,
                           count=len(resultados), results=resultados,
                           guardar_ok=False, guardar_error=str(e)), 200
    return jsonify(ok=True, query=query, location=location, backend=backend,
                   count=len(resultados), results=resultados,
                   guardar_ok=bool(data.get("guardar")), guardados=guardados)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
