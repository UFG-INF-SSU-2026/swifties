// Cliente MQTT falso: guarda os handlers para os testes dispararem eventos.
export class FakeClient {
  handlers: Record<string, (...a: any[]) => void> = {};
  subscribe = jest.fn();
  end = jest.fn();
  constructor(public url: string, public opts: any) {}
  on(ev: string, fn: (...a: any[]) => void) { this.handlers[ev] = fn; return this; }
  emit(ev: string, ...a: any[]) { this.handlers[ev]?.(...a); }
}
export const clientes: FakeClient[] = [];
export const connect = jest.fn((url: string, opts: any) => {
  const c = new FakeClient(url, opts);
  clientes.push(c);
  return c;
});
export const ultimo = () => clientes[clientes.length - 1];
