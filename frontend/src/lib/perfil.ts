/**
 * Parser tolerante del bloque YAML (frontmatter) de PERFIL-EMPRESA.md.
 *
 * Solo se usa para la checklist de completitud en vivo del wizard de configuración.
 * NO es un parser YAML general: soporta el subconjunto que usa la plantilla
 * (mapas anidados con indentación de 2 espacios, listas con `-`, escalares con
 * o sin comillas, comentarios con `#`). Sin dependencias externas.
 */

export interface PerfilCheck {
  id: 'nombre' | 'vertical' | 'productos' | 'cliente_ideal' | 'territorio';
  label: string;
  ok: boolean;
}

export interface PerfilParseResult {
  /** Mapa raíz del frontmatter, o null si no se pudo extraer/parsear. */
  data: Record<string, unknown> | null;
  /** Descripción del problema (bloque no encontrado o YAML inválido), o null si todo bien. */
  error: string | null;
  /** Etiquetas de los requisitos pendientes (para mostrar como advertencia). */
  faltantes: string[];
  /** Estado detallado de cada requisito de la checklist. */
  checks: PerfilCheck[];
}

interface YLine {
  text: string;
  indent: number;
}

function indentOf(line: string): number {
  const m = /^ */.exec(line);
  return m ? m[0].length : 0;
}

/** Quita un comentario `# ...` solo si está fuera de comillas. */
function stripComment(body: string): string {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === "'" && !inDouble) inSingle = !inSingle;
    else if (c === '"' && !inSingle) inDouble = !inDouble;
    else if (c === '#' && !inSingle && !inDouble && i > 0 && (body[i - 1] === ' ' || body[i - 1] === '\t')) {
      return body.slice(0, i).trimEnd();
    }
  }
  return body;
}

function scalar(s: string): unknown {
  const t = s.trim();
  if (t === '') return null;
  if (t.length >= 2 && ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'")))) {
    return t.slice(1, -1);
  }
  return t;
}

function esItemLista(text: string): boolean {
  return text === '-' || text.startsWith('- ');
}

function parseBlock(lines: YLine[], i: number, indent: number): [unknown, number] {
  const t = lines[i].text;
  if (esItemLista(t)) {
    const arr: unknown[] = [];
    while (i < lines.length && lines[i].indent === indent && esItemLista(lines[i].text)) {
      const rest = lines[i].text === '-' ? '' : lines[i].text.slice(2).trim();
      i++;
      if (rest === '') {
        // Item vacío con sub-bloque anidado.
        if (i < lines.length && lines[i].indent > indent) {
          const [node, ni] = parseBlock(lines, i, lines[i].indent);
          arr.push(node);
          i = ni;
        } else {
          arr.push(null);
        }
        continue;
      }
      const m = /^([^:]+):\s*(.*)$/.exec(rest);
      if (m) {
        // Item que inicia un mapa: "- clave: valor" + más claves con mayor indentación.
        const obj: Record<string, unknown> = {};
        const key = m[1].trim();
        const val = m[2];
        if (val === '') {
          if (i < lines.length && lines[i].indent > indent) {
            const [node, ni] = parseBlock(lines, i, lines[i].indent);
            obj[key] = node;
            i = ni;
          } else {
            obj[key] = null;
          }
        } else {
          obj[key] = scalar(val);
        }
        const childIndent = indent + 2; // convención de la plantilla (2 espacios)
        while (i < lines.length && lines[i].indent === childIndent && !esItemLista(lines[i].text)) {
          const cm = /^([^:]+):\s*(.*)$/.exec(lines[i].text);
          if (!cm) break;
          const ck = cm[1].trim();
          const cv = cm[2];
          i++;
          if (cv === '') {
            if (i < lines.length && lines[i].indent > childIndent) {
              const [node, ni] = parseBlock(lines, i, lines[i].indent);
              obj[ck] = node;
              i = ni;
            } else {
              obj[ck] = null;
            }
          } else {
            obj[ck] = scalar(cv);
          }
        }
        arr.push(obj);
      } else {
        arr.push(scalar(rest));
      }
    }
    return [arr, i];
  }
  // Mapa: líneas "clave: valor" al mismo nivel de indentación.
  const obj: Record<string, unknown> = {};
  while (i < lines.length && lines[i].indent === indent && !esItemLista(lines[i].text)) {
    const m = /^([^:]+):\s*(.*)$/.exec(lines[i].text);
    if (!m) throw new Error(`No se entendió la línea "${lines[i].text}" (se esperaba "clave: valor").`);
    const key = m[1].trim();
    const val = m[2];
    i++;
    if (val === '') {
      if (i < lines.length && lines[i].indent > indent) {
        const [node, ni] = parseBlock(lines, i, lines[i].indent);
        obj[key] = node;
        i = ni;
      } else {
        obj[key] = null;
      }
    } else {
      obj[key] = scalar(val);
    }
  }
  return [obj, i];
}

