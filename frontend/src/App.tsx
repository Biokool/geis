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

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Inicio />} />
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
