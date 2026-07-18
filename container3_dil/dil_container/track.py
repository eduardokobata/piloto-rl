"""
track.py — Representação mínima da pista.

Aceita a mesma saída que Container 1 (SLAM) ou Container 2 (pista sintética)
devem produzir: uma lista ordenada de pontos (x, y) formando a linha central
(ou borda) fechada da pista. Ver seção 1.4 do checklist — o "contrato de
dados" entre containers deveria fixar esse formato antes de todo mundo codar;
isso aqui assume o formato mais simples possível: JSON com lista de pontos.

Também cuida da detecção de "fechar volta" (pra saber quando o piloto/IA
completou 1 lap), usando o ponto de partida como checkpoint.
"""

from dataclasses import dataclass
import json
import math


@dataclass
class Track:
    points: list[tuple[float, float]]  # linha central fechada, em ordem
    start_radius_m: float = 3.0        # raio de tolerância pra considerar "voltou ao início"

    @classmethod
    def from_json_file(cls, path: str) -> "Track":
        with open(path, "r") as f:
            data = json.load(f)
        pts = [(p["x"], p["y"]) for p in data["points"]]
        return cls(points=pts)

    @classmethod
    def synthetic_ellipse(cls, a: float = 40.0, b: float = 25.0, n: int = 200) -> "Track":
        """Pista sintética de fallback (mesma ideia do simple-enduro do mock).
        Usar se o SLAM real (Container 1) não estiver pronto a tempo — ver
        seção 2 do checklist ('válvula de escape')."""
        pts = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            pts.append((a * math.cos(theta), b * math.sin(theta)))
        return cls(points=pts)

    def start_point(self) -> tuple[float, float]:
        return self.points[0]

    def distance_to_start(self, x: float, y: float) -> float:
        sx, sy = self.start_point()
        return math.hypot(x - sx, y - sy)

    def has_crossed_start(self, x: float, y: float, t_since_last_start: float, min_lap_time_s: float = 5.0) -> bool:
        """Evita contar volta 'fechada' nos primeiros segundos (quando o carro
        ainda está saindo do próprio ponto de partida)."""
        if t_since_last_start < min_lap_time_s:
            return False
        return self.distance_to_start(x, y) <= self.start_radius_m