function parseYamlSimple(text: string): { data: unknown; error: string | null } {
  const lines: YLine[] = [];
  for (const raw of text.split('\n')) {
    if (!raw.trim()) continue;
    const indent = indentOf(raw);
    const body = stripComment(raw.slice(indent));
    if (!body.trim() || body.startsWith('#')) continue;
    lines.push({ text: body.trim(), indent });
  }
  if (lines.length === 0) return { data: {}, error: null };
  try {
    const [node] = parseBlock(lines, 0, lines[0].indent);
    return { data: node, error: null };
  } catch (e) {
    return { data: null, error: e instanceof Error ? e.message : String(e) };
  }
}

/** true si el valor parece un dato real (no vacío, no placeholder, no PENDIENTE). */
function relleno(v: unknown): boolean {
  if (typeof v !== 'string') return false;
  const t = v.trim();
  if (t === '') return false;
  if (t.toLowerCase() === 'n/a') return true; // "no aplica" con nota = dato válido
  if (t.includes('Tu respuesta aquí')) return false;
  const up = t.toUpperCase();
  if (up === 'PENDIENTE' || up === '[PENDIENTE]') return false;
  return true;
}

function getPath(data: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, k) => {
    if (acc && typeof acc === 'object' && !Array.isArray(acc)) return (acc as Record<string, unknown>)[k];
    return undefined;
  }, data);
}

function buildChecks(data: Record<string, unknown> | null): PerfilCheck[] {
  const d: Record<string, unknown> = data ?? {};
  const productos = getPath(d, 'productos');
  const productosOk =
    Array.isArray(productos) &&
    productos.length > 0 &&
    productos.some(
      (p) => p && typeof p === 'object' && relleno((p as Record<string, unknown>).nombre),
    );
  const territorioOk =
    relleno(getPath(d, 'territorio.estados')) || relleno(getPath(d, 'territorio.ciudades'));
  return [
    { id: 'nombre', label: 'Nombre de la empresa', ok: relleno(getPath(d, 'empresa.nombre')) },
    { id: 'vertical', label: 'vertical.id (giro)', ok: relleno(getPath(d, 'vertical.id')) },
    { id: 'productos', label: 'Al menos 1 producto', ok: productosOk },
    { id: 'cliente_ideal', label: 'Cliente ideal', ok: relleno(getPath(d, 'cliente_ideal.descripcion')) },
    { id: 'territorio', label: 'Territorio (estados o ciudades)', ok: territorioOk },
  ];
}

/**
 * Extrae el bloque entre la primera y la segunda línea `---` del markdown y lo
 * parsea con el parser tolerante. Si algo falla, `data` es null y `error`
 * describe el problema sin romper a quien lo llame.
 */
export function parseFrontmatter(md: string): PerfilParseResult {
  const lines = md.split('\n');
  let inicio = -1;
  let fin = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === '---') {
      if (inicio === -1) inicio = i;
      else {
        fin = i;
        break;
      }
    }
  }
  if (inicio === -1 || fin === -1) {
    return {
      data: null,
      error: 'No se encontró el bloque estructurado (el contenido entre las líneas "---").',
      faltantes: ['Bloque YAML no encontrado'],
      checks: buildChecks(null),
    };
  }
  const yaml = lines.slice(inicio + 1, fin).join('\n');
  const { data, error } = parseYamlSimple(yaml);
  const root = data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : null;
  const checks = buildChecks(root);
  return {
    data: root,
    error,
    faltantes: checks.filter((c) => !c.ok).map((c) => c.label),
    checks,
  };
}

/** Sustituye el valor de `vertical.id` en el frontmatter por el giro elegido en el paso 1. */
export function precargarVertical(md: string, verticalId: string): string {
  const lines = md.split('\n');
  let enVertical = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^vertical:\s*$/.test(lines[i])) {
      enVertical = true;
      continue;
    }
    if (enVertical) {
      // Fin del bloque vertical: una línea sin indentación.
      if (/^\S/.test(lines[i]) && lines[i].trim() !== '') break;
      const m = /^(\s*id:\s*)(".*"|'.*'|.+)$/.exec(lines[i]);
      if (m) {
        lines[i] = `${m[1]}"${verticalId}"`;
        break;
      }
    }
  }
  return lines.join('\n');
}
