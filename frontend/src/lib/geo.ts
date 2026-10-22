/** Utilidades geoespaciales ligeras (sin turf). */

/** Color del pin por estrato DENUE (SRS §6.2: leyenda de estratos). */
export function estratoColor(estrato?: string): string {
  const e = (estrato ?? '').toLowerCase();
  if (e.includes('251')) return '#D64545'; // grande / rojo
  if (e.includes('101')) return '#E8590C';
  if (e.includes('51')) return '#E8A13D';
  if (e.includes('31') || e.includes('11')) return '#00B39B';
  return '#8a93a6'; // micro / gris
}

/** Radio del pin por estrato. */
export function estratoRadio(estrato?: string): number {
  const e = (estrato ?? '').toLowerCase();
  if (e.includes('251')) return 9;
  if (e.includes('101')) return 7;
  if (e.includes('51')) return 6;
  if (e.includes('31') || e.includes('11')) return 5;
  return 4;
}

/** Área aproximada (km²) de un polígono GeoJSON con fórmula esférica (anillo exterior). */
export function areaKm2(geojson: GeoJSON.Polygon | GeoJSON.MultiPolygon): number {
  const R = 6371; // km
  const ringArea = (coords: number[][]): number => {
    let total = 0;
    for (let i = 0; i < coords.length - 1; i++) {
      const [lon1, lat1] = coords[i];
      const [lon2, lat2] = coords[i + 1];
      const p1 = (lon2 - lon1) * (Math.PI / 180);
      total += p1 * (2 + Math.sin((lat1 * Math.PI) / 180) + Math.sin((lat2 * Math.PI) / 180));
    }
    return Math.abs((total * R * R) / 2);
  };
  if (geojson.type === 'Polygon') return ringArea(geojson.coordinates[0]);
  return geojson.coordinates.reduce((acc, poly) => acc + ringArea(poly[0]), 0);
}

export function verdictColor(veredicto?: string): string {
  const v = (veredicto ?? '').toUpperCase();
  if (v.includes('AVANZAR')) return '#2F9E44';
  if (v.includes('NEGOCIAR')) return '#E8A13D';
  if (v.includes('EXPLORAR')) return '#D64545';
  return '#8a93a6';
}

export function downloadBlob(data: BlobPart, filename: string, mime = 'application/octet-stream'): void {
  const blob = data instanceof Blob ? data : new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
