#!/usr/bin/env python3
"""
manual_drive.py — Controle manual (teclado) para o Container 3 (DIL simplificado).

Suporta:
- Visualização de largura da pista com borda interna (esquerda) e borda externa (direita).
- Desenho de DUAS trajetórias (Linha de Referência da Pista vs Rastro percorrido em tempo real).
- Detecção de fora da pista (Off-track alert) se o carro passar dos limites das bordas.
- Exportação automática ao encerrar.
"""

import sys
import os
import math
import time
import requests
import pygame
import numpy as np

# Configuração da URL da API
DIL_URL = os.getenv("DIL_URL", "http://localhost:8090").rstrip('/')

def get_track_data():
    """Busca os dados da pista no DIL container."""
    url = f"{DIL_URL}/track"
    print(f"Buscando pista de {url}...")
    for attempt in range(5):
        try:
            resp = requests.get(url, timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException as e:
            print(f"Tentativa {attempt+1}/5 falhou ao conectar ao DIL: {e}")
            time.sleep(1.0)
    print("Erro: Não foi possível conectar ao DIL container. Certifique-se de que ele está rodando.")
    sys.exit(1)

def reset_simulation():
    """Reseta a simulação definindo a fonte como piloto humano."""
    url = f"{DIL_URL}/reset"
    try:
        resp = requests.post(url, json={"source_label": "piloto"}, timeout=2.0)
        if resp.status_code == 200:
            print("Simulação resetada com sucesso para piloto humano.")
            return resp.json().get("state", {})
    except requests.RequestException as e:
        print(f"Erro ao resetar simulação: {e}")
    return {}

def send_step(torque, brake, steer):
    """Envia comandos para dar um passo de simulação."""
    url = f"{DIL_URL}/step"
    payload = {
        "torque_cmd": float(torque),
        "brake_cmd": float(brake),
        "steer_cmd": float(steer)
    }
    try:
        resp = requests.post(url, json=payload, timeout=0.5)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        pass
    return None

def export_run():
    """Exporta a simulação executada."""
    url = f"{DIL_URL}/export"
    try:
        resp = requests.post(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Corrida exportada com sucesso: CSV em {data.get('csv')}, JSON em {data.get('json')}")
            return
    except requests.RequestException as e:
        print(f"Erro ao exportar corrida: {e}")

def main():
    # 1. Carrega a pista do DIL
    track_info = get_track_data()
    points = track_info.get("points", [])
    left_boundary = track_info.get("left_boundary", [])
    right_boundary = track_info.get("right_boundary", [])
    track_width_m = track_info.get("track_width_m", 4.0)
    track_source = track_info.get("track_source", "desconhecido")
    
    if not points:
        print("Erro: A pista retornada pelo DIL está vazia!")
        sys.exit(1)
        
    print(f"Pista carregada com sucesso! Fonte: {track_source} | Largura: {track_width_m}m | {len(points)} pontos.")

    # 2. Inicializa o estado do Simulador
    initial_state = reset_simulation()
    
    # 3. Inicializa o Pygame
    pygame.init()
    pygame.font.init()
    
    screen_w, screen_h = 1024, 768
    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("Eracing - Piloto IA: Manual Drive & Telemetria")
    clock = pygame.time.Clock()
    
    try:
        font = pygame.font.SysFont("Outfit", 20)
        font_bold = pygame.font.SysFont("Outfit", 24, bold=True)
        font_alert = pygame.font.SysFont("Outfit", 28, bold=True)
    except Exception:
        font = pygame.font.Font(None, 24)
        font_bold = pygame.font.Font(None, 28)
        font_alert = pygame.font.Font(None, 32)

    # Coordenadas limites para escala
    all_x = [p[0] for p in points] + [p[0] for p in left_boundary] + [p[0] for p in right_boundary]
    all_y = [p[1] for p in points] + [p[1] for p in left_boundary] + [p[1] for p in right_boundary]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    track_w = max_x - min_x
    track_h = max_y - min_y
    
    margin = 70
    scale_x = (screen_w - 2 * margin) / max(track_w, 1e-5)
    scale_y = (screen_h - 2 * margin) / max(track_h, 1e-5)
    scale = min(scale_x, scale_y)
    
    offset_x = margin + (screen_w - 2 * margin - track_w * scale) / 2
    offset_y = margin + (screen_h - 2 * margin - track_h * scale) / 2
    
    def to_screen(x, y):
        sx = offset_x + (x - min_x) * scale
        sy = offset_y + (max_y - y) * scale
        return int(sx), int(sy)

    # Converte bordas e pontos centrais para coordenadas de tela
    screen_center = [to_screen(p[0], p[1]) for p in points]
    screen_left = [to_screen(p[0], p[1]) for p in left_boundary] if left_boundary else []
    screen_right = [to_screen(p[0], p[1]) for p in right_boundary] if right_boundary else []

    # Estado inicial do veículo
    car_x = initial_state.get("x", points[0][0])
    car_y = initial_state.get("y", points[0][1])
    car_heading = initial_state.get("heading_rad", 0.0)
    car_speed = initial_state.get("speed_mps", 0.0)
    lap_count = 0
    
    # Histórico de trajetória percorrida pelo jogador em tempo real (Rastro)
    player_trail = []

    # Controle de direção por rampa
    steer_cmd = 0.0
    max_steer = 0.45      # rad (~26 graus)
    ramp_speed = 1.6     # rad/s
    center_speed = 2.2   # rad/s
    dt = 0.02
    
    running = True

    pts_np = np.array(points)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()
        
        # Aceleração e Frenagem
        torque_cmd = 1.0 if keys[pygame.K_UP] else 0.0
        brake_cmd = 1.0 if keys[pygame.K_DOWN] else 0.0

        # Esterçamento
        if keys[pygame.K_LEFT]:
            steer_cmd = max(-max_steer, steer_cmd - ramp_speed * dt)
        elif keys[pygame.K_RIGHT]:
            steer_cmd = min(max_steer, steer_cmd + ramp_speed * dt)
        else:
            if steer_cmd > 0:
                steer_cmd = max(0.0, steer_cmd - center_speed * dt)
            elif steer_cmd < 0:
                steer_cmd = min(0.0, steer_cmd + center_speed * dt)

        # Passo da simulação
        step_result = send_step(torque_cmd, brake_cmd, steer_cmd)
        if step_result:
            state = step_result.get("state", {})
            car_x = state.get("x", car_x)
            car_y = state.get("y", car_y)
            car_heading = state.get("heading_rad", car_heading)
            car_speed = state.get("speed_mps", car_speed)
            lap_count = step_result.get("lap_count", lap_count)
            player_trail.append((car_x, car_y))

        # Verifica distância em relação à linha central para detecção de FORA DA PISTA
        dists = np.hypot(pts_np[:, 0] - car_x, pts_np[:, 1] - car_y)
        dist_to_center = np.min(dists)
        is_off_track = dist_to_center > (track_width_m / 2.0)

        # --- RENDERIZAÇÃO ---
        screen.fill((18, 18, 18))
        
        # 1. Pista: desenha o asfalto entre borda esquerda e direita
        if screen_left and screen_right and len(screen_left) == len(screen_right):
            for i in range(len(screen_left) - 1):
                poly_pts = [screen_left[i], screen_left[i+1], screen_right[i+1], screen_right[i]]
                pygame.draw.polygon(screen, (40, 44, 52), poly_pts)
        
        # 2. Desenha Borda Esquerda (Azul Cyan) e Borda Direita (Amarelo Neon)
        if screen_left and len(screen_left) > 1:
            pygame.draw.lines(screen, (0, 229, 255), True, screen_left, 2)
        if screen_right and len(screen_right) > 1:
            pygame.draw.lines(screen, (255, 215, 0), True, screen_right, 2)

        # 3. Trajetória 1: Linha Central da Pista / Linha de Referência (Tracejada/Suave)
        if len(screen_center) > 1:
            pygame.draw.lines(screen, (100, 110, 120), True, screen_center, 1)
            pygame.draw.circle(screen, (0, 255, 128), screen_center[0], 6)  # Linha de largada

        # 4. Trajetória 2: Rastro percorrido em tempo real pelo Piloto Humano (Rosa Neon)
        if len(player_trail) > 1:
            trail_screen = [to_screen(pt[0], pt[1]) for pt in player_trail[-800:]] # últimas posições
            if len(trail_screen) > 1:
                pygame.draw.lines(screen, (255, 0, 85), False, trail_screen, 3)

        # 5. Veículo (Círculo vermelho com direção do heading)
        car_screen = to_screen(car_x, car_y)
        car_color = (255, 50, 50) if not is_off_track else (255, 140, 0)
        pygame.draw.circle(screen, car_color, car_screen, 8)
        
        heading_x = car_x + (16 / scale) * math.cos(car_heading)
        heading_y = car_y + (16 / scale) * math.sin(car_heading)
        pygame.draw.line(screen, (255, 255, 255), car_screen, to_screen(heading_x, heading_y), 3)

        # HUD / Painel de Informações
        hud_bg = pygame.Surface((280, 180))
        hud_bg.set_alpha(190)
        hud_bg.fill((25, 25, 25))
        screen.blit(hud_bg, (15, 15))
        
        hud_lines = [
            ("Eracing DIL Simulator", (0, 229, 255), True),
            (f"Velocidade: {car_speed * 3.6:.1f} km/h", (240, 240, 240), False),
            (f"Voltas: {lap_count}", (240, 240, 240), False),
            (f"Torque: {torque_cmd * 100:.0f}%  Freio: {brake_cmd * 100:.0f}%", (240, 240, 240), False),
            (f"Direção: {math.degrees(steer_cmd):.1f}°", (240, 240, 240), False),
            (f"Pista: {track_source} ({track_width_m}m)", (0, 255, 128) if track_source == "csv" else (255, 165, 0), False)
        ]
        
        y_pos = 20
        for text, color, bold in hud_lines:
            txt_surf = font_bold.render(text, True, color) if bold else font.render(text, True, color)
            screen.blit(txt_surf, (25, y_pos))
            y_pos += 22

        # Alerta visual de FORA DA PISTA (Off-Track)
        if is_off_track:
            alert_surf = font_alert.render("⚠️ FORA DA PISTA (OFF-TRACK) ⚠️", True, (255, 40, 40))
            screen.blit(alert_surf, (screen_w // 2 - alert_surf.get_width() // 2, 20))

        pygame.display.flip()
        clock.tick(50)

    print("\nEncerrando e exportando volta...")
    pygame.quit()
    export_run()
    print("Concluído!")

if __name__ == "__main__":
    main()
