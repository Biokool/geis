import { Badge } from './Badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';

/**
 * Sello de honestidad: marca cifras que vienen de un modelo (ISM, Huff,
 * TAM, movilidad/proxy) en vez de una medición observada.
 * El backend lo exige en el SRS: «estimado vs observado».
 */
export function EstimadoBadge({ texto = 'Estimado' }: { texto?: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="outline" className="cursor-help border-dashed border-warning/60 text-warning">
            ≈ {texto}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-semibold">Cifra estimada, no observada</p>
          <p className="mt-1">
            Proviene de un modelo (ISM, Huff, TAM o proxy de movilidad), no de una medición
            directa. Úsala para comparar zonas, no como proyección de ventas.
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
