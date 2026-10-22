import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { Topbar } from '@/components/layout/Topbar';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/Alert';
import { Textarea } from '@/components/ui/Textarea';
import { Spinner } from '@/components/ui/Spinner';
import { Skeleton } from '@/components/ui/Skeleton';
import { Message } from '@/components/ui/Message';
import { MessageScroller } from '@/components/ui/MessageScroller';
import { Toast } from '@/components/ui/Toast';
import {
  getAiStatus, postAiChat, errorMessage, ApiError, type AiChatMessage,
} from '@/lib/api';

interface ChatMsg {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  toolsUsed?: string[];
  time: string;
}

const BIENVENIDA: ChatMsg = {
  id: 0,
  role: 'assistant',
  content:
    'Hola, soy el asistente interno de GEIS. Puedo ayudarte con:\n\n' +
    '• **Resumir tu empresa**: qué giro, productos y propuesta de valor tiene configurados.\n' +
    '• **Analizar territorio**: qué zonas convienen según tu vertical y tu cliente ideal.\n' +
    '• **Puntuar un lead**: explicarte por qué un prospecto obtuvo su score.\n' +
    '• **Sugerir códigos SCIAN** para tu giro o tus clientes.\n' +
    '• **Responder dudas** sobre cómo usar cada módulo del ecosistema.\n\n' +
    'Escríbeme abajo. Si aún no configuras tu empresa, hazlo primero en Configuración.',
  time: '',
};

let siguienteId = 1;
const hora = () => new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });

function iaNoDisponible(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 501 || e.status === 404);
}

export default function Asistente() {
  const navigate = useNavigate();
  const [mensajes, setMensajes] = React.useState<ChatMsg[]>([{ ...BIENVENIDA, time: hora() }]);
  const [entrada, setEntrada] = React.useState('');
  const [enviando, setEnviando] = React.useState(false);
  const [verificando, setVerificando] = React.useState(true);
  const [iaConfigurada, setIaConfigurada] = React.useState<boolean | null>(null);
  const [errorEnvio, setErrorEnvio] = React.useState<string | null>(null);

  // Verifica al entrar si la IA está disponible (diseño defensivo ante 404/501).
  React.useEffect(() => {
    getAiStatus()
      .then((st) => {
        const alguno = (st.providers ?? []).some((p) => p.configured);
        setIaConfigurada(alguno);
      })
      .catch((e) => {
        setIaConfigurada(iaNoDisponible(e) ? false : null);
      })
      .finally(() => setVerificando(false));
  }, []);

  const enviar = async () => {
    const texto = entrada.trim();
    if (!texto || enviando) return;
    setEntrada('');
    setErrorEnvio(null);
    const msgUsuario: ChatMsg = { id: siguienteId++, role: 'user', content: texto, time: hora() };
    const historial: AiChatMessage[] = [...mensajes, msgUsuario]
      .filter((m) => m.id !== 0)
      .map((m) => ({ role: m.role, content: m.content }));
    setMensajes((ms) => [...ms, msgUsuario]);
    setEnviando(true);
    try {
      const res = await postAiChat(texto, historial);
      setMensajes((ms) => [
        ...ms,
        { id: siguienteId++, role: 'assistant', content: res.reply, toolsUsed: res.tools_used ?? [], time: hora() },
      ]);
      if ((res.tools_used ?? []).length > 0) setIaConfigurada(true);
    } catch (e) {
      if (iaNoDisponible(e)) {
        setIaConfigurada(false);
        setErrorEnvio(
          'La IA interna no está disponible: el backend no expone /ai/chat o ningún provider está configurado.',
        );
      } else {
        setErrorEnvio(errorMessage(e));
        Toast.error('No se pudo contactar al asistente', errorMessage(e));
      }
    } finally {
      setEnviando(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Topbar titulo="Asistente IA" subtitulo="Operador interno: conoce tu empresa, tu territorio y tus leads" />
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 py-4 md:px-6">
          {verificando ? (
            <div className="space-y-3 py-4">
              <Skeleton className="h-16 w-3/4" />
              <Skeleton className="h-16 w-2/3 self-end" />
            </div>
          ) : iaConfigurada === false ? (
            <Alert className="mb-3">
              <AlertTitle>La IA no está configurada todavía</AlertTitle>
              <AlertDescription>
                <p className="mb-2">
                  Para usar el asistente necesitas: 1) completar el perfil de tu empresa y
                  2) configurar al menos un provider de IA (paso 3).
                </p>
                <Button size="sm" onClick={() => navigate('/configuracion')}>
                  Ir a Configuración →
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          <MessageScroller className="min-h-0 flex-1 rounded-lg border bg-card">
            {mensajes.map((m) => (
              <div key={m.id}>
                <Message
                  from={m.role}
                  author={m.role === 'assistant' ? 'Asistente GEIS' : 'Tú'}
                  time={m.time}
                >
                  <span className="whitespace-pre-line">{m.content}</span>
                </Message>
                {m.role === 'assistant' && m.toolsUsed && m.toolsUsed.length > 0 && (
                  <div className="ml-10 mt-1 flex flex-wrap items-center gap-1">
                    <span className="text-[11px] text-muted-foreground">herramientas usadas:</span>
                    {m.toolsUsed.map((t) => (
                      <Badge key={t} variant="outline" className="font-mono text-[11px]">{t}</Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {enviando && (
              <Message from="assistant" author="Asistente GEIS" time={hora()}>
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Spinner size={16} /> escribiendo…
                </span>
              </Message>
            )}
          </MessageScroller>

          {errorEnvio && !enviando && (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription>{errorEnvio}</AlertDescription>
            </Alert>
          )}

          <div className="mt-3 flex items-end gap-2">
            <Textarea
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Pregunta algo… (Enter para enviar, Shift+Enter para salto de línea)"
              aria-label="Mensaje para el asistente"
              disabled={enviando}
              className="resize-none"
            />
            <Button onClick={enviar} disabled={enviando || !entrada.trim()} className="shrink-0">
              {enviando ? <Spinner size={16} /> : 'Enviar'}
            </Button>
          </div>
          <p className="mt-1 text-center text-[11px] text-muted-foreground">
            El asistente usa tu perfil de empresa y el conocimiento del ecosistema; puede equivocarse: verifica decisiones críticas.
          </p>
        </div>
      </div>
    </div>
  );
}
