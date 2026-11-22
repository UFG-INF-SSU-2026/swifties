import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import { AtivoCard } from './src/AtivoCard';
import { DECISAO_META, DEFAULT_SETTINGS, Settings } from './src/config';
import { SettingsScreen } from './src/Settings';
import { Palette, radius, ThemeProvider, useTheme } from './src/theme';
import { useMqtt } from './src/useMqtt';

const KEY = 'swifties:settings';
const COR_STATUS = { online: '#10b981', conectando: '#f59e0b', offline: '#ef4444', erro: '#ef4444' } as const;
const TXT_STATUS = { online: 'Online', conectando: 'Conectando', offline: 'Offline', erro: 'Erro' } as const;

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <Main />
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

function Main() {
  const insets = useSafeAreaInsets();
  const { colors, scheme } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [alertas, setAlertas] = useState(true);
  const [aba, setAba] = useState<'ativos' | 'config'>('ativos');
  const [agora, setAgora] = useState(Date.now());

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((v) => setSettings(v ? { ...DEFAULT_SETTINGS, ...JSON.parse(v) } : DEFAULT_SETTINGS))
      .catch(() => setSettings(DEFAULT_SETTINGS));
  }, []);
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const { status, erro, ativos } = useMqtt(settings, alertas);
  const lista = useMemo(() => Object.values(ativos).sort((a, b) => a.entityId.localeCompare(b.entityId)), [ativos]);
  const cont = useMemo(() => {
    const c = { total: lista.length, ok: 0, atencao: 0, critico: 0 };
    lista.forEach((a) => {
      if (a.atual.decisao === 'NORMAL') c.ok++;
      else if (a.atual.decisao === 'ATENCAO') c.atencao++;
      else if (a.atual.decisao === 'CRITICO') c.critico++;
    });
    return c;
  }, [lista]);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>MANUTENÇÃO PREDITIVA</Text>
          <Text style={styles.logo}>Swifties</Text>
        </View>
        <View style={[styles.pill, { borderColor: COR_STATUS[status] + '66', backgroundColor: COR_STATUS[status] + '1f' }]}>
          <View style={[styles.dot, { backgroundColor: COR_STATUS[status] }]} />
          <Text style={[styles.pillTxt, { color: COR_STATUS[status] }]}>{TXT_STATUS[status]}</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {aba === 'ativos' ? (
          <>
            <View style={styles.resumo}>
              <Resumo styles={styles} n={cont.total} label="Ativos" cor={colors.text} />
              <Resumo styles={styles} n={cont.ok} label="Normais" cor={DECISAO_META.NORMAL.cor} />
              <Resumo styles={styles} n={cont.atencao} label="Atenção" cor={DECISAO_META.ATENCAO.cor} />
              <Resumo styles={styles} n={cont.critico} label="Críticos" cor={DECISAO_META.CRITICO.cor} />
            </View>
            {lista.length ? (
              lista.map((a) => <AtivoCard key={a.entityId} ativo={a} agora={agora} />)
            ) : (
              <View style={styles.vazio}>
                <Text style={styles.vazioIcone}>{status === 'online' ? '📡' : '🔌'}</Text>
                <Text style={styles.vazioTitulo}>{status === 'online' ? 'Aguardando decisões' : 'Sem conexão'}</Text>
                <Text style={styles.vazioTxt}>
                  {status === 'online'
                    ? 'Conectado ao broker. Os ativos aparecem assim que o consumidor publicar.'
                    : `Não foi possível alcançar ${settings?.host}:${settings?.porta}.${erro ? `\n${erro}` : ''}\nConfira o IP em Ajustes.`}
                </Text>
              </View>
            )}
          </>
        ) : (
          settings && (
            <SettingsScreen
              settings={settings}
              alertas={alertas}
              onAlertas={setAlertas}
              onSave={(s) => {
                AsyncStorage.setItem(KEY, JSON.stringify(s)).catch(() => {});
                setSettings(s);
                setAba('ativos');
              }}
            />
          )
        )}
      </ScrollView>

      <View style={[styles.tabbar, { paddingBottom: Math.max(insets.bottom, 12) }]}>
        {(
          [
            ['ativos', '◉', 'Ativos'],
            ['config', '⚙', 'Ajustes'],
          ] as const
        ).map(([k, ic, label]) => (
          <Pressable key={k} style={styles.tab} onPress={() => setAba(k)}>
            <Text style={[styles.tabIc, aba === k && { color: colors.primary }]}>{ic}</Text>
            <Text style={[styles.tabTxt, aba === k && { color: colors.text }]}>{label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Resumo({ n, label, cor, styles }: { n: number; label: string; cor: string; styles: ReturnType<typeof makeStyles> }) {
  return (
    <View style={styles.resumoItem}>
      <Text style={[styles.resumoN, { color: cor }]}>{n}</Text>
      <Text style={styles.resumoL}>{label}</Text>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14 },
  eyebrow: { color: colors.textFaint, fontSize: 10, fontWeight: '700', letterSpacing: 1.8 },
  logo: { color: colors.text, fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 7, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.pill, borderWidth: 1 },
  pillTxt: { fontSize: 12, fontWeight: '700' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  scroll: { padding: 20, paddingTop: 8, paddingBottom: 32 },
  resumo: { flexDirection: 'row', backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, paddingVertical: 14, marginBottom: 18 },
  resumoItem: { flex: 1, alignItems: 'center' },
  resumoN: { fontSize: 26, fontWeight: '800' },
  resumoL: { color: colors.textMuted, fontSize: 11, fontWeight: '600', marginTop: 2 },
  vazio: { alignItems: 'center', paddingVertical: 60, paddingHorizontal: 24, gap: 8 },
  vazioIcone: { fontSize: 44 },
  vazioTitulo: { color: colors.text, fontSize: 18, fontWeight: '700' },
  vazioTxt: { color: colors.textMuted, textAlign: 'center', lineHeight: 20, fontSize: 13 },
  tabbar: { flexDirection: 'row', backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10 },
  tab: { flex: 1, alignItems: 'center', gap: 2 },
  tabIc: { fontSize: 20, color: colors.textFaint },
  tabTxt: { fontSize: 11, fontWeight: '600', color: colors.textFaint },
});
