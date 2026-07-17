import numpy as np
import pandas as pd
import scipy.io as sio
import matplotlib
matplotlib.use('Agg') #pra rodar sem interface grafica no Docker
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
 
# =============================================================================
# 1. FUNÇÃO DE GERAÇÃO DA PISTA (SPLINE)
# =============================================================================
def carregar_pista_csv(path, ds=0.5, suavizacao=0.0, fechar_loop=None):
    df = pd.read_csv(path)
    x_raw = df['X'].values
    y_raw = df['Y'].values
 
    if fechar_loop is None:
        dist_fechamento = np.hypot(x_raw[-1]-x_raw[0], y_raw[-1]-y_raw[0])
        fechar_loop = dist_fechamento < 2.0
 
    per = 1 if fechar_loop else 0
    tck, u = splprep([x_raw, y_raw], s=suavizacao, per=per, k=3)
 
    u_fine = np.linspace(0, 1, 5000)
    x_fine, y_fine = splev(u_fine, tck)
    ds_fine = np.hypot(np.diff(x_fine), np.diff(y_fine))
    comprimento_total = np.sum(ds_fine)
 
    n_points = int(comprimento_total / ds)
    s = np.linspace(0, comprimento_total, n_points)
 
    s_acumulado = np.concatenate([[0], np.cumsum(ds_fine)])
    u_de_s = np.interp(s, s_acumulado, u_fine)
 
    x, y = splev(u_de_s, tck)
    dx, dy = splev(u_de_s, tck, der=1)
    ddx, ddy = splev(u_de_s, tck, der=2)
 
    num = dx*ddy - dy*ddx
    den = (dx**2 + dy**2)**1.5
    den[den < 1e-9] = 1e-9
    kappa = num / den
 
    print("\n" + "="*50)
    print("MÓDULO DE PISTA: DADOS CARREGADOS")
    print("="*50)
    print(f"Comprimento: {comprimento_total:.1f} m | {'FECHADA' if fechar_loop else 'ABERTA'}")
    print(f"Resolução: {n_points} pontos (ds = {ds} m)")
    print(f"Curva mais fechada: Raio = {1/np.max(np.abs(kappa)):.1f} m")
 
    return s, kappa, x, y, fechar_loop
 
# =============================================================================
# 2. CARREGAMENTO DO ENVELOPE G-G-V
# =============================================================================
path_ggv = 'content/GG_Multiplas_Velocidades_Resultado.mat'
 
try:
    dados_mat = sio.loadmat(path_ggv)
    struct_array = dados_mat['Resultados_GG']
 
    v_lista, ax_max_lista, ax_min_lista, ay_lim_lista = [], [], [], []
 
    print("\n" + "="*50)
    print("MÓDULO DE DINÂMICA: LENDO ENVELOPE G-G-V")
    print("="*50)
    for i in range(struct_array.shape[1]):
        item = struct_array[0, i]
        v_val = item['V0'][0, 0]
        ax_vetor = item['b_ax'].flatten()
        ay_vetor = item['b_ay'].flatten()
 
        ax_max = np.nanmax(ax_vetor)
        ax_min = np.nanmin(ax_vetor)
        ay_max = np.nanmax(np.abs(ay_vetor))
 
        v_lista.append(v_val)
        ax_max_lista.append(ax_max)
        ax_min_lista.append(ax_min)
        ay_lim_lista.append(ay_max)
 
        print(f"V = {v_val} m/s | Ax+ = {ax_max:.2f}g | Ax- = {ax_min:.2f}g | Ay = {ay_max:.2f}g")
 
    v_dados       = np.array(v_lista)
    ax_max_dados  = np.array(ax_max_lista)
    ax_frei_dados = np.abs(np.array(ax_min_lista)) # Deixa positivo para a matemática
    ay_max_dados  = np.array(ay_lim_lista)
 
except Exception as e:
    print(f"Atenção: Não foi possível ler o .mat. Usando dados fictícios. Erro: {e}")
    v_dados = np.array([5, 10, 15, 20])
    ax_max_dados = np.array([12.0, 9.0, 6.0, 4.0])
    ax_frei_dados = np.array([14.7, 14.7, 14.7, 14.7])
    ay_max_dados = np.array([14.5, 14.0, 13.5, 13.0])
 
