export const DECISAO_META: Record<string, { label: string; cor: string; curto: string }> = {
  NORMAL: { label: 'Normal', cor: '#10b981', curto: 'Normal' },
  ATENCAO: { label: 'Atenção', cor: '#f59e0b', curto: 'Atenção' },
  CRITICO: { label: 'Crítico', cor: '#ef4444', curto: 'Crítico' },
  SEM_COMUNICACAO: { label: 'Sem sinal', cor: '#f97316', curto: 'Sem sinal' },
  DADOS_INSUFICIENTES: { label: 'Baseline', cor: '#3b82f6', curto: 'Baseline' },
  NAO_AVALIAVEL: { label: 'Desligada', cor: '#9ca3af', curto: 'Desligada' },
};

export const MAX_PONTOS = 90;
export const MAX_HISTORICO = 8;
export const LIMITE_DESATUALIZADO_MS = 8000;
export const TOPICO = 'consumidor/+/decisao';

export type Settings = { host: string; porta: string; usuario: string; senha: string };

// Mesmos valores do dashboard web; troque "host" pelo IP da máquina que roda o broker.
export const DEFAULT_SETTINGS: Settings = {
  host: '192.168.1.241',
  porta: '9001',
  usuario: 'admin',
  senha: 'admin123',
};

export type Decisao = {
  entityId: string;
  decisao: string;
  timestamp: string;
  rmsNorm?: number;
  curtoseMax?: number;
  deltaT?: number;
};

export type Ponto = { hora: string; rms: number | null; temp: number | null };
export type Ativo = {
  entityId: string;
  atual: Decisao;
  recebidoEm: number;
  pontos: Ponto[];
  historico: { hora: string; decisao: string }[];
};
