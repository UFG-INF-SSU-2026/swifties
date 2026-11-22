import { StyleSheet, Text, View } from 'react-native';
import { Ativo, DECISAO_META, LIMITE_DESATUALIZADO_MS } from './config';
import { Sparkline } from './Sparkline';
import { useMemo } from 'react';
import { mono, Palette, radius, shadowFor, useTheme } from './theme';

const fmt = (v?: number, suf = '') => (typeof v === 'number' ? `${v}${suf}` : '—');

export function AtivoCard({ ativo, agora }: { ativo: Ativo; agora: number }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shadow = shadowFor(colors);
  const meta = DECISAO_META[ativo.atual.decisao] ?? DECISAO_META.DADOS_INSUFICIENTES;
  const velho = agora - ativo.recebidoEm > LIMITE_DESATUALIZADO_MS;
  const desligada = ativo.atual.decisao === 'NAO_AVALIAVEL';
  const critico = ativo.atual.decisao === 'CRITICO';

  return (
    <View
      style={[
        styles.card,
        shadow,
        { opacity: velho || desligada ? 0.6 : 1 },
        critico && { borderColor: meta.cor, shadowColor: meta.cor, shadowOpacity: 0.5 },
      ]}
    >
      <View style={[styles.faixa, { backgroundColor: meta.cor }]} />
      <View style={styles.head}>
        <View style={{ flex: 1 }}>
          <Text style={styles.eyebrow}>ATIVO</Text>
          <Text style={styles.titulo} numberOfLines={1}>
            {ativo.entityId}
          </Text>
        </View>
        <View style={[styles.badge, { backgroundColor: meta.cor + '22', borderColor: meta.cor + '66' }]}>
          <View style={[styles.dot, { backgroundColor: meta.cor }]} />
          <Text style={[styles.badgeTxt, { color: meta.cor }]}>{meta.curto}</Text>
        </View>
      </View>

      <View style={styles.metricas}>
        <Metrica styles={styles} label="RMS NORM" valor={fmt(ativo.atual.rmsNorm, '×')} cor={colors.rms} />
        <Metrica styles={styles} label="ΔT" valor={fmt(ativo.atual.deltaT, '°')} cor={colors.temp} />
        <Metrica styles={styles} label="CURTOSE" valor={fmt(ativo.atual.curtoseMax)} cor={colors.text} />
      </View>

      <Text style={styles.sub}>Tendência · RMS</Text>
      <Sparkline id={ativo.entityId + 'r'} valores={ativo.pontos.map((p) => p.rms)} cor={colors.rms} />
      <Text style={styles.sub}>Tendência · ΔT</Text>
      <Sparkline id={ativo.entityId + 't'} valores={ativo.pontos.map((p) => p.temp)} cor={colors.temp} />

      <Text style={[styles.sub, { marginTop: 14 }]}>Linha do tempo</Text>
      {ativo.historico.slice(0, 4).map((h, i) => {
        const m = DECISAO_META[h.decisao] ?? meta;
        return (
          <View key={i} style={styles.hItem}>
            <View style={[styles.hDot, { backgroundColor: m.cor }]} />
            <Text style={styles.hHora}>{h.hora}</Text>
            <Text style={styles.hTxt}>{m.curto}</Text>
          </View>
        );
      })}

      <View style={styles.rodape}>
        <View style={[styles.dot, { backgroundColor: velho ? '#f97316' : '#10b981' }]} />
        <Text style={styles.ts}>
          {velho ? 'Dados desatualizados · ' : 'Ao vivo · '}
          {new Date(ativo.atual.timestamp).toLocaleTimeString()}
        </Text>
      </View>
    </View>
  );
}

function Metrica({ label, valor, cor, styles }: { label: string; valor: string; cor: string; styles: ReturnType<typeof makeStyles> }) {
  return (
    <View style={styles.metrica}>
      <Text style={styles.mLabel}>{label}</Text>
      <Text style={[styles.mValor, { color: cor }]}>{valor}</Text>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: 18,
    paddingTop: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  faixa: { position: 'absolute', top: 0, left: 0, right: 0, height: 3 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  eyebrow: { color: colors.textFaint, fontSize: 10, fontWeight: '700', letterSpacing: 1.5 },
  titulo: { color: colors.text, fontSize: 19, fontWeight: '700', marginTop: 2 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1 },
  badgeTxt: { fontSize: 12, fontWeight: '700' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  metricas: { flexDirection: 'row', gap: 10, marginVertical: 16 },
  metrica: { flex: 1, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, padding: 12 },
  mLabel: { color: colors.textMuted, fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  mValor: { fontSize: 22, fontWeight: '700', marginTop: 4, fontFamily: mono },
  sub: { color: colors.textMuted, fontSize: 12, fontWeight: '600', marginTop: 8, marginBottom: 4 },
  hItem: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 },
  hDot: { width: 8, height: 8, borderRadius: 4 },
  hHora: { color: colors.textFaint, fontSize: 12, fontFamily: mono, width: 84 },
  hTxt: { color: colors.text, fontSize: 13, fontWeight: '600' },
  rodape: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border },
  ts: { color: colors.textFaint, fontSize: 11 },
});
