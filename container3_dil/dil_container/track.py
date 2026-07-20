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
    source: str = "synthetic"          # "csv" ou "synthetic"

    @classmethod
    def from_json_file(cls, path: str) -> "Track":
        with open(path, "r") as f:
            data = json.load(f)
        pts = [(p["x"], p["y"]) for p in data["points"]]
        return cls(points=pts, source="json")

    @classmethod
    def from_csv(cls, path: str) -> "Track":
        import logging
        logger = logging.getLogger("uvicorn")
        try:
            import numpy as np
            import pandas as pd
            from scipy.interpolate import splprep, splev
            
            df = pd.read_csv(path)
            x_col = 'X' if 'X' in df.columns else 'x'
            y_col = 'Y' if 'Y' in df.columns else 'y'
            x_raw = df[x_col].values
            y_raw = df[y_col].values
            
            dist_fechamento = np.hypot(x_raw[-1]-x_raw[0], y_raw[-1]-y_raw[0])
            fechar_loop = dist_fechamento < 2.0
            
            per = 1 if fechar_loop else 0
            tck, u = splprep([x_raw, y_raw], s=0.0, per=per, k=3)
            
            u_fine = np.linspace(0, 1, 5000)
            x_fine, y_fine = splev(u_fine, tck)
            ds_fine = np.hypot(np.diff(x_fine), np.diff(y_fine))
            comprimento_total = np.sum(ds_fine)
            
            n_points = int(comprimento_total / 0.5) # ds=0.5
            s = np.linspace(0, comprimento_total, n_points)
            
            s_acumulado = np.concatenate([[0], np.cumsum(ds_fine)])
            u_de_s = np.interp(s, s_acumulado, u_fine)
            
            x, y = splev(u_de_s, tck)
            
            pts = list(zip(x.tolist(), y.tolist()))
            logger.info(f"Pista real carregada do CSV {path} com {len(pts)} pontos.")
            return cls(points=pts, source="csv")
        except Exception as e:
            logger.warning(f"Erro ao carregar/parsear a pista real do CSV {path}: {e}. Caindo no fallback sintético.")
            return cls.synthetic_mixed_corners()

    @classmethod
    def synthetic_ellipse(cls, a: float = 40.0, b: float = 25.0, n: int = 200) -> "Track":
        """Pista sintética de fallback (mesma ideia do simple-enduro do mock).
        Usar se o SLAM real (Container 1) não estiver pronto a tempo — ver
        seção 2 do checklist ('válvula de escape')."""
        pts = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            pts.append((a * math.cos(theta), b * math.sin(theta)))
        return cls(points=pts, source="synthetic")

    @classmethod
    def synthetic_mixed_corners(cls, n: int = 400) -> "Track":
        """Gera uma pista sintética com curvas de diferentes raios (mixed corners)."""
        pts = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            r = 30.0 + 10.0 * math.sin(2 * theta) + 5.0 * math.sin(5 * theta)
            pts.append((r * math.cos(theta), r * math.sin(theta)))
        return cls(points=pts, source="synthetic")

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
