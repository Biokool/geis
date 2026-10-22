import { create } from 'zustand';

export interface ActiveTerritory {
  id?: string;
  nombre: string;
  tipo?: string;
  geojson?: GeoJSON.GeoJSON;
  area_km2?: number;
}

interface GeisState {
  territorio: ActiveTerritory | null;
  setTerritorio: (t: ActiveTerritory | null) => void;
  usuario: string;
  setUsuario: (u: string) => void;
  veredictFilter: string | null;
  setVeredictFilter: (v: string | null) => void;
}

export const useGeisStore = create<GeisState>((set) => ({
  territorio: null,
  setTerritorio: (territorio) => set({ territorio }),
  usuario: 'analista',
  setUsuario: (usuario) => set({ usuario }),
  veredictFilter: null,
  setVeredictFilter: (veredictFilter) => set({ veredictFilter }),
}));
