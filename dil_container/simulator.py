"""
simulator.py — Orquestra physics.py + track.py, mantém histórico do passo
a passo (percurso do piloto/IA) e exporta pra CSV/JSON, conforme pedido na
seção 1.3 ("Interface simples para registrar e exportar dados").
"""

from dataclasses import asdict
import csv
import json
import time

from .physics import PointMassCar, CarParams, CarState
from .track import Track


class DILSimulator:
    def __init__(self, track: Track, params: CarParams | None = None, dt: float = 0.02):
        self.track = track
        self.car = PointMassCar(params=params)
        self.dt = dt
        self.history: list[dict] = []
        self.lap_count = 0
        self._t_last_start = 0.0
        self.source_label = "unknown"  # "piloto" ou "ia", útil pro gráfico de overlay (seção 5)

    def reset(self, source_label: str = "unknown"):
        self.car.reset()
        self.history = []
        self.lap_count = 0
        self._t_last_start = 0.0
        self.source_label = source_label

    def step(self, torque_cmd: float, brake_cmd: float, steer_cmd: float, requested_torque: float | None = None):
        state = self.car.step(torque_cmd, brake_cmd, steer_cmd, self.dt)

        lap_closed = self.track.has_crossed_start(
            state.x, state.y, state.t - self._t_last_start
        )
        if lap_closed:
            self.lap_count += 1
            self._t_last_start = state.t

        record = state.as_dict()
        record.update({
            "torque_cmd": torque_cmd,
            "requested_torque": requested_torque if requested_torque is not None else torque_cmd,
            "brake_cmd": brake_cmd,
            "steer_cmd": steer_cmd,
            "lap_count": self.lap_count,
            "source": self.source_label,
            "wall_time": time.time(),
        })
        self.history.append(record)
        return record, lap_closed

    def export_csv(self, path: str):
        if not self.history:
            return
        keys = list(self.history[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.history)

    def export_json(self, path: str):
        with open(path, "w") as f:
            json.dump(self.history, f)
