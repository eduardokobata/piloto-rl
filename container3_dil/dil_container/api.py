"""
api.py — Interface HTTP do Container 3 (DIL simplificado).

Este é o "contrato de dados" (seção 1.4) exposto pelo container. Dois
consumidores esperados:
  1. O processo Python no HOST que roda matlab.engine (Controle VCU em
     Simulink) — chama /step a cada tick de controle, mandando os comandos
     que o Simulink calculou.
  2. Mais tarde, o Container 4 (Piloto IA / RL) — vai chamar /reset no
     início de cada episódio e /step a cada ação, lendo o `state` de volta
     como observação.

Rodar: uvicorn dil_container.api:app --host 0.0.0.0 --port 8090
"""

from fastapi import FastAPI
from pydantic import BaseModel

from .simulator import DILSimulator
from .track import Track

import os

app = FastAPI(title="TelemetriaV2 - Container 3 DIL simplificado")

# Inicializa tentando carregar a pista real a partir do volume compartilhado.
# Em caso de erro, cai automaticamente no fallback sintético (mixed corners).
pista_csv_path = os.getenv("TRACK_CSV_PATH", "/data/track/pista_slam.csv")
_sim = DILSimulator(track=Track.from_csv(pista_csv_path))


class ResetRequest(BaseModel):
    source_label: str = "unknown"   # "piloto" | "ia"


class StepRequest(BaseModel):
    torque_cmd: float     # -1..1
    brake_cmd: float      # 0..1
    steer_cmd: float      # rad
    requested_torque: float | None = None  # opcional: torque pedido antes de limitação, p/ gráfico "solicitado x entregue"


@app.post("/reset")
def reset(req: ResetRequest):
    _sim.reset(source_label=req.source_label)
    return {"ok": True, "state": _sim.car.state.as_dict()}


@app.post("/step")
def step(req: StepRequest):
    record, lap_closed = _sim.step(
        torque_cmd=req.torque_cmd,
        brake_cmd=req.brake_cmd,
        steer_cmd=req.steer_cmd,
        requested_torque=req.requested_torque,
    )
    return {"state": record, "lap_closed": lap_closed, "lap_count": _sim.lap_count}


@app.get("/state")
def get_state():
    state_dict = _sim.car.state.as_dict()
    state_dict["track_source"] = _sim.track.source
    return state_dict


@app.get("/track")
def get_track():
    return {
        "track_source": _sim.track.source,
        "points": _sim.track.points
    }


@app.post("/export")
def export(path_csv: str = "/data/dil_runs/run.csv", path_json: str = "/data/dil_runs/run.json"):
    _sim.export_csv(path_csv)
    _sim.export_json(path_json)
    return {"ok": True, "n_records": len(_sim.history), "csv": path_csv, "json": path_json}


@app.get("/healthz")
def healthz():
    return {"ok": True}
