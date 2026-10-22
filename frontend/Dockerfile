# =====================================================================
# GEIS · frontend/Dockerfile — build multietapa (Vite -> Nginx)
# ---------------------------------------------------------------------
# Etapa 1 (build): Node 20 compila la SPA (npm ci && npm run build).
#   El código fuente (src/, package.json) lo aporta el worker frontend.
#   VITE_* se incrustan en tiempo de build (ver .env.example).
# Etapa 2 (runtime): nginx:alpine sirve dist/ y proxya /api/ al backend.
# =====================================================================
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Runtime ---------------------------------------------------------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
