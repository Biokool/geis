/** Contenido embebido de `PERFIL-EMPRESA.md` (ver `docs/` del ecosistema).
 * Actualizado: generado desde docs el 2026-10-19. Si cambias el doc original,
 * regenera este archivo.
 */
export const PERFIL_TEMPLATE = `# PERFIL DE EMPRESA — Plantilla oficial GEIS

> **Qué es este archivo:** la configuración inicial del ecosistema. Todo lo que el sistema calcule, puntúe, reporte y aprenda de aquí en adelante se basa en lo que declares aquí: tu giro, tus productos/servicios, tu cliente ideal, tu territorio y tu forma de vender.
>
> **Quién lo llena (dos modos):**
> - **Modo humano:** responde cada pregunta donde dice \`[Tu respuesta aquí]\`. Si no sabes un dato, escribe \`[PENDIENTE]\`. No dejes preguntas vacías sin marca.
> - **Modo IA:** entrégale este archivo a una IA junto con tu URL, PDFs, presentaciones o textos de tu empresa y la instrucción: *"Llena este perfil con la información de mis materiales. No inventes datos: lo que no encuentres, márcalo como [PENDIENTE] y al final dime exactamente qué te falta para completarlo."*
>
> **Reglas para la IA que llena (obligatorias):**
> 1. Jamás inventes cifras (precios, empleados, sucursales). Si no están en los materiales → \`[PENDIENTE]\`.
> 2. El bloque YAML de arriba (\`---\`) es lo que el sistema lee automáticamente: debe quedar **válido y completo**. El cuerpo en markdown es el detalle para humanos.
> 3. Si un campo no aplica a tu negocio, escribe \`n/a\` con una nota de por qué.
> 4. Al terminar, lista aparte las preguntas que quedaron en \`[PENDIENTE]\` ordenadas por importancia.
> 5. Usa el vocabulario real de la empresa (nombres de productos, como los llama el cliente).

---
# BLOQUE ESTRUCTURADO (lo lee el sistema automáticamente — no cambies los nombres de los campos)
empresa:
  nombre: "[Tu respuesta aquí]"
  sitio_web: "[Tu respuesta aquí]"
  ubicacion_base: "[Tu respuesta aquí — ciudad, estado]"
  tamano_empleados: "[Tu respuesta aquí — número aproximado]"
  antiguedad_anos: "[Tu respuesta aquí]"
vertical:
  id: "[Tu respuesta aquí — ej: gimnasios, climatizacion, cafeterias, talleres_mecanicos, o 'personalizado']"
  giro_descripcion: "[Tu respuesta aquí — a qué se dedica, en una frase]"
productos:  # repite este bloque por cada producto/servicio/solución (mínimo 1)
  - nombre: "[Tu respuesta aquí]"
    descripcion: "[Tu respuesta aquí — qué es y para quién]"
    ticket_min_mxn: "[Tu respuesta aquí — número]"
    ticket_max_mxn: "[Tu respuesta aquí — número]"
    ciclo_venta_dias: "[Tu respuesta aquí — días típicos de primer contacto a cierre]"
    margen_aprox_pct: "[Tu respuesta aquí — o PENDIENTE]"
cliente_ideal:
  descripcion: "[Tu respuesta aquí — quién compra, con detalle]"
  tamano: "[Tu respuesta aquí — ej: empresas de 50-500 empleados, o personas de 25-45 años]"
  puesto_decisor: "[Tu respuesta aquí — quién firma: dueño, gerente de planta, mamá, etc.]"
  dolores: "[Tu respuesta aquí — lista de 3 a 5 problemas que tu cliente sufre hoy]"
propuesta_valor: "[Tu respuesta aquí — por qué te eligen a ti y no a otro, en 2-3 líneas]"
diferenciadores:
  - "[Tu respuesta aquí]"
competidores:
  - "[Tu respuesta aquí — nombre y en qué te gana/pierde]"
modelo_comercial:
  ticket_promedio_mxn: "[Tu respuesta aquí]"
  canales_contacto: "[Tu respuesta aquí — ej: llamada, whatsapp, visita, email]"
  ciclo_descripcion: "[Tu respuesta aquí — cómo se vende hoy, paso a paso]"
territorio:
  estados: "[Tu respuesta aquí — lista]"
  ciudades: "[Tu respuesta aquí — lista]"
  radio_km: "[Tu respuesta aquí — o PENDIENTE]"
estacionalidad:
  notas: "[Tu respuesta aquí — meses fuertes/débiles y por qué]"
objetivos:
  - "[Tu respuesta aquí — qué quieres lograr con el sistema: ej. 20 reuniones/mes]"
vocabulario:  # término: significado — para que el sistema hable tu idioma
  "[término]": "[significado]"
scian_sugeridos:  # códigos SCIAN de tus clientes o de tu giro (si los conoces; si no, PENDIENTE)
  - "[Tu respuesta aquí]"
---

# 1. Identidad de la empresa
1.1. Nombre comercial y razón social: [Tu respuesta aquí]
1.2. Sitio web y redes principales: [Tu respuesta aquí]
1.3. Ubicación base (donde opera hoy): [Tu respuesta aquí]
1.4. Tamaño (empleados) y antigüedad: [Tu respuesta aquí]
1.5. Sucursales o puntos actuales (lista con ciudad): [Tu respuesta aquí]

# 2. Giro / vertical
2.1. ¿A qué se dedica la empresa en una frase? [Tu respuesta aquí]
2.2. ¿Es B2B (vende a empresas), B2C (vende a personas) o mixto? [Tu respuesta aquí]
2.3. Si es B2B: ¿qué giros o industrias son tus clientes? (ej: naves industriales, restaurantes, escuelas) [Tu respuesta aquí]
2.4. Si es B2C: ¿qué perfil de persona es tu cliente? (edad, zona, hábitos) [Tu respuesta aquí]

# 3. Productos / servicios / soluciones (uno por bloque)
## 3.1. [Nombre del producto/servicio 1]
- ¿Qué es y qué problema resuelve? [Tu respuesta aquí]
- Precio o ticket (rango en MXN): [Tu respuesta aquí]
- ¿Se vende una vez, por suscripción/mensualidad o por proyecto? [Tu respuesta aquí]
- Ciclo de venta típico (días de primer contacto a cierre): [Tu respuesta aquí]
- Margen aproximado: [Tu respuesta aquí]
## 3.2. [Nombre del producto/servicio 2] (repite la estructura)

# 4. Cliente ideal (ICP)
4.1. Descríbelo como si fuera una persona o empresa concreta: [Tu respuesta aquí]
4.2. Tamaño / perfil: [Tu respuesta aquí]
4.3. ¿Quién decide la compra (puesto o rol)? [Tu respuesta aquí]
4.4. Sus 3–5 dolores principales hoy: [Tu respuesta aquí]
4.5. ¿Qué pasa si NO te compra (costo de no hacer nada)? [Tu respuesta aquí]
4.6. Señales de que es buen momento para contactarlo (ej: abrió sucursal, es temporada de calor, cambió de gerente): [Tu respuesta aquí]

# 5. Propuesta de valor y diferenciadores
5.1. ¿Por qué te eligen a ti y no a la competencia? (2–3 líneas) [Tu respuesta aquí]
5.2. Diferenciadores concretos (lista): [Tu respuesta aquí]
5.3. Prueba social (clientes conocidos, casos, números): [Tu respuesta aquí]

# 6. Competidores
6.1. Directos (venden lo mismo): [Tu respuesta aquí]
6.2. Indirectos (resuelven lo mismo de otra forma): [Tu respuesta aquí]
6.3. ¿En qué te ganan y en qué les ganas? [Tu respuesta aquí]

# 7. Modelo comercial actual
7.1. Ticket promedio en MXN: [Tu respuesta aquí]
7.2. Canales de contacto que usas (llamada, WhatsApp, visita, email, redes): [Tu respuesta aquí]
7.3. Describe tu proceso de venta paso a paso: [Tu respuesta aquí]
7.4. ¿Cuántos leads necesitas al mes para tus metas? [Tu respuesta aquí]

# 8. Territorio
8.1. Estados y ciudades donde operas hoy: [Tu respuesta aquí]
8.2. ¿A dónde quieres expandirte? [Tu respuesta aquí]
8.3. Radio máximo de operación en km (o PENDIENTE): [Tu respuesta aquí]

# 9. Estacionalidad
9.1. Meses fuertes y por qué: [Tu respuesta aquí]
9.2. Meses débiles y por qué: [Tu respuesta aquí]
9.3. ¿Hay eventos o temporadas que disparan la demanda? [Tu respuesta aquí]

# 10. Datos y fuentes disponibles
10.1. ¿Tienes CRM o lista de clientes/prospectos? (¿cuál?) [Tu respuesta aquí]
10.2. ¿Tienes base de datos de ubicaciones o sucursales? [Tu respuesta aquí]
10.3. Materiales que puedes compartir (web, PDFs, presentaciones): [Tu respuesta aquí]

# 11. Objetivos con el sistema
11.1. ¿Qué quieres lograr en 90 días? (ej: 20 reuniones/mes, 3 sucursales evaluadas) [Tu respuesta aquí]
11.2. ¿Qué decisión quieres que el sistema te ayude a tomar cada semana? [Tu respuesta aquí]

# 12. Vocabulario del negocio
12.1. Términos propios que usa tu empresa o tus clientes (término: significado): [Tu respuesta aquí]
12.2. ¿Cómo le dice tu cliente a lo que vendes (puede ser distinto a tu nombre interno)? [Tu respuesta aquí]

---
# CHECKLIST DE COMPLETITUD (para la IA o la persona que llena)
- [ ] Bloque YAML válido (sin \`[Tu respuesta aquí]\` en campos críticos: nombre, vertical.id, productos, cliente_ideal, territorio)
- [ ] Al menos 1 producto con ticket y ciclo de venta
- [ ] Cliente ideal con decisor y 3+ dolores
- [ ] Territorio definido (estados o ciudades)
- [ ] Lista de [PENDIENTE] al final, ordenada por importancia
`;
