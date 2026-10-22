# Señales manuales del SDR — `signals/`

El workflow n8n `03-signal-catcher` lee **`/signals/input.json`** (montado
read-only en el contenedor n8n) una vez al día (7am) o cuando se dispara el
webhook `radar-03`. Cada señal suma **+25 al score** del lead que coincida por
`nombre` (match insensible a mayúsculas), o crea el lead con `source='manual'`
si no existe.

## Quién lo edita

El **SDR a mano**, con cualquier editor de texto. No hay UI: es un archivo
plano versionable. Flujo típico: ves una noticia/licitación/post → agregas un
objeto al array → el workflow 03 lo procesa en la siguiente corrida y le suma
+25 al lead.

## Formato

`input.json` es un **array JSON**. Cada elemento:

| Campo      | Requerido | Descripción |
|------------|-----------|-------------|
| `empresa`  | sí        | Nombre de la empresa tal como aparece (o aparecerá) en `prod.leads.nombre`. El match es por nombre; si no coincide con ningún lead existente, se crea uno nuevo con `source='manual'`. |
| `evidencia`| sí        | Qué viste y dónde: la prueba de la señal (licitación, noticia, post, visita, referido…). |
| `fecha`    | sí        | Fecha de la evidencia en formato `AAAA-MM-DD`. |
| `giro`     | no        | Giro/actividad (`centro logístico`, `planta industrial`, `gasolinera`…). Ayuda a la línea recomendada. |
| `tipo`     | no        | Tipo de señal: `licitación`, `noticia`, `post`, `visita`, `referido`, `feria`, `otro`. |

Ver `input.example.json` para un ejemplo completo y válido.

## Reglas

- El archivo **debe ser JSON válido** (un array). Si el JSON está roto, el
  workflow 03 falla en "Parsear señales" y lo verás en las ejecuciones de n8n.
- `[]` (array vacío) es válido: significa "sin señales manuales hoy". El
  workflow sigue procesando las `warm_signals` de LinkedIn.
- Las señales ya procesadas **no** se borran solas: el workflow las aplica con
  idempotencia práctica (el +25 se suma una vez por corrida; si vuelves a
  correr el 03 sin cambios, el lead ya existe y vuelve a sumar — evita
  duplicar corridas manuales el mismo día).
- No pongas datos sensibles (teléfonos personales, correos privados): la
  evidencia debe ser información pública o comercial.
