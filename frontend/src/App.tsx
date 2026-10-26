import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import Inicio from '@/pages/Inicio';
import Mapa from '@/pages/Mapa';
import Kpis from '@/pages/Kpis';
import Leads from '@/pages/Leads';
import Reporte from '@/pages/Reporte';
import Comparador from '@/pages/Comparador';
import Historial from '@/pages/Historial';
import Geofencing from '@/pages/Geofencing';
import Exportacion from '@/pages/Exportacion';
import Operacion from '@/pages/Operacion';
import Sistema from '@/pages/Sistema';
import Configuracion from '@/pages/Configuracion';
import Asistente from '@/pages/Asistente';
// Sección 1 · Ubicaciones (los crea el worker de Sección 1)
import Analizar from '@/pages/Analizar';
import Aprende from '@/pages/Aprende';
import ReportePrint from '@/pages/ReportePrint';
import ReporteCompartido from '@/pages/ReporteCompartido';
// Sección 2 · Radar
import PanelRadar from '@/pages/PanelRadar';

export default function App() {
  return (
    <Routes>
      {/* Vistas públicas / imprimibles: FUERA del layout principal (sin sidebar) */}
      <Route path="/reporte/:id/imprimir" element={<ReportePrint />} />
      <Route path="/r/:token" element={<ReporteCompartido />} />
      <Route element={<AppLayout />}>
        <Route index element={<Inicio />} />
        {/* Sección 1 · Ubicaciones */}
        <Route path="/analizar" element={<Analizar />} />
        <Route path="/aprende" element={<Aprende />} />
        {/* Sección 2 · Radar */}
        <Route path="/panel-radar" element={<PanelRadar />} />
        {/* Rutas existentes (compartidas / comunes) */}
        <Route path="/mapa" element={<Mapa />} />
        <Route path="/kpis" element={<Kpis />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/reporte" element={<Reporte />} />
        <Route path="/comparador" element={<Comparador />} />
        <Route path="/historial" element={<Historial />} />
        <Route path="/geofencing" element={<Geofencing />} />
        <Route path="/exportacion" element={<Exportacion />} />
        <Route path="/operacion" element={<Operacion />} />
        <Route path="/sistema" element={<Sistema />} />
        <Route path="/configuracion" element={<Configuracion />} />
        <Route path="/asistente" element={<Asistente />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