def obter_limites(v_atual):
    # Fator para correlacionar o limite teórico com a realidade do asfalto
    fator_pista = 1
    ay_lim  = np.interp(v_atual, v_dados, ay_max_dados)
    ax_lim  = np.interp(v_atual, v_dados, ax_max_dados) * fator_pista
    ax_frei = np.interp(v_atual, v_dados, ax_frei_dados)
    return ay_lim, ax_lim, ax_frei
 
# =============================================================================
# 3. SIMULAÇÃO QSS UNIVERSAL (LTS)
# =============================================================================
def simulacao_lts_completa(s, kappa, x, y, ds, fechar_loop):
    print("\n" + "="*50)
    print("INICIANDO INTEGRAÇÃO DE TEMPO DE VOLTA (QSS)...")
    print("="*50)
 
    n_points = len(s)
    v_profile = np.zeros(n_points)
    ax_profile = np.zeros(n_points)
    ay_profile = np.zeros(n_points)
    v_max_absoluta = np.max(v_dados) if np.max(v_dados) > 0 else 30.0
 
    # 3.1 LIMITES DE ÁPICE (Velocidade máxima possível em cada curva)
    for i in range(n_points):
        k_abs = abs(kappa[i]) # Curvas para os dois lados!
        if k_abs > 1e-5:
            v_teste = np.linspace(1.0, v_max_absoluta, 200)
            v_valida = 1.0
            for v in v_teste:
                ay_disp, _, _ = obter_limites(v)
                if (v ** 2) * k_abs <= ay_disp:
                    v_valida = v
            v_profile[i] = v_valida
        else:
            v_profile[i] = v_max_absoluta
 
    # 3.2 INTEGRAÇÃO FORWARD (Acelerando)
    # =========================================================
    # INTEGRAÇÃO QSS - LOOP DUPLO PARA VOLTA LANÇADA (ENDURO)
    # =========================================================
 
    # Vamos rodar a integração 2 vezes.
    # A 1ª vez resolve a pista. A 2ª vez costura o final com o começo.
    passos_integracao = 2 if fechar_loop else 1
    v_profile[0] = 0.1
 
    # Criamos variáveis vazias para guardar os dois mundos
    v_profile_estatico = np.zeros(n_points)
 
    for iteracao in range(passos_integracao):
 
        if iteracao == 1:
            # Antes de sobrescrever, salva a Volta 1 (Largada)
            v_profile_estatico = np.copy(v_profile)
            # Prepara o vetor para a Volta 2 (Lançada)
            v_profile[0] = v_profile[-1]
 
        # 3.2 INTEGRAÇÃO FORWARD (Acelerando)
        for i in range(n_points - 1):
            v_atual = v_profile[i]
            ay_lim, ax_trac, _ = obter_limites(v_atual)
            ay_req = (v_atual ** 2) * abs(kappa[i])
            if ay_req >= ay_lim: ax_disp = 0.0
            else: ax_disp = ax_trac * np.sqrt(1 - (ay_req / ay_lim) ** 2)
            v_prox = np.sqrt(v_atual ** 2 + 2 * ax_disp * ds)
            v_profile[i + 1] = min(v_profile[i + 1], v_prox)
 
        # 3.3 INTEGRAÇÃO BACKWARD (Freando)
        for i in range(n_points - 1, 0, -1):
            v_atual = v_profile[i]
            ay_lim, _, ax_frei = obter_limites(v_atual)
            ay_req = (v_atual ** 2) * abs(kappa[i])
            if ay_req >= ay_lim: ax_disp = 0.0
            else: ax_disp = ax_frei * np.sqrt(1 - (ay_req / ay_lim) ** 2)
            v_ant = np.sqrt(v_atual ** 2 + 2 * ax_disp * ds)
            v_profile[i - 1] = min(v_profile[i - 1], v_ant)
 
    # Salva a Volta 2 (Lançada)
    v_profile_lancado = np.copy(v_profile)
    if passos_integracao == 1: # Se não for loop, as duas são iguais
        v_profile_estatico = np.copy(v_profile)
    # 3.4 CÁLCULO DE TEMPO E ACELERAÇÕES REAIS NA VOLTA
    v_media = (v_profile[:-1] + v_profile[1:]) / 2.0
    v_media[v_media < 0.1] = 0.1 # Proteção
    dt = ds / v_media
    tempo_total = np.sum(dt)
 
    ax_profile[0] = 0
    for i in range(1, n_points):
        ax_profile[i] = (v_profile[i] - v_profile[i-1]) / dt[i-1]
 
    ay_profile = (v_profile ** 2) * kappa
 
    print(f">> TEMPO DE VOLTA: {tempo_total:.3f} segundos")
    print(f">> Velocidade Média: {np.mean(v_profile) * 3.6:.1f} km/h")
    print(f">> Velocidade Máxima Atingida: {np.max(v_profile) * 3.6:.1f} km/h")
    print("="*50 + "\n")
 
    # =========================================================================
    # 3.4.5 EXTRAÇÃO DE DADOS PARA O SIMULINK (CONTROLE STANLEY)
    # =========================================================================
 
    # 1. Criação do Vetor de Tempo Cumulativo
    t_array = np.zeros(n_points)
    for i in range(1, n_points):
        t_array[i] = t_array[i-1] + dt[i-1]
 
    # 2. Cálculo do Ângulo da Pista (Heading - Theta)
    # Derivada da posição para encontrar para onde a pista aponta
    dx = np.gradient(x)
    dy = np.gradient(y)
    theta = np.arctan2(dy, dx)
    theta = np.unwrap(theta) # Impede o pulo de 180 para -180 graus nas curvas
 
    # 3. Matrizes formatadas em Colunas para uso geral (Waypoints)
    Ref_X = x.reshape(-1, 1)
    Ref_Y = y.reshape(-1, 1)
    Ref_Theta = theta.reshape(-1, 1)
    Ref_V = v_profile.reshape(-1, 1)
 
    # 4. Matrizes de Tempo Nx4 e Nx2 para blocos "From Workspace" no Simulink
    # Se o bloco do Stanley pedir "Pose", geralmente ele espera [X, Y, Theta]
    Pose_Timeseries = np.column_stack((t_array, x, y, theta))
    V_Timeseries = np.column_stack((t_array, v_profile))
 
    sio.savemat('output/Trajetoria_Stanley_vovozinha.mat', {
        'Ref_X': Ref_X,
        'Ref_Y': Ref_Y,
        'Ref_Theta': Ref_Theta,
        'Ref_V_Estatico': v_profile_estatico.reshape(-1,1),
        'Ref_V_Lancado': v_profile_lancado.reshape(-1,1),
        'Pose_Timeseries': Pose_Timeseries,
        'V_Timeseries': V_Timeseries,
        'Tempo_Total': tempo_total
    })
 
    print(">> EXPORTAÇÃO: 'Trajetoria_Stanley.mat' salvo com sucesso no diretorio output!")
    # =========================================================================
 
    # 3.5 GRÁFICOS E MAPA DE CALOR
 
    # Gráfico 1: Velocidade e Curvatura
    fig1, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(s, v_profile * 3.6, 'b-', linewidth=2.5, label='Velocidade (km/h)')
    ax1.set_xlabel('Distância Percorrida (m)')
    ax1.set_ylabel('Velocidade (km/h)', color='b')
    ax1.grid(True)
    ax1.legend(loc='upper left')
 
    ax2 = ax1.twinx()
    ax2.fill_between(s, 0, np.abs(kappa), color='red', alpha=0.15, label='Curvatura')
    ax2.set_ylabel('Curvatura Absoluta', color='r')
    ax2.set_ylim(0, max(np.abs(kappa)) * 1.5)
    plt.title('Perfil de Velocidade')
 
    # Gráfico 2: Aceleração Longitudinal (g) e Curvatura
    g = 9.81
    fig_ax, ax3 = plt.subplots(figsize=(10, 4))
    ax3.plot(s, ax_profile / g, 'g-', linewidth=2.0, label='Ax Longitudinal (g)')
    ax3.axhline(0, color='k', linestyle='--', alpha=0.5) # Linha do zero
    ax3.set_xlabel('Distância Percorrida (m)')
    ax3.set_ylabel('Aceleração Longitudinal (g)', color='g')
    ax3.grid(True)
    ax3.legend(loc='upper left')
 
    ax4 = ax3.twinx()
    ax4.fill_between(s, 0, np.abs(kappa), color='red', alpha=0.15, label='Curvatura')
    ax4.set_ylabel('Curvatura Absoluta', color='r')
    ax4.set_ylim(0, max(np.abs(kappa)) * 1.5)
    plt.title('Perfil de Aceleração Longitudinal')
 
    # Gráfico 3: Mapa de Calor Velocidade
    fig2, ax_map = plt.subplots(figsize=(10, 8))
    sc = ax_map.scatter(x, y, c=(v_profile * 3.6), cmap='jet', s=15, zorder=2)
    cbar = plt.colorbar(sc, ax=ax_map, fraction=0.046, pad=0.04)
    cbar.set_label('Velocidade (km/h)')
 
    ax_map.plot(x[0], y[0], 'go', markersize=10, markeredgecolor='k', label='Largada')
 
    ax_map.set_aspect('equal', 'box')
    ax_map.set_xlabel('Posição X (m)')
    ax_map.set_ylabel('Posição Y (m)')
    ax_map.set_title('Mapa de Velocidade: Autocross')
    ax_map.legend()
    ax_map.grid(True, linestyle='--', alpha=0.6)
 
    # Gráfico 4: Mapa de Calor Aceleração Longitudinal
    fig3, ax_map_ax = plt.subplots(figsize=(10, 8))
    # Usando cmap 'coolwarm' onde vermelho é aceleração e azul é frenagem
    sc_ax = ax_map_ax.scatter(x, y, c=(ax_profile / g), cmap='coolwarm', s=15, zorder=2)
    cbar_ax = plt.colorbar(sc_ax, ax=ax_map_ax, fraction=0.046, pad=0.04)
    cbar_ax.set_label('Aceleração Longitudinal Ax (g)')
 
    ax_map_ax.plot(x[0], y[0], 'go', markersize=10, markeredgecolor='k', label='Largada')
 
    ax_map_ax.set_aspect('equal', 'box')
    ax_map_ax.set_xlabel('Posição X (m)')
    ax_map_ax.set_ylabel('Posição Y (m)')
    ax_map_ax.set_title('Mapa de Aceleração Longitudinal: Enduro')
    ax_map_ax.legend()
    ax_map_ax.grid(True, linestyle='--', alpha=0.6)
 
    #plt.show()
    fig1.savefig('output/perfil_velocidade.png', bbox_inches='tight')
    fig_ax.savefig('output/perfil_aceleracao.png', bbox_inches='tight')
    fig2.savefig('output/mapa_velocidade.png', bbox_inches='tight')
    fig3.savefig('output/mapa_aceleracao.png', bbox_inches='tight')
    print(">> EXPORTAÇÃO: Gráficos salvos com sucesso no diretorio 'output'!")
 
# =============================================================================
# 4. EXECUÇÃO PRINCIPAL DO SCRIPT
# =============================================================================
if __name__ == "__main__":
    # Caminho do seu CSV (Ajuste se for Enduro, Autocross, etc)
    caminho_pista = 'content/Pista_Auto_X_FSAE.csv'
 
    # Parâmetro ds = 0.5 (Resolve a pista de meio em meio metro)
    ds_simulacao = 0.5
 
    # 1. Carrega e limpa a pista
    s_pista, kappa_pista, x_pista, y_pista, pista_fechada = carregar_pista_csv(
        path=caminho_pista,
        ds=ds_simulacao,
        suavizacao=0.0
    )
 
    # 2. Executa o simulador
    simulacao_lts_completa(s_pista, kappa_pista, x_pista, y_pista, ds=ds_simulacao, fechar_loop=pista_fechada)