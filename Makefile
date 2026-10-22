# =====================================================================
# GEIS · Makefile — atajos sobre docker compose
# ---------------------------------------------------------------------
# Si existe .env en la raíz, sus variables quedan disponibles en los
# targets (p. ej. POSTGRES_USER para `make psql`).
# =====================================================================

ifneq (,$(wildcard .env))
include .env
export
endif

POSTGRES_USER ?= geis
POSTGRES_DB ?= geis

.PHONY: up down build logs migrate seed test psql clean help n8n scraper-logs

up:        ## Levanta los servicios base (construye imágenes) en segundo plano
	docker compose up --build -d

down:      ## Detiene y elimina contenedores (conserva los datos)
	docker compose down

build:     ## Construye las imágenes sin levantar los servicios
	docker compose build

logs:      ## Muestra los logs de todos los servicios (en vivo)
	docker compose logs -f

migrate:   ## Aplica las migraciones de Alembic (crea las tablas; corre antes del primer seed)
	docker compose exec api alembic upgrade head

seed:      ## Carga datos de muestra deterministas (requiere api arriba y migraciones aplicadas)
	docker compose exec api python -m app.seed

test:      ## Corre la suite de pruebas del backend
	docker compose exec api pytest -q

psql:      ## Abre psql contra la base de datos del proyecto
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

clean:     ## Detiene todo y BORRA volúmenes (datos) e imágenes locales
	docker compose down -v --rmi local

help:      ## Muestra esta ayuda
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Ecosistema GEIS × Radar (ver README, sección «Ecosistema GEIS × Radar») ---

n8n:       ## Levanta el perfil de automatización (n8n en :5678 con sus workflows)
	docker compose --profile automation up -d n8n

scraper-logs: ## Logs en vivo del servicio scraper (:5000)
	docker compose logs -f scraper
