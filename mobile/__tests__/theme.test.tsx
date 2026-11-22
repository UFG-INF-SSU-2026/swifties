import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import { ReactNode } from 'react';
import { ThemeProvider, useTheme } from '../src/theme';

const wrapper = ({ children }: { children: ReactNode }) => <ThemeProvider>{children}</ThemeProvider>;

beforeEach(async () => { await AsyncStorage.clear(); jest.clearAllMocks(); });

test('padrão: automático', async () => {
  const { result } = await renderHook(() => useTheme(), { wrapper });
  expect(result.current.mode).toBe('auto');
});

test('setMode muda esquema de cores e persiste', async () => {
  const { result } = await renderHook(() => useTheme(), { wrapper });
  await act(async () => result.current.setMode('dark'));
  expect(result.current.scheme).toBe('dark');
  expect(result.current.colors.bg).toBe('#0b0f17');
  expect(AsyncStorage.setItem).toHaveBeenCalledWith('swifties:theme', 'dark');
  await act(async () => result.current.setMode('light'));
  expect(result.current.colors.bg).toBe('#f4f6fa');
});

test('carrega modo salvo', async () => {
  await AsyncStorage.setItem('swifties:theme', 'dark');
  const { result } = await renderHook(() => useTheme(), { wrapper });
  await waitFor(() => expect(result.current.mode).toBe('dark'));
});

test('ignora valor salvo inválido', async () => {
  await AsyncStorage.setItem('swifties:theme', 'roxo');
  const { result } = await renderHook(() => useTheme(), { wrapper });
  await act(async () => {});
  expect(result.current.mode).toBe('auto');
});
