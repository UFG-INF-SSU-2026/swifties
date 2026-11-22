import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { Platform, useColorScheme } from 'react-native';

const dark = {
  bg: '#0b0f17',
  surface: '#131a26',
  surfaceAlt: '#1a2332',
  border: '#232e42',
  text: '#f1f5f9',
  textMuted: '#8a97ad',
  textFaint: '#566178',
  primary: '#6366f1',
  rms: '#60a5fa',
  temp: '#fb923c',
  shadowOpacity: 0.35,
};

const light: typeof dark = {
  bg: '#f4f6fa',
  surface: '#ffffff',
  surfaceAlt: '#f1f4f9',
  border: '#e3e8f0',
  text: '#0f172a',
  textMuted: '#5b677d',
  textFaint: '#94a0b4',
  primary: '#4f46e5',
  rms: '#2563eb',
  temp: '#ea580c',
  shadowOpacity: 0.08,
};

export type Palette = typeof dark;
export type Mode = 'auto' | 'light' | 'dark';

export const radius = { sm: 10, md: 16, lg: 22, pill: 999 };
export const mono = Platform.select({ ios: 'Menlo', default: 'monospace' });

export const shadowFor = (c: Palette) => ({
  shadowColor: '#000',
  shadowOpacity: c.shadowOpacity,
  shadowRadius: 16,
  shadowOffset: { width: 0, height: 8 },
  elevation: 4,
});

type Ctx = { colors: Palette; scheme: 'light' | 'dark'; mode: Mode; setMode: (m: Mode) => void };
const ThemeCtx = createContext<Ctx>({ colors: light, scheme: 'light', mode: 'auto', setMode: () => {} });
const KEY = 'swifties:theme';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const sistema = useColorScheme() === 'dark' ? 'dark' : 'light';
  const [mode, setModeState] = useState<Mode>('auto');

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((v) => v && ['auto', 'light', 'dark'].includes(v) && setModeState(v as Mode))
      .catch(() => {});
  }, []);

  const value = useMemo<Ctx>(() => {
    const scheme = mode === 'auto' ? sistema : mode;
    return {
      colors: scheme === 'dark' ? dark : light,
      scheme,
      mode,
      setMode: (m) => {
        setModeState(m);
        AsyncStorage.setItem(KEY, m).catch(() => {});
      },
    };
  }, [mode, sistema]);

  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export const useTheme = () => useContext(ThemeCtx);
