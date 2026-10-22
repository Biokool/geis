# REVISIÓN PROFUNDA — GEIS × Biokool Radar (2026-10-21)

> Encargo de Chino: el ecosistema subido a `github.com/Biokool/geis` «no se parece a
> ninguno de los 2 sistemas, le faltan funcionalidades, no se entiende cómo iniciar
> ni cómo avanzar: son un montón de cosas dispersas, sin sincronía ni idea».
> Este documento es el diagnóstico verificado y el diseño rector de la corrección.

---

## 1. Qué era cada sistema original (la referencia)

### 1.1. Biokool Radar (el operativo)
Una **consola operativa de 5 vistas** con una historia clarísima:
**Panel → Operación → Leads → Mapa → Sistema.**
Su gracia: en una pantalla sabías cuántos leads hay (badge en el menú), si el
sistema está sano (dot de advertencia) y qué botón correr para avanzar la cadena
(scrapeo → dedup/score → señales → CRM → LinkedIn). Todo giraba alrededor del
**flujo de trabajo diario**, no de las pantallas.

### 1.2. GEIS (el analítico)
Una **plataforma de inteligencia territorial**: mapa con dibujo de polígonos,
análisis (ISM, Huff, TAM, IDT), reporte de 13 secciones con veredicto, comparador
multi-ubicación e historial de investigaciones. Su gracia: responder
**«¿dónde abro / a quién ataco?»** con números auditables.

### 1.3. La fusión actual (el problema)
- **13 destinos de menú en lista plana**, sin grupos ni orden de trabajo: el
  usuario ve pantallas, no un proceso. Nadie sabe qué hacer primero.
- **Comparador = stub vacío** («Fase 2») pese a que el backend sí calcula los
  análisis que lo alimentarían.
- **Dos listas de leads** (Espaciales DENUE / Curados Radar) como tabs con
  tablas y fichas distintas: el mismo concepto partido en dos, sin conteo total
  real (Inicio pagina 5×100 para contar — backlog P1).
- **Mapa incompleto**: dibuja establecimientos y el polígono, pero sin control
  de capas (leads con geometría, isócronas, territorios), sin leyenda y sin
  acciones desde el popup. El mapa no conversa con Leads ni con Reporte.
- **Inicio sin guía**: es un dashboard de KPIs; no responde «¿cómo empiezo?»
  ni «¿cuál es mi siguiente paso?».
- **Historial sin salida**: lista investigaciones pero no permite borrarlas ni
  reabrirlas en Mapa/Reporte (DELETE no existe — backlog P2).
- Lo bueno que SÍ existe y se conserva: backend íntegro (88/88 tests), cadena
  Radar operando con datos reales (160 leads, HubSpot, Apollo, LinkedIn, n8n),
  módulo de Configuración + IA interna, fórmulas reales y honestidad (501/404).

**Veredicto:** el motor está; lo que falta es **producto**: una historia, un
orden, y las funciones de detalle que conectan las pantallas entre sí.

---

## 2. Diseño rector: UN sistema, UNA historia

El ecosistema se ordena como un proceso de 5 momentos. La navegación los
refleja en grupos, en este orden:

| Grupo | Pregunta que responde | Pantallas |
|---|---|---|
| **Inicio** | ¿Cómo voy y qué hago ahora? | Inicio (centro de mando) |
| **1 · Inteligencia** | ¿Dónde están las oportunidades? | Mapa · Reporte · Comparador · Historial |
| **2 · Prospección** | ¿A quién contacto y en qué orden? | Leads · KPIs |
| **3 · Operación** | ¿Cómo se mueve la máquina? | Operación · Geofencing · Exportación |
| **4 · Sistema** | ¿Está sano y bien configurado? | Sistema · Configuración · Asistente IA |

### Funciones definidas por módulo (contrato)
- **Inicio = centro de mando.** Checklist «Primeros pasos» con estado REAL
  desde la API (1 perfil activo → 2 datos cargados → 3 primera investigación →
  4 leads generados → 5 primera corrida del pipeline), barra de progreso y UN
  botón de «siguiente paso». Debajo: KPIs clave, actividad reciente (runs) y
  accesos directos. Nada decorativo: todo clic lleva a hacer algo.
- **Mapa = el centro visual.** Capas conmutables con conteos: establecimientos
  DENUE, leads con geometría (color por score/temperatura), isócronas del
  análisis activo, territorios guardados. Leyenda visible. Popup con datos y
  acciones (ver ficha del lead, crear investigación aquí). Al dibujar un
  polígono: análisis inmediato + botón «Generar reporte».
- **Leads = UNA lista.** Una tabla, una ficha. Columna y filtro de **Origen**
  (Espacial/Radar), filtros: búsqueda, etapa, línea/producto, score mínimo.
  Contador total real (`GET /leads/count`). La ficha (drawer) trae score con
  desglose, «Cómo contactarlo», etapa editable y origen. Export = la vista
  filtrada.
- **Comparador = real.** Backend `POST /analysis/compare` con 2–5
  investigaciones → tabla de métricas (veredicto, ISM, TAM, competencia,
  población, Huff) con semáforos y «elegir ganadora» (la marca como principal).
- **Historial = memoria útil.** Cada investigación: reabrir en Mapa, ver
  Reporte, comparar (checkbox → Comparador) y **borrar** (`DELETE
  /investigations/{id}` con confirmación).
- **Operación, Geofencing, Exportación, KPIs, Sistema:** se conservan; solo
  reciben estados vacíos guiados («aún no hay X → ve a Y») y enlaces cruzados.
- **Configuración + Asistente IA:** se conservan tal cual (grupo Sistema).

### Reglas de UX (obligatorias en toda pantalla)
1. Toda lista vacía dice **qué falta y qué botón lo resuelve**.
2. Toda cifra muestra su origen (dato real / estimado) — honestidad GEIS.
3. Ningún botón sin destino: o funciona o no está.
4. Desde cualquier objeto (lead, investigación, territorio) se puede saltar
   al Mapa, a su Reporte y a su ficha — las pantallas conversan.

---

## 3. Backend a agregar (mínimo y suficiente)
- `GET /leads/count` → total real sin paginar (resuelve el hack 5×100).
- `POST /analysis/compare` {investigation_ids[2..5]} → métricas por
  investigación reutilizando el motor de análisis existente.
- `DELETE /investigations/{id}` → 204 (conserva auditoría: borrado lógico
  `deleted_at` si la tabla lo soporta; si no, físico con registro en log).

## 4. Validación profunda (checklist de cierre)
- [ ] `pytest` completo verde (88 previos + nuevos de count/compare/delete).
- [ ] `npm run build` verde.
- [ ] Contrato: ninguna llamada del frontend apunta a un endpoint inexistente
      (cruce `api.ts` ↔ OpenAPI).
- [ ] Recorrido manual por las 13 rutas con datos seed: cada página carga,
      muestra datos o un vacío guiado, y sus botones responden.
- [ ] Mapa: las 4 capas pintan con datos seed y la leyenda coincide.
- [ ] Leads: el contador coincide con `GET /leads/count`; filtros combinan.
- [ ] Comparador: 2 investigaciones seed producen tabla con ganadora.
- [ ] Inicio: el checklist refleja el estado real (sin perfil → paso 1 activo).

## 5. Fuera de alcance (se queda como estaba)
Motores de cálculo, workflows n8n, scraper, integraciones (HubSpot/Apollo/
LinkedIn), módulo de IA interna y sus 8 providers. Esto es **producto y
orquestación**, no reingeniería del motor.
