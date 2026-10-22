# GEIS — Seguridad

## Modelo de amenazas (local-first)

Deployment local por defecto; la exposición pública es opcional (cloudflared) y debe endurecerse primero.

## Manejo de secretos

- **Verdad única**: `.env` — **nunca se commitea** (`.gitignore`); `.env.example` solo plantillas con valores de desarrollo.
- Secretos en juego (nombres): `SECRET_KEY` (firma JWT), `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY` (cifra credenciales n8n), `APOLLO_API_KEY`, `HUBSPOT_TOKEN`, `LINKEDIN_CLIENT_SECRET`/`LINKEDIN_ACCESS_TOKEN`, `APIFY_TOKEN`, `DENUE_API_TOKEN`, claves de proveedores IA.
- Backups SQL (`backup_*.sql`) pueden contener datos reales → excluidos de git.
- `signals/input.json` (datos del SDR en runtime) → excluido de git; `input.example.json` como plantilla.
- **Regla de la n8n**: `N8N_ENCRYPTION_KEY` se genera una vez y no se rota (rotarla descifra mal todas las credenciales del volumen `n8n_data` → crash loop).

## Endurecimientos aplicados (sesiones 2026-10)

1. `N8N_BASIC_AUTH_USER/PASSWORD` **eliminados** del `.env`/`.env.example` (autenticación legacy de n8n deprecada; la UI usa owner account propia).
2. `N8N_RESTRICT_FILE_ACCESS_TO=/signals`: n8n solo puede leer ese path — un workflow comprometido no exfilera archivos del host.
3. Credenciales n8n creadas **programáticamente** (`n8n import:credentials`) sin exponer tokens en el editor ni en logs.
4. `N8N_ENCRYPTION_KEY` añadida al servicio n8n en `docker-compose.yml` (persiste el cifrado entre recreaciones).
5. Scope mínimo verificado por integración: HubSpot (private app con `crm.*` + `crm.schemas.custom.write` añadido a mano), LinkedIn (solo `r_organization_social`, `w_organization_social`).
6. Validaciones de tokens: Apollo (`healthy/logged_in`), Apify (plan FREE, usuario `biokool`), HubSpot (scopes activos verificados por API).

## Superficie expuesta

| Puerto | Servicio | Exposición |
|---|---|---|
| 3000 | web (Nginx) | Localhost; proxy `/api/` interno |
| 8000 | api (Swagger en `/docs`) | Localhost — cerrar/autenticar si se expone |
| 5432 | Postgres | Localhost — credenciales fuertes obligatorias fuera de dev |
| 5678 | n8n (editor) | Localhost — **jamás exponer sin auth fuerte** |
| 5000 | scraper | Red interna; sin auth propia |

## Datos

- Datos personales/comerciales en `prod.leads` (empresas, contactos, emails Apollo) — tratar como confidenciales; export CSV tope 5,000 filas.
- Regla anti-cautiverio: la nube es espejo; borrar en HubSpot/Apollo no pierde el sistema de registro (Postgres).

## Pendientes de endurecimiento

- Auth de la API para despliegue expuesto (hoy no hay login en backend).
- TLS/HTTPS terminado (cloudflared lo da; en LAN no).
- Rotación documentada de tokens de nube con re-import de credenciales n8n.
