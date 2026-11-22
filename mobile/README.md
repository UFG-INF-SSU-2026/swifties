# Swifties Monitor — app mobile (Expo Go)

Equivalente mobile do `../dashboard`: conecta ao broker Mosquitto por **MQTT sobre WebSocket (porta 9001)**, assina `consumidor/+/decisao` e mostra, por ativo, estado (Normal/Atenção/Crítico/…), RMS Norm, ΔT, curtose, gráficos de tendência e histórico de mudanças de estado. Vibra ao entrar em estado **Crítico** (desativável).

## Rodar
1. Suba o broker (`../broker`) e o consumidor (`../consumidor`) e algum publisher/mock.
2. ```bash
   cd mobile && npm install && npx expo start
   ```
3. Escaneie o QR code com o Expo Go (celular e computador na mesma rede Wi-Fi).
4. Na aba **Configurações**, informe o IP do computador (ex.: `192.168.1.241`), porta `9001`, usuário/senha (`admin`/`admin123`). Fica salvo no aparelho.

Obs.: `localhost` não funciona no celular — use o IP da LAN. Se não conectar, libere a porta 9001 no firewall.
