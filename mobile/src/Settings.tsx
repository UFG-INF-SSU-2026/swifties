import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { DEFAULT_SETTINGS, Settings } from './config';
import { Mode, Palette, radius, useTheme } from './theme';

type Props = {
  settings: Settings;
  alertas: boolean;
  onSave: (s: Settings) => void;
  onAlertas: (v: boolean) => void;
};

export function SettingsScreen({ settings, alertas, onSave, onAlertas }: Props) {
  const { colors, mode, setMode } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [s, setS] = useState(settings);
  const campo = (k: keyof Settings, label: string, extra = {}) => (
    <View style={styles.campo}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={s[k]}
        onChangeText={(t) => setS({ ...s, [k]: t.trim() })}
        autoCapitalize="none"
        autoCorrect={false}
        placeholderTextColor={colors.textFaint}
        selectionColor={colors.primary}
        {...extra}
      />
    </View>
  );
  return (
    <View style={{ gap: 16 }}>
      <Text style={styles.titulo}>Conexão</Text>
      <Text style={styles.hint}>
        Informe o IP do computador que roda o broker Mosquitto (porta WebSocket 9001). Celular e computador precisam estar na mesma rede.
      </Text>
      <View style={styles.painel}>
        {campo('host', 'Host / IP do broker', { keyboardType: 'url' })}
        <View style={styles.linhaCampos}>
          <View style={{ flex: 1 }}>{campo('porta', 'Porta', { keyboardType: 'number-pad' })}</View>
          <View style={{ flex: 2 }}>{campo('usuario', 'Usuário')}</View>
        </View>
        {campo('senha', 'Senha', { secureTextEntry: true })}
      </View>

      <View style={styles.painel}>
        <Text style={styles.label}>Aparência</Text>
        <View style={styles.seg}>
          {([['auto', 'Automático'], ['light', 'Claro'], ['dark', 'Escuro']] as [Mode, string][]).map(([m, l]) => (
            <Pressable key={m} style={[styles.segItem, mode === m && { backgroundColor: colors.primary }]} onPress={() => setMode(m)}>
              <Text style={[styles.segTxt, mode === m && { color: '#fff' }]}>{l}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={[styles.painel, styles.linha]}>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>Vibrar em alerta crítico</Text>
          <Text style={styles.hint}>Feedback tátil quando um ativo entra em estado crítico.</Text>
        </View>
        <Switch value={alertas} onValueChange={onAlertas} trackColor={{ true: colors.primary, false: colors.border }} />
      </View>

      <Pressable style={({ pressed }) => [styles.btn, pressed && { opacity: 0.85 }]} onPress={() => onSave(s)}>
        <Text style={styles.btnTxt}>Salvar e reconectar</Text>
      </Pressable>
      <Pressable onPress={() => setS(DEFAULT_SETTINGS)} hitSlop={10}>
        <Text style={styles.link}>Restaurar padrão</Text>
      </Pressable>
    </View>
  );
}

const makeStyles = (colors: Palette) => StyleSheet.create({
  seg: { flexDirection: 'row', backgroundColor: colors.surfaceAlt, borderRadius: radius.sm, padding: 3 },
  segItem: { flex: 1, paddingVertical: 9, borderRadius: radius.sm - 3, alignItems: 'center' },
  segTxt: { color: colors.textMuted, fontWeight: '600', fontSize: 13 },
  titulo: { color: colors.text, fontSize: 24, fontWeight: '800' },
  hint: { color: colors.textMuted, fontSize: 13, lineHeight: 19 },
  painel: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: 16, gap: 14, borderWidth: 1, borderColor: colors.border },
  campo: { gap: 6 },
  label: { color: colors.text, fontWeight: '600', fontSize: 14 },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.text,
  },
  linhaCampos: { flexDirection: 'row', gap: 12 },
  linha: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  btn: { backgroundColor: colors.primary, paddingVertical: 15, borderRadius: radius.md, alignItems: 'center' },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 16 },
  link: { color: colors.textMuted, textAlign: 'center', fontSize: 14 },
});
