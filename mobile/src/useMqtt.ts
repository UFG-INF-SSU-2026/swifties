import { useEffect, useRef, useState } from 'react';
import { Vibration } from 'react-native';
// bundle de navegador do mqtt.js: funciona no Metro/Expo Go (WebSocket nativo do RN)
// @ts-ignore
import mqtt from 'mqtt/dist/mqtt.esm';
import { Ativo, Decisao, MAX_HISTORICO, MAX_PONTOS, Settings, TOPICO } from './config';

export type Status = 'conectando' | 'online' | 'offline' | 'erro';

const num = (v: unknown) => (typeof v === 'number' ? v : null);

export function useMqtt(settings: Settings | null, alertas: boolean) {
  const [status, setStatus] = useState<Status>('offline');
  const [erro, setErro] = useState<string>('');
  const [ativos, setAtivos] = useState<Record<string, Ativo>>({});
  const alertasRef = useRef(alertas);
  alertasRef.current = alertas;

  useEffect(() => {
    if (!settings) return;
    setStatus('conectando');
    setErro('');
    const client = mqtt.connect(`ws://${settings.host}:${settings.porta}`, {
      username: settings.usuario,
      password: settings.senha,
      clientId: 'mobile_' + Math.random().toString(16).slice(2, 8),
      reconnectPeriod: 3000,
      connectTimeout: 8000,
    });

    client.on('connect', () => {
      setStatus('online');
      setErro('');
      client.subscribe(TOPICO, { qos: 1 });
    });
    client.on('reconnect', () => setStatus('conectando'));
    client.on('close', () => setStatus((s) => (s === 'erro' ? s : 'offline')));
    client.on('error', (e: Error) => {
      setStatus('erro');
      setErro(e?.message ?? String(e));
    });

    client.on('message', (_t: string, payload: any) => {
      let d: Decisao;
      try {
        d = JSON.parse(payload.toString());
      } catch {
        return;
      }
      if (!d?.entityId) return;
      const hora = new Date(d.timestamp).toLocaleTimeString();
      setAtivos((prev) => {
        const ant = prev[d.entityId];
        const pontos = [...(ant?.pontos ?? []), { hora, rms: num(d.rmsNorm), temp: num(d.deltaT) }].slice(-MAX_PONTOS);
        let historico = ant?.historico ?? [];
        if (ant?.atual.decisao !== d.decisao) {
          historico = [{ hora, decisao: d.decisao }, ...historico].slice(0, MAX_HISTORICO);
          if (ant && d.decisao === 'CRITICO' && alertasRef.current) Vibration.vibrate([0, 400, 200, 400]);
        }
        return { ...prev, [d.entityId]: { entityId: d.entityId, atual: d, recebidoEm: Date.now(), pontos, historico } };
      });
    });

    return () => {
      client.end(true);
    };
  }, [settings?.host, settings?.porta, settings?.usuario, settings?.senha]);

  return { status, erro, ativos };
}
