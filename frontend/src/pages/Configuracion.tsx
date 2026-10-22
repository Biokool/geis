import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/Alert';
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/AlertDialog';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/Dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Textarea } from '@/components/ui/Textarea';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Separator } from '@/components/ui/Separator';
import { Progress } from '@/components/ui/Progress';
import { Spinner } from '@/components/ui/Spinner';
import { Skeleton } from '@/components/ui/Skeleton';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { Stepper, StepperMobileLabel } from '@/components/ui/Stepper';
import { Toast } from '@/components/ui/Toast';
import {
  getCompanyProfile, putCompanyProfile, deriveCompanyConfig, activateCompanyProfile,
  listCompanyProfiles, getAiStatus, postAiFillProfile,
  errorMessage, ApiError,
  type VerticalConfig, type CompanyProfileSummary,
} from '@/lib/api';
import { parseFrontmatter, precargarVertical, type PerfilParseResult } from '@/lib/perfil';
import { PERFIL_TEMPLATE } from '@/data/perfilTemplate';
import { PERFIL_EJEMPLO_GIMNASIOS } from '@/data/perfilEjemploGimnasios';

const PASOS = [
  { id: 'giro', label: 'Giro', description: '¿A qué se dedica tu empresa?' },
  { id: 'perfil', label: 'Perfil', description: 'Describe tu empresa' },
  { id: 'ia', label: 'IA interna', description: 'API keys (opcional)' },
  { id: 'resumen', label: 'Resumen', description: 'Revisa y activa' },
];

const GIROS = [
  { id: 'climatizacion', icono: '❄️', nombre: 'Climatización', descripcion: 'Control térmico, aire acondicionado y bioclimatización evaporativa.' },
  { id: 'gimnasios', icono: '🏋️', nombre: 'Gimnasios', descripcion: 'Acondicionamiento físico, clases grupales y entrenamiento personal.' },
  { id: 'cafeterias', icono: '☕', nombre: 'Cafeterías / Restaurantes', descripcion: 'Venta de alimentos y bebidas, servicio en local.' },
  { id: 'talleres_mecanicos', icono: '🔧', nombre: 'Talleres mecánicos', descripcion: 'Reparación y mantenimiento de vehículos.' },
  { id: 'personalizado', icono: '✏️', nombre: 'Personalizado', descripcion: 'Otro giro: escríbelo y adapta la plantilla a tu negocio.' },
];

type AIProviderExtra = { id: string; label: string; env: string; placeholder: string };
type AIProvider = {
  id: string; nombre: string; env: string; alias: string[];
  nota?: string; extra?: AIProviderExtra;
};

const AI_PROVIDERS: AIProvider[] = [
  { id: 'openai', nombre: 'OpenAI', env: 'OPENAI_API_KEY', alias: ['openai'] },
  { id: 'anthropic', nombre: 'Anthropic', env: 'ANTHROPIC_API_KEY', alias: ['anthropic', 'claude'] },
  { id: 'gemini', nombre: 'Gemini', env: 'GEMINI_API_KEY', alias: ['gemini', 'google'] },
  { id: 'groq', nombre: 'Groq', env: 'GROQ_API_KEY', alias: ['groq'] },
  { id: 'deepseek', nombre: 'DeepSeek', env: 'DEEPSEEK_API_KEY', alias: ['deepseek'] },
  { id: 'openrouter', nombre: 'OpenRouter', env: 'OPENROUTER_API_KEY', alias: ['openrouter'], nota: 'Gateway multi-modelo (endpoint compatible OpenAI)' },
  { id: 'nvidia', nombre: 'NVIDIA NIM', env: 'NVIDIA_API_KEY', alias: ['nvidia'], nota: 'build.nvidia.com (endpoint compatible OpenAI)' },
  {
    id: 'cloudflare', nombre: 'Cloudflare Workers AI', env: 'CLOUDFLARE_API_TOKEN', alias: ['cloudflare'],
    nota: 'Requiere API token + Account ID (endpoint compatible OpenAI)',
    extra: { id: 'cloudflare_account', label: 'Account ID', env: 'CLOUDFLARE_ACCOUNT_ID', placeholder: 'Pega tu Account ID de Cloudflare…' },
  },
];

