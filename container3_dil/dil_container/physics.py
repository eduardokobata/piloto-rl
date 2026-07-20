"""
physics.py — Modelo de carro como ponto de massa (bloco com massa).

Escopo deliberadamente mínimo (ver checklist seção 1.3):
- posição (x, y), heading, velocidade escalar
- SEM suspensão, SEM transferência de carga, SEM modelo de pneu detalhado
- integração simples (Euler explícito) — suficiente para o sprint

Entradas por passo: torque_cmd (Nm ou N normalizado -1..1), brake_cmd (0..1),
steer_cmd (rad, ângulo de esterçamento equivalente).

Isso é intencionalmente simples: o roadmap pós-sprint (seção 7.2 do checklist)
é justamente sofisticar isso aos poucos (pneu, suspensão, esterçamento variável).
"""

from dataclasses import dataclass, field
import math


@dataclass
class CarParams:
    mass_kg: float = 220.0          # massa aproximada FSAE-E
    max_motor_force_n: float = 4000.0
    max_brake_force_n: float = 6000.0
    drag_coeff: float = 0.6         # resistência aerodinâmica simplificada
    rolling_resistance: float = 40.0
    wheelbase_m: float = 1.55       # usado só p/ relação steer -> yaw rate (modelo bicicleta cinemático)


@dataclass
class CarState:
    x: float = 0.0
    y: float = 0.0
    heading_rad: float = 0.0        # yaw
    speed_mps: float = 0.0          # velocidade escalar ao longo do heading
    accel_mps2: float = 0.0         # última aceleração longitudinal (para telemetria/log)
    yaw_rate_rad_s: float = 0.0
    t: float = 0.0                  # tempo de simulação acumulado

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "heading_rad": self.heading_rad,
            "speed_mps": self.speed_mps,
            "accel_mps2": self.accel_mps2,
            "yaw_rate_rad_s": self.yaw_rate_rad_s,
            "t": self.t,
        }


class PointMassCar:
    """Integrador simples: recebe comandos normalizados, devolve novo estado."""

    def __init__(self, params: CarParams | None = None, state: CarState | None = None):
        self.params = params or CarParams()
        self.state = state or CarState()

    def reset(self, state: CarState | None = None):
        self.state = state or CarState()

    def step(self, torque_cmd: float, brake_cmd: float, steer_cmd: float, dt: float) -> CarState:
        """
        torque_cmd: -1..1 (negativo = regen/torque reverso, se fizer sentido pro VCU de vocês)
        brake_cmd: 0..1
        steer_cmd: rad, ângulo de esterçamento (equivalente, modelo bicicleta cinemático)
        dt: passo de integração em segundos
        """
        p, s = self.params, self.state
        torque_cmd = max(-1.0, min(1.0, torque_cmd))
        brake_cmd = max(0.0, min(1.0, brake_cmd))

        drive_force = torque_cmd * p.max_motor_force_n
        brake_force = -math.copysign(1.0, s.speed_mps) * brake_cmd * p.max_brake_force_n if s.speed_mps != 0 else 0.0
        drag_force = -math.copysign(1.0, s.speed_mps) * p.drag_coeff * s.speed_mps ** 2
        rolling_force = -math.copysign(1.0, s.speed_mps) * p.rolling_resistance if s.speed_mps != 0 else 0.0

        net_force = drive_force + brake_force + drag_force + rolling_force
        accel = net_force / p.mass_kg

        new_speed = s.speed_mps + accel * dt
        # não deixa "vento" empurrar o carro pra trás sozinho num freio total
        if s.speed_mps > 0 and new_speed < 0:
            new_speed = 0.0

        # modelo bicicleta cinemático simplificado pra yaw rate
        yaw_rate = 0.0
        if p.wheelbase_m > 0:
            yaw_rate = (new_speed / p.wheelbase_m) * math.tan(steer_cmd)

        new_heading = s.heading_rad + yaw_rate * dt
        new_x = s.x + new_speed * math.cos(new_heading) * dt
        new_y = s.y + new_speed * math.sin(new_heading) * dt

        self.state = CarState(
            x=new_x,
            y=new_y,
            heading_rad=new_heading,
            speed_mps=new_speed,
            accel_mps2=accel,
            yaw_rate_rad_s=yaw_rate,
            t=s.t + dt,
        )
        return self.state
