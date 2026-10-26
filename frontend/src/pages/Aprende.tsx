import * as React from 'react';
import { useLocation } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

interface Explicador {
  ancla: string;
  titulo: string;
  icono: string;
  queEs: string;
  comoCalcula: string;
  comoUsarlo: string;
}

const EXPLICADORES: Explicador[] = [
  {
    ancla: 'competencia',
    titulo: 'Competencia en la zona',
    icono: '🥊',
    queEs:
      'Son los negocios de tu misma clase SCIAN (tu giro exacto) que ya operan dentro de los radios de análisis de 1 km y 2 km. La lista los ordena por cercanía y marca «PARECE ACTIVO» según el registro vigente del DENUE; el conteo «del anillo exterior» es solo la franja entre 1 y 2 km, no el acumulado.',
    comoCalcula:
      'GEIS consulta el DENUE (INEGI) con distancia geográfica real (PostGIS) sobre el punto analizado y resume la presión competitiva con el ISM = población objetivo ÷ (competidores + 1): un ISM alto indica demanda poco atendida («océano azul»); uno bajo, saturación («océano rojo»).',
    comoUsarlo:
      'Si los competidores cercanos son pocos y el ISM es alto, la zona está desatendida. Si hay varios a menos de 500 m, necesitas una diferenciación clara (precio, horario, especialidad) o moverte unas cuadras: revisa el mapa numerado y visita en Maps a los 3 más cercanos antes de firmar.',
  },
  {
    ancla: 'movimiento',
    titulo: 'Movimiento y acceso (movilidad estimada)',
    icono: '🚗',
    queEs:
      'Es el flujo estimado de vehículos y personas que pasan cerca del punto, más las vialidades principales que lo alimentan. Siempre se presenta como rango con nivel de 0 a 100 y con la etiqueta «estimado»: es un modelo, no un conteo con sensores.',
    comoCalcula:
      'Con las vialidades de OpenStreetMap (vía Overpass) se suma el flujo típico por jerarquía de vía (troncal, primaria, secundaria), atenuado por distancia. El flujo peatonal combina la población a ~500 m, el empleo residente cercano (PEA) y el número de atractores, con un rango de ±30 % (proxy §3.10 del SRS).',
    comoUsarlo:
      'Un nivel vehicular alto sirve para negocios de paso y visibilidad (rótulo, acceso en auto, estacionamiento). Un nivel peatonal alto es el que vende en giros de impulso y comida al paso. Compara el nivel entre tus ubicaciones candidatas en el Comparador: es una cifra relativa, úsala para ordenar opciones, no como promesa de ventas.',
  },
  {
    ancla: 'poblacion',
    titulo: 'Población de la zona',
    icono: '👥',
    queEs:
      'Es la gente que vive dentro del radio de análisis, desagregada por edad (0–14, 15–29, 30–59, 60+) y sexo, junto con los hogares: viviendas habitadas, personas por vivienda y equipamiento (internet, computadora, automóvil). Es población residente observada en el censo, no una estimación de compradores.',
    comoCalcula:
      'GEIS suma las AGEB del Censo 2020 (INEGI) que intersectan el radio mayor del análisis. El «segmento objetivo» del reporte es el grupo 30–59 años, que alimenta la demanda D del ISM y el TAM; los porcentajes de cada tarjeta son sobre la población total de la zona.',
    comoUsarlo:
      'Cruza el segmento dominante con tu cliente ideal: una zona joven (15–29) favorece formatos rápidos y digitales; una de 30–59 con hogares equipados sostiene tickets medios y recurrencia. Si tu giro depende de familias, mira personas por vivienda y % con automóvil antes que la población bruta.',
  },
  {
    ancla: 'actividad',
    titulo: 'Actividad económica',
    icono: '💼',
    queEs:
      'Es la PEA ocupada: las personas económicamente activas que ya tienen ocupación y viven en la zona, expresada también como porcentaje de la población de 15 años y más. Ojo: mide empleo de los residentes, no los empleos generados dentro de la zona.',
    comoCalcula:
      'Se suma el campo de población ocupada de las mismas AGEB censales (INEGI, Censo 2020) del radio de análisis y se divide entre la población de 15 años y más del mismo radio.',
    comoUsarlo:
      'Un porcentaje alto indica una zona con ingresos circulando a diario: sostiene consumo entre semana y tickets recurrentes. Combínalo con el NSE detectado (perfil de gasto, referencia AMAI 2024) para estimar si el ticket de tu giro cabe en el bolsillo local antes de comprometerte con una renta.',
  },
];

export default function Aprende() {
  const { hash } = useLocation();

  React.useEffect(() => {
    if (!hash) return;
    const t = window.setTimeout(() => {
      document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 60);
    return () => window.clearTimeout(t);
  }, [hash]);

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Aprende" subtitulo="Qué significa cada bloque del reporte, cómo lo calcula GEIS y cómo usarlo para decidir" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex flex-wrap gap-2">
            {EXPLICADORES.map((e) => (
              <a key={e.ancla} href={`#${e.ancla}`}>
                <Badge variant="outline" className="cursor-pointer px-3 py-1.5 text-sm">{e.icono} {e.titulo}</Badge>
              </a>
            ))}
          </div>
          {EXPLICADORES.map((e) => (
            <Card key={e.ancla} id={e.ancla} className="scroll-mt-6">
              <CardHeader>
                <CardTitle><span aria-hidden className="mr-2">{e.icono}</span>{e.titulo}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm leading-relaxed">
                <div>
                  <p className="mb-1 font-semibold">Qué es</p>
                  <p className="text-muted-foreground">{e.queEs}</p>
                </div>
                <div>
                  <p className="mb-1 font-semibold">Cómo lo calcula GEIS</p>
                  <p className="text-muted-foreground">{e.comoCalcula}</p>
                </div>
                <div>
                  <p className="mb-1 font-semibold">Cómo usarlo para decidir</p>
                  <p className="text-muted-foreground">{e.comoUsarlo}</p>
                </div>
              </CardContent>
            </Card>
          ))}
          <p className="text-xs text-muted-foreground">
            Regla de la casa: lo observado (censo, DENUE) se presenta como dato; lo modelado (movilidad, TAM, ISM) siempre lleva la etiqueta «estimado» y su método. Si un dato no existe, el reporte lo declara en lugar de inventarlo.
          </p>
        </div>
      </div>
    </div>
  );
}