/* ---------------- utilidades ---------------- */

function aPorcentaje(v: unknown): number {
  const n = typeof v === 'string' ? parseFloat(v) : typeof v === 'number' ? v : NaN;
  if (Number.isNaN(n)) return 0;
  return n > 1 ? Math.min(100, n) : Math.max(0, Math.min(100, n * 100));
}

async function copiar(texto: string, etiqueta: string) {
  try {
    await navigator.clipboard.writeText(texto);
    Toast.exito('Copiado', etiqueta);
  } catch {
    Toast.error('No se pudo copiar', 'Selecciona el texto manualmente.');
  }
}

/* ---------------- paso 1: giro ---------------- */

function PasoGiro({
  verticalId, giroPersonalizado, onElegir,
}: {
  verticalId: string;
  giroPersonalizado: string;
  onElegir: (id: string, personalizado?: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">¿A qué se dedica tu empresa?</h2>
        <p className="text-sm text-muted-foreground">
          El giro precarga el campo <code>vertical.id</code> del perfil y ajusta los valores
          por defecto que el sistema derivará después.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {GIROS.map((g) => {
          const activo = verticalId === g.id;
          return (
            <button
              key={g.id}
              type="button"
              onClick={() => onElegir(g.id, g.id === 'personalizado' ? giroPersonalizado : undefined)}
              aria-pressed={activo}
              className={`rounded-lg border p-4 text-left transition-colors hover:border-primary/60 hover:bg-muted/50 ${
                activo ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border bg-card'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-2xl" aria-hidden>{g.icono}</span>
                {activo && <Badge variant="default">Elegido</Badge>}
              </div>
              <p className="mt-2 font-semibold">{g.nombre}</p>
              <p className="mt-1 text-sm text-muted-foreground">{g.descripcion}</p>
              {g.id === 'personalizado' && activo && (
                <Input
                  className="mt-3"
                  placeholder="Ej: florerías, refaccionarias…"
                  value={giroPersonalizado}
                  onChange={(e) => onElegir('personalizado', e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  aria-label="Describe tu giro"
                />
              )}
            </button>
          );
        })}
      </div>
      {verticalId === '' && (
        <Alert>
          <AlertDescription>Elige un giro para continuar al siguiente paso.</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

/* ---------------- checklist de completitud ---------------- */

function Checklist({ resultado }: { resultado: PerfilParseResult }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Completitud del perfil</CardTitle>
        <CardDescription>Se actualiza mientras escribes.</CardDescription>
      </CardHeader>
      <CardContent>
        {resultado.error ? (
          <Alert variant="destructive">
            <AlertTitle>El bloque estructurado tiene un problema</AlertTitle>
            <AlertDescription>{resultado.error}</AlertDescription>
          </Alert>
        ) : (
          <ul className="space-y-2">
            {resultado.checks.map((c) => (
              <li key={c.id} className="flex items-center gap-2 text-sm">
                <span
                  aria-hidden
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold ${
                    c.ok ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {c.ok ? '✓' : '✗'}
                </span>
                <span className={c.ok ? 'font-medium' : 'text-muted-foreground'}>{c.label}</span>
              </li>
            ))}
          </ul>
        )}
        <Separator className="my-3" />
        <p className="text-xs text-muted-foreground">
          Marca con <code>[PENDIENTE]</code> lo que aún no sepas; podrás activar la configuración
          de todos modos y completarla después.
        </p>
      </CardContent>
    </Card>
  );
}

/* ---------------- diálogo "Llenar con IA" ---------------- */

function DialogoLlenarIA({
  abierto, onCerrar, onListo,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onListo: (markdown: string, pendientes: string[]) => void;
}) {
  const [tab, setTab] = React.useState('url');
  const [url, setUrl] = React.useState('');
  const [texto, setTexto] = React.useState('');
  const [archivo, setArchivo] = React.useState<{ nombre: string; contenido: string } | null>(null);
  const [cargando, setCargando] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const leerArchivo = (f: File | undefined) => {
    setArchivo(null);
    if (!f) return;
    const lector = new FileReader();
    lector.onload = () => setArchivo({ nombre: f.name, contenido: String(lector.result ?? '') });
    lector.onerror = () => setError('No se pudo leer el archivo.');
    lector.readAsText(f);
  };

  const enviar = async () => {
    setError(null);
    const payload =
      tab === 'url'
        ? { url: url.trim() }
        : tab === 'texto'
          ? { text: texto.trim() }
          : { text: archivo?.contenido ?? '', filename: archivo?.nombre };
    if (tab === 'url' && !url.trim()) { setError('Pega la URL del sitio de tu empresa.'); return; }
    if (tab === 'texto' && !texto.trim()) { setError('Pega algún texto sobre tu empresa (presentación, folleto, “quiénes somos”…).'); return; }
    if (tab === 'archivo' && !archivo) { setError('Elige un archivo .md o .txt.'); return; }
    setCargando(true);
    try {
      const res = await postAiFillProfile(payload);
      onListo(res.markdown, res.pendientes ?? []);
      onCerrar();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 501 || e.status === 404)) {
        setError('La IA interna no está disponible todavía (el backend no expone /ai/fill-profile o no hay provider configurado). Llena la plantilla manualmente.');
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setCargando(false);
    }
  };

  return (
    <Dialog open={abierto} onOpenChange={(v) => { if (!v) onCerrar(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Llenar el perfil con IA</DialogTitle>
          <DialogDescription>
            La IA lee tus materiales y propone el perfil lleno. Revisa el resultado: lo que no
            encuentre lo marca como <code>[PENDIENTE]</code>.
          </DialogDescription>
        </DialogHeader>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="url">Pegar URL</TabsTrigger>
            <TabsTrigger value="texto">Pegar texto</TabsTrigger>
            <TabsTrigger value="archivo">Subir archivo</TabsTrigger>
          </TabsList>
          <TabsContent value="url" className="space-y-2 pt-2">
            <Label htmlFor="ia-url">Sitio web de la empresa</Label>
            <Input id="ia-url" placeholder="https://miempresa.mx" value={url} onChange={(e) => setUrl(e.target.value)} />
          </TabsContent>
          <TabsContent value="texto" className="space-y-2 pt-2">
            <Label htmlFor="ia-texto">Texto sobre tu empresa</Label>
            <Textarea id="ia-texto" rows={6} placeholder="Pega aquí tu presentación, folleto o sección “quiénes somos”…" value={texto} onChange={(e) => setTexto(e.target.value)} />
          </TabsContent>
          <TabsContent value="archivo" className="space-y-2 pt-2">
            <Label htmlFor="ia-archivo">Archivo .md o .txt</Label>
            <Input id="ia-archivo" type="file" accept=".md,.txt,.markdown,text/plain" onChange={(e) => leerArchivo(e.target.files?.[0])} />
            {archivo && <p className="text-xs text-muted-foreground">✓ {archivo.nombre} ({(archivo.contenido.length / 1024).toFixed(1)} KB leídos)</p>}
          </TabsContent>
        </Tabs>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCerrar} disabled={cargando}>Cancelar</Button>
          <Button onClick={enviar} disabled={cargando}>
            {cargando ? <><Spinner className="mr-2" size={16} /> Llenando…</> : 'Llenar con IA'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------- paso 2: perfil ---------------- */

function PasoPerfil({
  markdown, onCambiar, onPreviewGenerado,
}: {
  markdown: string;
  onCambiar: (md: string) => void;
  onPreviewGenerado: (cfg: VerticalConfig) => void;
}) {
  const [dialogoIA, setDialogoIA] = React.useState(false);
  const [pendientesIA, setPendientesIA] = React.useState<string[] | null>(null);
  const [derivando, setDerivando] = React.useState(false);
  const [previewOk, setPreviewOk] = React.useState(false);
  const resultado = React.useMemo(() => parseFrontmatter(markdown), [markdown]);

  const generarPreview = async () => {
    if (!markdown.trim()) {
      Toast.aviso('El editor está vacío', 'Carga la plantilla o el ejemplo primero.');
      return;
    }
    setDerivando(true);
    try {
      const cfg = await deriveCompanyConfig(markdown);
      onPreviewGenerado(cfg);
      setPreviewOk(true);
      Toast.exito('Vista previa lista', 'Revisa el resultado en el paso 4 · Resumen.');
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
        Toast.error('Vista previa no disponible', 'El backend aún no expone /company/profile/derive.');
      } else {
        Toast.error('No se pudo generar la vista previa', errorMessage(e));
      }
    } finally {
      setDerivando(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Perfil de tu empresa</h2>
          <p className="text-sm text-muted-foreground">
            Edita el bloque estructurado (YAML) de arriba; el cuerpo en markdown es el detalle para humanos.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => { onCambiar(PERFIL_TEMPLATE); setPendientesIA(null); setPreviewOk(false); }}>
            Cargar plantilla
          </Button>
          <Button variant="outline" size="sm" onClick={() => { onCambiar(PERFIL_EJEMPLO_GIMNASIOS); setPendientesIA(null); setPreviewOk(false); }}>
            Cargar ejemplo gimnasios
          </Button>
          <Button variant="outline" size="sm" onClick={() => setDialogoIA(true)}>
            ✨ Llenar con IA
          </Button>
        </div>
      </div>

      {pendientesIA && pendientesIA.length > 0 && (
        <Alert>
          <AlertTitle>La IA dejó estos puntos pendientes</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5 text-sm">
              {pendientesIA.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <Textarea
          value={markdown}
          onChange={(e) => { onCambiar(e.target.value); setPreviewOk(false); }}
          rows={28}
          spellCheck={false}
          className="font-mono text-[13px] leading-relaxed"
          placeholder="Carga la plantilla o pega aquí el perfil de tu empresa…"
          aria-label="Editor del perfil de empresa"
        />
        <Checklist resultado={resultado} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={generarPreview} disabled={derivando || !markdown.trim()}>
          {derivando ? <><Spinner className="mr-2" size={16} /> Derivando…</> : 'Vista previa de configuración'}
        </Button>
        {previewOk && <Badge variant="accent">✓ Vista previa generada — ver paso 4</Badge>}
        <p className="text-xs text-muted-foreground">
          La vista previa calcula la configuración operativa sin guardar nada todavía.
        </p>
      </div>

      <DialogoLlenarIA
        abierto={dialogoIA}
        onCerrar={() => setDialogoIA(false)}
        onListo={(md, pendientes) => {
          onCambiar(md);
          setPendientesIA(pendientes);
          setPreviewOk(false);
          Toast.exito('Perfil llenado por la IA', pendientes.length > 0 ? `Quedaron ${pendientes.length} puntos pendientes.` : 'Sin puntos pendientes.');
        }}
      />
    </div>
  );
}

/* ---------------- paso 3: API keys ---------------- */

function PasoIA() {
  const [keys, setKeys] = React.useState<Record<string, string>>({});
  const [estado, setEstado] = React.useState<Record<string, boolean | null>>({});
  const [probando, setProbando] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [dialogoEnv, setDialogoEnv] = React.useState(false);

  const probar = async () => {
    setProbando(true);
    setError(null);
    try {
      const st = await getAiStatus();
      const mapa: Record<string, boolean | null> = {};
      for (const p of AI_PROVIDERS) {
        const hit = (st.providers ?? []).find((pr) =>
          p.alias.some((a) => pr.name.toLowerCase().includes(a)),
        );
        mapa[p.id] = hit ? !!hit.configured : null;
      }
      setEstado(mapa);
      Toast.exito('Estado consultado', 'Revisa qué providers están configurados.');
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
        setError('El backend aún no expone /ai/status. Podrás probar los providers cuando el módulo de IA interna esté activo.');
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setProbando(false);
    }
  };

  const lineasEnv = AI_PROVIDERS.flatMap((p) => {
    const lineas: string[] = [];
    if (keys[p.id]?.trim()) lineas.push(`${p.env}=${keys[p.id].trim()}`);
    if (p.extra && keys[p.extra.id]?.trim()) lineas.push(`${p.extra.env}=${keys[p.extra.id].trim()}`);
    return lineas;
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">IA interna (opcional)</h2>
        <p className="text-sm text-muted-foreground">
          Conecta un provider para el asistente y el llenado automático del perfil.
          Puedes saltar este paso y configurarlo después.
        </p>
      </div>

      <Alert>
        <AlertDescription>
          Las keys se guardan en el <code>.env</code> del servidor: nunca se muestran completas
          ni viajan al navegador. Este panel <strong>no puede escribir el .env por ti</strong>;
          el botón «Generar líneas para .env» te da el texto exacto para pegarlo en el servidor.
        </AlertDescription>
      </Alert>

      <div className="grid gap-3 md:grid-cols-2">
        {AI_PROVIDERS.map((p) => {
          const cfg = estado[p.id];
          const extra = p.extra;
          return (
            <Card key={p.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{p.nombre}</CardTitle>
                  {cfg === true && <Badge variant="accent">✓ Configurado</Badge>}
                  {cfg === false && <Badge variant="outline">No configurado</Badge>}
                </div>
                <CardDescription className="font-mono text-xs">{p.env}</CardDescription>
              </CardHeader>
              <CardContent>
                <Label htmlFor={`key-${p.id}`} className="sr-only">API key de {p.nombre}</Label>
                <Input
                  id={`key-${p.id}`}
                  type="password"
                  autoComplete="off"
                  placeholder="Pega aquí tu API key…"
                  value={keys[p.id] ?? ''}
                  onChange={(e) => setKeys((k) => ({ ...k, [p.id]: e.target.value }))}
                />
                {extra && (
                  <div className="mt-2">
                    <Label htmlFor={`key-${extra.id}`}>{extra.label}</Label>
                    <Input
                      id={`key-${extra.id}`}
                      type="text"
                      autoComplete="off"
                      placeholder={extra.placeholder}
                      value={keys[extra.id] ?? ''}
                      onChange={(e) => setKeys((k) => ({ ...k, [extra.id]: e.target.value }))}
                    />
                  </div>
                )}
                {p.nota && (
                  <p className="mt-2 text-xs text-muted-foreground">{p.nota}</p>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  La key solo se usa para generar las líneas del .env; no se envía al servidor desde aquí.
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={probar} disabled={probando}>
          {probando ? <><Spinner className="mr-2" size={16} /> Probando…</> : 'Probar providers'}
        </Button>
        <Button onClick={() => setDialogoEnv(true)} disabled={lineasEnv.length === 0}>
          Generar líneas para .env
        </Button>
      </div>

      <Dialog open={dialogoEnv} onOpenChange={setDialogoEnv}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Líneas para el .env del servidor</DialogTitle>
            <DialogDescription>
              Pega estas líneas en el <code>.env</code> junto al <code>docker-compose.yml</code> del
              backend y reinicia el servicio de la API. No las compartas por chat ni correo.
            </DialogDescription>
          </DialogHeader>
          <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
            {lineasEnv.join('\n')}
          </pre>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogoEnv(false)}>Cerrar</Button>
            <Button onClick={() => copiar(lineasEnv.join('\n'), 'Líneas del .env copiadas.')}>Copiar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- paso 4: resumen ---------------- */

function Barra({ etiqueta, valor }: { etiqueta: string; valor: number }) {
  const pct = aPorcentaje(valor);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{etiqueta}</span>
        <span className="text-muted-foreground">{pct.toFixed(0)}%</span>
      </div>
      <Progress value={pct} />
    </div>
  );
}

function PasoResumen({
  preview, cargando, error, onReintentar,
  faltantes, versiones, onActivarVersion,
}: {
  preview: VerticalConfig | null;
  cargando: boolean;
  error: string | null;
  onReintentar: () => void;
  faltantes: string[];
  versiones: CompanyProfileSummary[];
  onActivarVersion: (id: string) => void;
}) {
  if (cargando) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (error || !preview) {
    return (
      <Alert variant="destructive">
        <AlertTitle>No se pudo generar la configuración</AlertTitle>
        <AlertDescription>
          <p className="mb-2">{error ?? 'Sin datos para mostrar.'}</p>
          <Button variant="outline" size="sm" onClick={onReintentar}>Reintentar</Button>
        </AlertDescription>
      </Alert>
    );
  }
  const pesos = Object.entries(preview.scoring_weights ?? {});
  const demandas = Object.entries(preview.demand_intensity ?? {});
  const tam = preview.tam_defaults ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Resumen de la configuración</h2>
        <p className="text-sm text-muted-foreground">
          Esto es lo que el sistema usará para puntuar, reportar y aprender. Revísalo antes de activar.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {preview.nombre_empresa && <Badge variant="default" className="text-sm">{preview.nombre_empresa}</Badge>}
        <Badge variant="outline">vertical: {preview.vertical_id}</Badge>
      </div>

      {faltantes.length > 0 && (
        <Alert>
          <AlertTitle>Faltan datos en tu perfil</AlertTitle>
          <AlertDescription>
            <p className="mb-1">Puedes activar de todos modos y completarlos después:</p>
            <ul className="list-disc pl-5 text-sm">
              {faltantes.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Códigos SCIAN objetivo</CardTitle></CardHeader>
          <CardContent>
            {preview.scian_targets.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {preview.scian_targets.map((s) => <Badge key={s} variant="secondary" className="font-mono">{s}</Badge>)}
              </div>
            ) : <p className="text-sm text-muted-foreground">Sin códigos sugeridos.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Canales de contacto</CardTitle></CardHeader>
          <CardContent>
            {preview.outreach_channels.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {preview.outreach_channels.map((c) => <Badge key={c} variant="outline">{c}</Badge>)}
              </div>
            ) : <p className="text-sm text-muted-foreground">Sin canales definidos.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Intensidad de demanda</CardTitle>
            <CardDescription>Ponderación por segmento o zona.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {demandas.length > 0
              ? demandas.map(([k, v]) => <Barra key={k} etiqueta={k} valor={v} />)
              : <p className="text-sm text-muted-foreground">Sin datos.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pesos del scoring</CardTitle>
            <CardDescription>Los {pesos.length} componentes del puntaje de leads.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {pesos.length > 0
              ? pesos.map(([k, v]) => <Barra key={k} etiqueta={k} valor={v} />)
              : <p className="text-sm text-muted-foreground">Sin datos.</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ticket y ciclo por producto</CardTitle>
        </CardHeader>
        <CardContent>
          {tam.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Producto</TableHead>
                  <TableHead>Ticket (MXN)</TableHead>
                  <TableHead>Ciclo (días)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tam.map((t, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{String(t.producto ?? t.nombre ?? `Producto ${i + 1}`)}</TableCell>
                    <TableCell className="font-mono text-sm">
                      {t.ticket_min_mxn ?? '—'} – {t.ticket_max_mxn ?? '—'}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{t.ciclo_venta_dias ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : <p className="text-sm text-muted-foreground">Sin productos en la configuración derivada.</p>}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Palabras clave del cliente ideal</CardTitle></CardHeader>
          <CardContent>
            {preview.icp_keywords.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {preview.icp_keywords.map((k) => <Badge key={k} variant="secondary">{k}</Badge>)}
              </div>
            ) : <p className="text-sm text-muted-foreground">Sin palabras clave.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Vocabulario del negocio</CardTitle></CardHeader>
          <CardContent>
            {Object.keys(preview.vocabulary ?? {}).length > 0 ? (
              <dl className="space-y-1 text-sm">
                {Object.entries(preview.vocabulary).map(([t, s]) => (
                  <div key={t} className="flex gap-2">
                    <dt className="font-semibold">{t}:</dt>
                    <dd className="text-muted-foreground">{s}</dd>
                  </div>
                ))}
              </dl>
            ) : <p className="text-sm text-muted-foreground">Sin vocabulario definido.</p>}
          </CardContent>
        </Card>
      </div>

      {preview.line_rules.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Reglas de línea</CardTitle></CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {preview.line_rules.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </CardContent>
        </Card>
      )}

      {versiones.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Versiones anteriores</CardTitle>
            <CardDescription>Puedes volver a activar una versión previa.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {versiones.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2 text-sm">
                  <span>
                    <span className="font-medium">v{v.version}</span>
                    <span className="text-muted-foreground"> · {v.nombre ?? 'Sin nombre'}</span>
                    {v.is_active && <Badge variant="accent" className="ml-2">Activa</Badge>}
                  </span>
                  {!v.is_active && (
                    <Button variant="outline" size="sm" onClick={() => onActivarVersion(v.id)}>
                      Activar
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ---------------- wizard principal ---------------- */

export default function Configuracion() {
  const navigate = useNavigate();
  const [paso, setPaso] = React.useState(0);
  const [verticalId, setVerticalId] = React.useState('');
  const [giroPersonalizado, setGiroPersonalizado] = React.useState('');
  const [markdown, setMarkdown] = React.useState('');
  const [preview, setPreview] = React.useState<VerticalConfig | null>(null);
  const [previewCargando, setPreviewCargando] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [perfilExistente, setPerfilExistente] = React.useState<string | null>(null);
  const [versiones, setVersiones] = React.useState<CompanyProfileSummary[]>([]);
  const [guardando, setGuardando] = React.useState(false);
  const [confirmarFaltantes, setConfirmarFaltantes] = React.useState(false);

  // Si ya hay perfil activo, avisarlo y precargarlo en el editor.
  React.useEffect(() => {
    getCompanyProfile()
      .then((p) => {
        setPerfilExistente(`Ya existe un perfil activo (v${p.version}${p.nombre ? ` · ${p.nombre}` : ''}). Guardar aquí creará una nueva versión.`);
        if (p.markdown) setMarkdown(p.markdown);
      })
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 404)) {
          // Otro error (p. ej. backend sin el módulo): no bloquea el wizard.
        }
      });
    listCompanyProfiles().then(setVersiones).catch(() => { /* el módulo puede no existir aún */ });
  }, []);

  const elegirGiro = (id: string, personalizado?: string) => {
    setVerticalId(id);
    if (personalizado !== undefined) setGiroPersonalizado(personalizado);
    setMarkdown((md) => precargarVertical(md.trim() === '' ? PERFIL_TEMPLATE : md, id));
    setPreview(null);
    setPreviewError(null);
  };

  const generarPreview = React.useCallback(async () => {
    if (!markdown.trim()) return;
    setPreviewCargando(true);
    setPreviewError(null);
    try {
      const cfg = await deriveCompanyConfig(markdown);
      setPreview(cfg);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
        setPreviewError('El backend aún no expone /company/profile/derive (módulo en construcción).');
      } else {
        setPreviewError(errorMessage(e));
      }
    } finally {
      setPreviewCargando(false);
    }
  }, [markdown]);

  // Al entrar al paso 4, genera la vista previa si aún no existe.
  React.useEffect(() => {
    if (paso === 3 && !preview && !previewCargando && !previewError) generarPreview();
  }, [paso, preview, previewCargando, previewError, generarPreview]);

  const faltantes = React.useMemo(() => parseFrontmatter(markdown).faltantes, [markdown]);

  const puedeContinuar = () => {
    if (paso === 0) return verticalId !== '';
    if (paso === 1) return markdown.trim() !== '';
    return true;
  };

  const guardarYActivar = async () => {
    setGuardando(true);
    try {
      const res = await putCompanyProfile(markdown);
      const pendientes = res.faltantes ?? [];
      if (pendientes.length > 0) {
        Toast.aviso('Configuración activada con pendientes', `${pendientes.length} campos por completar.`);
      } else {
        Toast.exito('Configuración guardada y activada', `Versión ${res.version} del perfil.`);
      }
      navigate('/');
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
        Toast.error('No se pudo guardar', 'El backend aún no expone /company/profile (módulo en construcción).');
      } else {
        Toast.error('No se pudo guardar', errorMessage(e));
      }
    } finally {
      setGuardando(false);
      setConfirmarFaltantes(false);
    }
  };

  const activarVersion = async (id: string) => {
    try {
      await activateCompanyProfile(id);
      Toast.exito('Versión activada');
      listCompanyProfiles().then(setVersiones).catch(() => undefined);
    } catch (e) {
      Toast.error('No se pudo activar la versión', errorMessage(e));
    }
  };

  const iniciarGuardado = () => {
    if (faltantes.length > 0) setConfirmarFaltantes(true);
    else guardarYActivar();
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Configuración" subtitulo="Configuración inicial del ecosistema: tu empresa y la IA interna" />
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <Card>
            <CardContent className="pt-6">
              <Stepper steps={PASOS} current={paso} onStepClick={(i) => i < paso && setPaso(i)} />
              <div className="mt-2">
                <StepperMobileLabel steps={PASOS} current={paso} />
              </div>
            </CardContent>
          </Card>

          {perfilExistente && (
            <Alert>
              <AlertDescription>{perfilExistente}</AlertDescription>
            </Alert>
          )}

          {paso === 0 && (
            <PasoGiro verticalId={verticalId} giroPersonalizado={giroPersonalizado} onElegir={elegirGiro} />
          )}
          {paso === 1 && (
            <PasoPerfil
              markdown={markdown}
              onCambiar={setMarkdown}
              onPreviewGenerado={(cfg) => setPreview(cfg)}
            />
          )}
          {paso === 2 && <PasoIA />}
          {paso === 3 && (
            <PasoResumen
              preview={preview}
              cargando={previewCargando}
              error={previewError}
              onReintentar={generarPreview}
              faltantes={faltantes}
              versiones={versiones}
              onActivarVersion={activarVersion}
            />
          )}

          <div className="flex items-center justify-between gap-2 pb-4">
            <Button variant="outline" onClick={() => setPaso((p) => Math.max(0, p - 1))} disabled={paso === 0}>
              ← Atrás
            </Button>
            {paso < 3 ? (
              <Button onClick={() => setPaso((p) => Math.min(3, p + 1))} disabled={!puedeContinuar()}>
                Continuar →
              </Button>
            ) : (
              <Button onClick={iniciarGuardado} disabled={guardando || !markdown.trim()}>
                {guardando ? <><Spinner className="mr-2" size={16} /> Guardando…</> : 'Guardar y activar configuración'}
              </Button>
            )}
          </div>
        </div>
      </div>

      <AlertDialog open={confirmarFaltantes} onOpenChange={setConfirmarFaltantes}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Activar con datos pendientes</AlertDialogTitle>
            <AlertDialogDescription>
              Tu perfil aún tiene campos sin completar:
              <ul className="mt-2 list-disc pl-5">
                {faltantes.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
              El sistema funcionará con valores parciales. ¿Activar de todos modos?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={guardando}>Volver a revisar</AlertDialogCancel>
            <AlertDialogAction onClick={guardarYActivar} disabled={guardando}>
              {guardando ? 'Guardando…' : 'Activar de todos modos'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
