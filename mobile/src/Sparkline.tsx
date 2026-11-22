import { useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from 'react-native-svg';

// Gráfico de linha suave com área em gradiente. Pontos nulos quebram a linha.
export function Sparkline({ valores, cor, altura = 64, id }: { valores: (number | null)[]; cor: string; altura?: number; id: string }) {
  const [w, setW] = useState(0);
  const v = valores.filter((x): x is number => x !== null);
  const pad = 6;
  let linha = '';
  let area = '';
  let ultimo: { x: number; y: number } | null = null;

  if (w > 0 && v.length >= 2) {
    const min = Math.min(...v);
    const max = Math.max(...v);
    const faixa = max - min || 1;
    const passo = (w - pad * 2) / Math.max(valores.length - 1, 1);
    const pts = valores.map((x, i) =>
      x === null ? null : { x: pad + i * passo, y: pad + (1 - (x - min) / faixa) * (altura - pad * 2) },
    );
    let seg: { x: number; y: number }[] = [];
    const segs: { x: number; y: number }[][] = [];
    pts.forEach((p) => {
      if (p) seg.push(p);
      else if (seg.length) (segs.push(seg), (seg = []));
    });
    if (seg.length) segs.push(seg);
    segs.forEach((s) => {
      if (s.length < 2) return;
      let d = `M ${s[0].x} ${s[0].y}`;
      for (let i = 1; i < s.length; i++) {
        const cx = (s[i - 1].x + s[i].x) / 2;
        d += ` C ${cx} ${s[i - 1].y}, ${cx} ${s[i].y}, ${s[i].x} ${s[i].y}`;
      }
      linha += d + ' ';
      area += `${d} L ${s[s.length - 1].x} ${altura} L ${s[0].x} ${altura} Z `;
    });
    ultimo = [...pts].reverse().find((p) => p) ?? null;
  }

  return (
    <View style={{ height: altura }} onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {w > 0 && linha !== '' && (
        <Svg width={w} height={altura}>
          <Defs>
            <LinearGradient id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={cor} stopOpacity={0.35} />
              <Stop offset="1" stopColor={cor} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          <Path d={area} fill={`url(#g-${id})`} />
          <Path d={linha} stroke={cor} strokeWidth={2} fill="none" strokeLinecap="round" />
          {ultimo && <Circle cx={ultimo.x} cy={ultimo.y} r={3.5} fill={cor} />}
        </Svg>
      )}
    </View>
  );
}
