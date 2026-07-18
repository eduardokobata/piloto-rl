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

app = FastAPI(title="TelemetriaV2 - Container 3 DIL simplificado")

# Pista sintética por padrão (fallback da seção 2). Trocar por Track.from_json_file(...)
# assim que o Container 1/2 entregar a pista real.
_sim = DILSimulator(track=Track.synthetic_ellipse())


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
    return _sim.car.state.as_dict()


@app.post("/export")
def export(path_csv: str = "/data/run.csv", path_json: str = "/data/run.json"):
    _sim.export_csv(path_csv)
    _sim.export_json(path_json)
    return {"ok": True, "n_records": len(_sim.history), "csv": path_csv, "json": path_json}


@app.get("/healthz")
def healthz():
    return {"ok": True}
