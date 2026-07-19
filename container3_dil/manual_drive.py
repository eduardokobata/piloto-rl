#!/usr/bin/env python3
"""
manual_drive.py — Controle manual (teclado) para o Container 3 (DIL simplificado).

Requisitos:
- pygame
- requests
- numpy (opcional, não obrigatório para rodar o drive)
"""

import sys
import os
import math
import time
import requests
import pygame

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
        # Usando os caminhos padrão do volume compartilhado do Docker Compose
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
    track_source = track_info.get("track_source", "desconhecido")
    
    if not points:
        print("Erro: A pista retornada pelo DIL está vazia!")
        sys.exit(1)
        
    print(f"Pista carregada com sucesso! Fonte: {track_source} | {len(points)} pontos.")

    # 2. Inicializa o estado do Simulador
    initial_state = reset_simulation()
    
    # 3. Inicializa o Pygame
    pygame.init()
    pygame.font.init()
    
    screen_w, screen_h = 800, 600
    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("Eracing - Piloto IA: Manual Drive")
    clock = pygame.time.Clock()
    
    # Configura fontes modernas/legíveis
    try:
        font = pygame.font.SysFont("Outfit", 20)
        font_bold = pygame.font.SysFont("Outfit", 24, bold=True)
    except Exception:
        font = pygame.font.Font(None, 24)
        font_bold = pygame.font.Font(None, 28)

    # Coordenadas limites da pista para fazer a escala
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    track_w = max_x - min_x
    track_h = max_y - min_y
    
    margin = 60
    # Calcula fator de escala preservando proporção (aspect ratio)
    scale_x = (screen_w - 2 * margin) / max(track_w, 1e-5)
    scale_y = (screen_h - 2 * margin) / max(track_h, 1e-5)
    scale = min(scale_x, scale_y)
    
    # Centralização
    offset_x = margin + (screen_w - 2 * margin - track_w * scale) / 2
    offset_y = margin + (screen_h - 2 * margin - track_h * scale) / 2
    
    def to_screen(x, y):
        # Inverte eixo Y do cartesiano para a tela do pygame
        sx = offset_x + (x - min_x) * scale
        sy = offset_y + (max_y - y) * scale
        return int(sx), int(sy)

    # Pré-calcula os pontos da pista em coordenadas de tela para desenhar rápido
    screen_points = [to_screen(p[0], p[1]) for p in points]

    # Estado inicial do veículo no loop
    car_x = initial_state.get("x", 0.0)
    car_y = initial_state.get("y", 0.0)
    car_heading = initial_state.get("heading_rad", 0.0)
    car_speed = initial_state.get("speed_mps", 0.0)
    lap_count = 0

    # Variáveis de controle dinâmico de direção por teclado (rampa)
    steer_cmd = 0.0
    max_steer = 0.4      # rad (~23 graus)
    ramp_speed = 1.5     # rad/s
    center_speed = 2.0   # rad/s
    dt = 0.02            # DIL Simulator roda a 50Hz (dt = 0.02)
    
    running = True
    print("\n--- INSTRUÇÕES DE CONTROLE ---")
    print("Seta para CIMA    : Acelerar (torque_cmd)")
    print("Seta para BAIXO   : Frear (brake_cmd)")
    print("Seta ESQUERDA/DIR : Esterçar (steer_cmd)")
    print("ESC / Fechar jan. : Sair e exportar corrida")
    print("------------------------------\n")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # Leitura das teclas para controle
        keys = pygame.key.get_pressed()
        
        # Aceleração e Frenagem
        if keys[pygame.K_UP]:
            torque_cmd = 1.0
        else:
            torque_cmd = 0.0
            
        if keys[pygame.K_DOWN]:
            brake_cmd = 1.0
        else:
            brake_cmd = 0.0

        # Esterçamento com rampa e centralização automática
        if keys[pygame.K_LEFT]:
            steer_cmd = max(-max_steer, steer_cmd - ramp_speed * dt)
        elif keys[pygame.K_RIGHT]:
            steer_cmd = min(max_steer, steer_cmd + ramp_speed * dt)
        else:
            if steer_cmd > 0:
                steer_cmd = max(0.0, steer_cmd - center_speed * dt)
            elif steer_cmd < 0:
                steer_cmd = min(0.0, steer_cmd + center_speed * dt)

        # Envia comando para a simulação e lê o novo estado
        step_result = send_step(torque_cmd, brake_cmd, steer_cmd)
        if step_result:
            state = step_result.get("state", {})
            car_x = state.get("x", car_x)
            car_y = state.get("y", car_y)
            car_heading = state.get("heading_rad", car_heading)
            car_speed = state.get("speed_mps", car_speed)
            lap_count = step_result.get("lap_count", lap_count)

        # --- RENDERIZAÇÃO ---
        # Fundo escuro (charcoal premium)
        screen.fill((18, 18, 18))
        
        # Desenha a pista como uma linha fechada
        if len(screen_points) > 1:
            pygame.draw.lines(screen, (0, 200, 255), True, screen_points, 3)
            
            # Ponto de partida (verde neon)
            pygame.draw.circle(screen, (0, 255, 100), screen_points[0], 6)
            
        # Desenha o carro (Círculo vermelho neon + linha amarela de heading)
        car_screen = to_screen(car_x, car_y)
        pygame.draw.circle(screen, (255, 50, 50), car_screen, 9)
        
        # Desenha linha de heading
        line_len = 16
        heading_x = car_x + (line_len / scale) * math.cos(car_heading)
        heading_y = car_y + (line_len / scale) * math.sin(car_heading)
        pygame.draw.line(screen, (255, 215, 0), car_screen, to_screen(heading_x, heading_y), 3)

        # HUD / Painel de Informações
        hud_bg = pygame.Surface((250, 160))
        hud_bg.set_alpha(180)
        hud_bg.fill((30, 30, 30))
        screen.blit(hud_bg, (15, 15))
        
        # Renderização do texto no painel
        hud_lines = [
            ("Eracing DIL Status", (0, 200, 255), True),
            (f"Velocidade: {car_speed * 3.6:.1f} km/h", (240, 240, 240), False),
            (f"Voltas: {lap_count}", (240, 240, 240), False),
            (f"Torque: {torque_cmd * 100:.0f}%", (240, 240, 240), False),
            (f"Freio: {brake_cmd * 100:.0f}%", (240, 240, 240), False),
            (f"Direção: {math.degrees(steer_cmd):.1f}°", (240, 240, 240), False),
            (f"Pista: {track_source}", (0, 255, 100) if track_source == "csv" else (255, 165, 0), False)
        ]
        
        y_pos = 20
        for text, color, bold in hud_lines:
            txt_surf = font_bold.render(text, True, color) if bold else font.render(text, True, color)
            screen.blit(txt_surf, (25, y_pos))
            y_pos += 20

        pygame.display.flip()
        clock.tick(50) # 50 FPS (corresponde a dt = 0.02s)

    # 4. Finalização e Exportação
    print("\nEncerrando e exportando volta...")
    pygame.quit()
    export_run()
    print("Concluído!")

if __name__ == "__main__":
    main()
