import * as React from 'react';
import { Button } from '@/components/ui/Button';

const CLAVE = 'geis-theme';

/** Lee el tema guardado o la preferencia del sistema. */
export function temaInicial(): 'dark' | 'light' {
  try {
    const g = localStorage.getItem(CLAVE);
    if (g === 'dark' || g === 'light') return g;
  } catch { /* sin localStorage */ }
  return 'light';
}

/** Aplica el tema al <html> (Tailwind darkMode: 'class') y lo persiste. */
export function aplicarTema(t: 'dark' | 'light') {
  document.documentElement.classList.toggle('dark', t === 'dark');
  try { localStorage.setItem(CLAVE, t); } catch { /* sin localStorage */ }
}

export function ThemeToggle() {
  const [tema, setTema] = React.useState<'dark' | 'light'>(temaInicial);

  React.useEffect(() => { aplicarTema(tema); }, [tema]);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTema((t) => (t === 'dark' ? 'light' : 'dark'))}
      title={tema === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      aria-label={tema === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
    >
      {tema === 'dark' ? '☀️' : '🌙'}
    </Button>
  );
}
