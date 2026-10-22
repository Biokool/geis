import { toast } from 'sonner';

/** API de toasts en español sobre sonner (SRS §6.1: toasts para jobs async). */
export const Toast = {
  exito: (mensaje: string, descripcion?: string) => toast.success(mensaje, { description: descripcion }),
  error: (mensaje: string, descripcion?: string) => toast.error(mensaje, { description: descripcion }),
  aviso: (mensaje: string, descripcion?: string) => toast.warning(mensaje, { description: descripcion }),
  info: (mensaje: string, descripcion?: string) => toast.info(mensaje, { description: descripcion }),
  cargando: (mensaje: string) => toast.loading(mensaje),
  cerrar: (id?: string | number) => toast.dismiss(id),
};

export { toast };
