import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Marco de mapa con botón «Pantalla completa».
 *
 * Usa la Fullscreen API sobre el propio contenedor, así **lo que esté dentro
 * se mantiene visible al ampliar**: en Mapa y Reporte el contenedor incluye
 * los filtros/capas, de modo que no se pierden al pasar a pantalla completa.
 * Tras entrar/salir se dispara `resize` para que Leaflet recalcule su tamaño
 * (`invalidateSize` implícito, igual que cuando cambia la ventana).
 */
export function MapaExpandible({
  children,
  className,
  etiqueta = 'Pantalla completa',
  titulo,
}: {
  children: React.ReactNode;
  className?: string;
  etiqueta?: string;
  titulo?: string;
}) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [expandido, setExpandido] = React.useState(false);
  const [soportado, setSoportado] = React.useState(true);

  React.useEffect(() => {
    setSoportado(typeof document !== 'undefined' && !!document.documentElement.requestFullscreen);
    const alCambiar = () => {
      const activo = document.fullscreenElement === ref.current;
      setExpandido(activo);
      // Leaflet escucha window.resize; se lanza tras el reflow del fullscreen.
      window.setTimeout(() => window.dispatchEvent(new Event('resize')), 120);
    };
    document.addEventListener('fullscreenchange', alCambiar);
    return () => document.removeEventListener('fullscreenchange', alCambiar);
  }, []);

  const alternar = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await ref.current?.requestFullscreen();
      }
    } catch {
      /* Navegador/iframe sin permiso: se conserva el mapa normal. */
      setSoportado(false);
    }
  };

  return (
    <div
      ref={ref}
      className={cn('mapa-expandible', className, expandido && 'is-expandido')}
      data-titulo={titulo}
    >
      {children}
      {soportado && (
        <button
          type="button"
          onClick={alternar}
          className="mapa-expandible-btn"
          title={expandido ? 'Salir de pantalla completa (Esc)' : etiqueta}
          aria-label={expandido ? 'Salir de pantalla completa' : etiqueta}
        >
          <span aria-hidden>{expandido ? '✕' : '⛶'}</span>
          <span className="mapa-expandible-btn-texto">{expandido ? 'Salir' : 'Pantalla completa'}</span>
        </button>
      )}
    </div>
  );
}
