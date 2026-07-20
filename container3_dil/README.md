# Container 3 — DIL simplificado (scaffold inicial)

## O que já está aqui

- `dil_container/physics.py` — carro como ponto de massa (F=ma, modelo bicicleta cinemático pro yaw).
- `dil_container/track.py` — pista como lista de pontos + detecção de fechamento de volta. Tem fallback sintético (elipse) igual ao `simple-enduro` do mock de telemetria.
- `dil_container/simulator.py` — junta os dois, guarda histórico, exporta CSV/JSON.
- `dil_container/api.py` — API HTTP (`/reset`, `/step`, `/state`, `/export`) que é o contrato de dados do container.
- `host_bridge/vcu_bridge_example.py` — **roda fora do Docker**, no host com MATLAB. Esqueleto de como chamar o `.slx` da VCU via `matlab.engine` e falar com o Container 3 via HTTP.
- `Dockerfile`, `requirements.txt`, `docker-compose.snippet.yml` — pra buildar e plugar na rede dos outros containers.

## Rodar localmente (teste rápido, sem Docker ainda)

```bash
cd container3_dil
pip install -r requirements.txt
uvicorn dil_container.api:app --host 0.0.0.0 --port 8090
```

Testar manualmente:

```bash
curl -X POST localhost:8090/reset -H "Content-Type: application/json" -d '{"source_label":"piloto"}'
curl -X POST localhost:8090/step -H "Content-Type: application/json" \
  -d '{"torque_cmd":0.5,"brake_cmd":0.0,"steer_cmd":0.1}'
curl localhost:8090/state
```

## O que falta pra fechar o escopo do sprint (seção 1.3 do checklist)

- [ ] **Entrada de comandos do teclado/joystick** pra volta manual de bootstrap — hoje só dá pra mandar comando via HTTP/curl. Precisa de um script simples (`pygame` ou `keyboard`) que lê teclado e chama `/step` em loop — essa é a próxima peça a escrever, é rápida.
- [ ] **Trocar o `vcu_bridge_example.py` pelos nomes reais** do modelo `.slx` de vocês (bloco, portas, nome do arquivo).
- [ ] **Receber a pista real do Container 1/2** — hoje só tem `Track.synthetic_ellipse()`. Assim que o contrato de dados da pista (seção 1.4) estiver definido, trocar por `Track.from_json_file(...)` ou consumir direto da ponte do SLAM.
- [ ] **Calibrar `CarParams`** (massa, força máxima do motor/freio) com valores reais do carro, se der tempo — não bloqueia o sprint, mas melhora o realismo do "bloco com massa".
- [ ] **Validar taxa de publicação de estado** compatível com o loop de RL do Container 4 (checklist pede isso explicitamente) — hoje o `dt` é fixo em `simulator.py`, ajustar conforme o que o Container 4 espera.

## Decisão de arquitetura registrada

MATLAB fica **fora do Docker** (roda no host, onde já tem licença). O Container 3 (Python, Dockerizado) só fala HTTP — não precisa saber que do outro lado tem MATLAB. Isso espelha a decisão já tomada pro Container 1 (ROS2 isolado, ponte simples pra fora).
