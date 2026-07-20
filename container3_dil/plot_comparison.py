#!/usr/bin/env python3
"""
plot_comparison.py — Gera gráficos comparativos e overlay do entregável (Seção 5 do Checklist):
1. Mapa da Pista + Percurso do Piloto (Humano) + Percurso da VCU (Simulink), sobrepostos.
2. Gráfico de Aceleração Longitudinal (Piloto x VCU).
3. Gráfico de Freio e Torque (Piloto x VCU).
4. Relatório comparativo com tempos de volta e velocidades.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Para salvar imagens sem precisar de servidor X11
import matplotlib.pyplot as plt

def load_data(vcu_path, piloto_path, track_path):
    """Carrega os dados dos logs da VCU, Piloto e Pista."""
    vcu_df = None
    piloto_df = None
    track_df = None

    if os.path.exists(vcu_path):
        vcu_df = pd.read_csv(vcu_path)
        print(f"✓ Log VCU/Simulink carregado: {len(vcu_df)} pontos.")
    else:
        print(f"⚠️ Aviso: Arquivo da VCU ({vcu_path}) não encontrado.")

    if os.path.exists(piloto_path):
        piloto_df = pd.read_csv(piloto_path)
        print(f"✓ Log Piloto Humano carregado: {len(piloto_df)} pontos.")
    else:
        print(f"⚠️ Aviso: Arquivo do Piloto ({piloto_path}) não encontrado.")

    if os.path.exists(track_path):
        track_df = pd.read_csv(track_path)
        print(f"✓ Pista real carregada: {len(track_df)} pontos.")

    return vcu_df, piloto_df, track_df

def generate_comparison_plots(vcu_df, piloto_df, track_df, output_dir="mod_din_mlt/output"):
    """Gera e salva todos os gráficos comparativos."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Define paleta visual moderna/premium (Dark Theme)
    plt.style.use('dark_background')
    color_track = '#4A5568'       # Cinza escuro para a pista
    color_vcu = '#00E5FF'         # Ciano neon para Simulink/VCU
    color_piloto = '#FF0055'      # Rosa/Vermelho neon para Piloto Humano
    
    # -------------------------------------------------------------------------
    # GRÁFICO 1: MAPA DA PISTA + OVERLAY DE TRAJETÓRIAS
    # -------------------------------------------------------------------------
    fig1, ax1 = plt.subplots(figsize=(10, 8), dpi=300)
    
    if track_df is not None:
        x_col = 'X' if 'X' in track_df.columns else 'x'
        y_col = 'Y' if 'Y' in track_df.columns else 'y'
        ax1.plot(track_df[x_col], track_df[y_col], '--', color=color_track, linewidth=1.5, alpha=0.7, label='Linha Central da Pista (SLAM)')
        # Ponto de largada
        ax1.plot(track_df[x_col].iloc[0], track_df[y_col].iloc[0], 'go', markersize=8, label='Largada/Chegada')

    if vcu_df is not None:
        ax1.plot(vcu_df['x'], vcu_df['y'], color=color_vcu, linewidth=2.5, label='Percurso VCU (Simulink)')

    if piloto_df is not None:
        ax1.plot(piloto_df['x'], piloto_df['y'], color=color_piloto, linewidth=2.0, linestyle='-', label='Percurso Piloto (Humano)')

    ax1.set_aspect('equal', 'box')
    ax1.set_title('Sprint Piloto IA — Overlay de Trajetórias (Pista vs VCU vs Piloto)', fontsize=14, pad=15, fontweight='bold', color='white')
    ax1.set_xlabel('Posição X (m)', fontsize=11)
    ax1.set_ylabel('Posição Y (m)', fontsize=11)
    ax1.grid(True, linestyle=':', alpha=0.3)
    ax1.legend(loc='upper right', framealpha=0.8)
    
    overlay_path = os.path.join(output_dir, 'overlay_trajetorias.png')
    fig1.savefig(overlay_path, bbox_inches='tight')
    plt.close(fig1)
    print(f"✓ Gráfico salvo: {overlay_path}")

    # -------------------------------------------------------------------------
    # GRÁFICO 2: PERFIL DE VELOCIDADE (PILOTO VS VCU)
    # -------------------------------------------------------------------------
    fig2, ax2 = plt.subplots(figsize=(12, 5), dpi=300)
    
    if vcu_df is not None:
        vcu_speed_kmh = vcu_df['speed_mps'] * 3.6
        ax2.plot(vcu_df['t'], vcu_speed_kmh, color=color_vcu, linewidth=2.0, label='Velocidade VCU (km/h)')
        
    if piloto_df is not None:
        piloto_speed_kmh = piloto_df['speed_mps'] * 3.6
        ax2.plot(piloto_df['t'], piloto_speed_kmh, color=color_piloto, linewidth=2.0, label='Velocidade Piloto Humano (km/h)')

    ax2.set_title('Comparativo de Perfil de Velocidade (km/h)', fontsize=14, pad=15, fontweight='bold', color='white')
    ax2.set_xlabel('Tempo (s)', fontsize=11)
    ax2.set_ylabel('Velocidade (km/h)', fontsize=11)
    ax2.grid(True, linestyle=':', alpha=0.3)
    ax2.legend(loc='upper right', framealpha=0.8)

    speed_path = os.path.join(output_dir, 'comparativo_velocidade.png')
    fig2.savefig(speed_path, bbox_inches='tight')
    plt.close(fig2)
    print(f"✓ Gráfico salvo: {speed_path}")

    # -------------------------------------------------------------------------
    # GRÁFICO 3: ATUADORES DE ACELERAÇÃO E FREIO (TORQUE & BRAKE CMD)
    # -------------------------------------------------------------------------
    fig3, (ax3_top, ax3_bottom) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, dpi=300)

    # Torque / Aceleração
    if vcu_df is not None:
        ax3_top.plot(vcu_df['t'], vcu_df['torque_cmd'], color=color_vcu, linewidth=2.0, label='Torque VCU (Simulink)')
    if piloto_df is not None:
        ax3_top.plot(piloto_df['t'], piloto_df['torque_cmd'], color=color_piloto, linewidth=2.0, label='Torque Piloto Humano')
    
    ax3_top.set_title('Comando de Aceleração / Torque (-1..1)', fontsize=12, fontweight='bold')
    ax3_top.set_ylabel('Torque Cmd', fontsize=11)
    ax3_top.grid(True, linestyle=':', alpha=0.3)
    ax3_top.legend(loc='upper right')

    # Frenagem
    if vcu_df is not None:
        ax3_bottom.plot(vcu_df['t'], vcu_df['brake_cmd'], color=color_vcu, linewidth=2.0, label='Freio VCU (Simulink)')
    if piloto_df is not None:
        ax3_bottom.plot(piloto_df['t'], piloto_df['brake_cmd'], color=color_piloto, linewidth=2.0, label='Freio Piloto Humano')

    ax3_bottom.set_title('Comando de Frenagem (0..1)', fontsize=12, fontweight='bold')
    ax3_bottom.set_xlabel('Tempo (s)', fontsize=11)
    ax3_bottom.set_ylabel('Brake Cmd', fontsize=11)
    ax3_bottom.grid(True, linestyle=':', alpha=0.3)
    ax3_bottom.legend(loc='upper right')

    actuators_path = os.path.join(output_dir, 'comparativo_atuadores.png')
    fig3.savefig(actuators_path, bbox_inches='tight')
    plt.close(fig3)
    print(f"✓ Gráfico salvo: {actuators_path}")

    # -------------------------------------------------------------------------
    # IMPRESSÃO DA TABELA RESUMO NO TERMINAL
    # -------------------------------------------------------------------------
    print("\n" + "="*60)
    print(" 📊 RESUMO COMPARATIVO TELEMETRIA — SPRINT PILOTO IA")
    print("="*60)

    if vcu_df is not None:
        t_vcu = vcu_df['t'].max() - vcu_df['t'].min()
        v_max_vcu = (vcu_df['speed_mps'] * 3.6).max()
        v_avg_vcu = (vcu_df['speed_mps'] * 3.6).mean()
        print(f" [VCU Simulink]     Tempo Total: {t_vcu:.2f}s | V.Máx: {v_max_vcu:.1f} km/h | V.Média: {v_avg_vcu:.1f} km/h")

    if piloto_df is not None:
        t_piloto = piloto_df['t'].max() - piloto_df['t'].min()
        v_max_piloto = (piloto_df['speed_mps'] * 3.6).max()
        v_avg_piloto = (piloto_df['speed_mps'] * 3.6).mean()
        print(f" [Piloto Humano]    Tempo Total: {t_piloto:.2f}s | V.Máx: {v_max_piloto:.1f} km/h | V.Média: {v_avg_piloto:.1f} km/h")

    print("="*60 + "\n")

if __name__ == "__main__":
    vcu_csv = sys.argv[1] if len(sys.argv) > 1 else "mod_din_mlt/output/run_vcu.csv"
    piloto_csv = sys.argv[2] if len(sys.argv) > 2 else "mod_din_mlt/output/run_piloto.csv"
    track_csv = sys.argv[3] if len(sys.argv) > 3 else "pista_slam.csv"

    # Se run_vcu.csv não existir mas run.csv existir, usa run.csv como vcu
    if not os.path.exists(vcu_csv) and os.path.exists("mod_din_mlt/output/run.csv"):
        vcu_csv = "mod_din_mlt/output/run.csv"

    vcu_data, piloto_data, track_data = load_data(vcu_csv, piloto_csv, track_csv)
    generate_comparison_plots(vcu_data, piloto_data, track_data)
