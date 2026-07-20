"""
vcu_bridge_example.py — Roda NO HOST (fora do Docker), onde o MATLAB/Simulink
está licenciado. NÃO entra no container 3.

Loop:
  1. lê o estado atual do DIL (Container 3, via HTTP)
  2. passa esse estado pro modelo Simulink da VCU (matlab.engine)
  3. pega torque/freio/direção calculados pelo Simulink
  4. manda de volta pro Container 3 via /step

Pré-requisito: `pip install matlabengine` (ou o pacote que corresponde à
versão do MATLAB instalada) e o Simulink Engine API habilitado.

Isso é só um esqueleto — ajuste os nomes de bloco/porta do seu modelo .slx
real (`MODEL_NAME`, `INPUT_PORT`, `OUTPUT_PORT` abaixo são placeholders).
"""

import time
import requests

DIL_URL = "http://localhost:8090"   # ajustar se o container publicar noutra porta/host
MODEL_NAME = "vcu_control"          # nome do .slx, sem extensão
DT = 0.02                           # deve bater com o dt do DILSimulator

try:
    import matlab.engine
except ImportError:
    matlab = None  # permite importar este arquivo sem MATLAB instalado, só pra leitura/CI


def start_matlab():
    eng = matlab.engine.start_matlab()
    eng.load_system(MODEL_NAME, nargout=0)
    return eng


def run_control_step(eng, state: dict) -> dict:
    """
    Chama o modelo Simulink com o estado atual do carro e devolve os
    comandos calculados. Adaptar a chamada real (via `eng.set_param`,
    `eng.sim`, ou um bloco S-Function com I/O direto) ao que o modelo de
    vocês espera. Deixo aqui a versão mais simples: workspace variables +
    `sim()` de um passo, que costuma ser o caminho mais direto pra rodar o
    Simulink em modo "step by step" a partir do Python.
    """
    eng.workspace["car_x"] = state["x"]
    eng.workspace["car_y"] = state["y"]
    eng.workspace["car_speed"] = state["speed_mps"]
    eng.workspace["car_heading"] = state["heading_rad"]
    eng.workspace["car_yaw_rate"] = state["yaw_rate_rad_s"]

    eng.set_param(MODEL_NAME, "SimulationCommand", "step", nargout=0)

    torque_cmd = eng.workspace["vcu_torque_cmd"]
    brake_cmd = eng.workspace["vcu_brake_cmd"]
    steer_cmd = eng.workspace["vcu_steer_cmd"]

    return {
        "torque_cmd": float(torque_cmd),
        "brake_cmd": float(brake_cmd),
        "steer_cmd": float(steer_cmd),
    }


def main():
    assert matlab is not None, "matlab.engine não instalado neste host."
    eng = start_matlab()

    requests.post(f"{DIL_URL}/reset", json={"source_label": "piloto"})

    try:
        while True:
            state = requests.get(f"{DIL_URL}/state").json()
            cmd = run_control_step(eng, state)
            resp = requests.post(f"{DIL_URL}/step", json=cmd).json()

            if resp["lap_closed"]:
                print(f"Volta fechada! lap_count={resp['lap_count']}")

            time.sleep(DT)
    except KeyboardInterrupt:
        pass
    finally:
        requests.post(f"{DIL_URL}/export")
        eng.quit()


if __name__ == "__main__":
    main()
