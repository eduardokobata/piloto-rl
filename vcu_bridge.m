% vcu_bridge.m — roda no PC com Simulink (fora do Docker, fora do servidor).
%
% Loop: le o estado do carro no Container 3 (HTTP), passa pro modelo
% Simulink, pega os comandos calculados, manda de volta via /step.
%
% Pre-requisito: nenhum pacote Python. So MATLAB com Simulink carregado.
% Ajustar DIL_URL pro IP real do servidor.

DIL_URL = "http://localhost:8090";  % mesma maquina agora (Docker Desktop publica a porta em localhost)
MODEL_NAME = "vcu_control";               % nome do .slx, sem extensao
DT = 0.02;

% Parametros do carro, devem bater com container3_dil/dil_container/physics.py
MASS_KG = 220.0;
MAX_MOTOR_FORCE_N = 4000.0;
MAX_BRAKE_FORCE_N = 6000.0;

REF_PATH_FILE = "mod_din_mlt\output\Trajetoria_Stanley_vovozinha.mat";
ref = load(REF_PATH_FILE);
disp(fieldnames(ref));  % ja confirmado: Ref_X, Ref_Y, Ref_Theta, Ref_V_Estatico,
                         % Ref_V_Lancado, Pose_Timeseries, V_Timeseries, Tempo_Total

load_system(MODEL_NAME);

% Inicia a simulação em modo pausado para compilar o modelo de forma síncrona
fprintf("Compilando e inicializando o modelo Simulink '%s'...\n", MODEL_NAME);
set_param(MODEL_NAME, 'SimulationCommand', 'pause');

% Aguarda o modelo compilar e entrar em modo 'paused'
while true
    status = get_param(MODEL_NAME, 'SimulationStatus');
    if strcmp(status, 'paused') || strcmp(status, 'running')
        break;
    end
    pause(0.1);
end
fprintf("Modelo compilado e pronto (Status: %s).\n", status);
 
% reset do episodio no container3
webwrite(DIL_URL + "/reset", struct("source_label", "piloto"));

try
    while true
        % 1. le estado atual do carro
        state = webread(DIL_URL + "/state");

        % 2. acha o ponto mais proximo na trajetoria de referencia (isso
        %    substitui o HelperPathAnalyzer do exemplo oficial da MathWorks
        %    — feito aqui no MATLAB puro, fora do Simulink, pra nao precisar
        %    montar esse bloco no diagrama)
        dists = hypot(ref.Ref_X - state.x, ref.Ref_Y - state.y);
        [~, idx] = min(dists);
        ref_pose_x = ref.Ref_X(idx);
        ref_pose_y = ref.Ref_Y(idx);
        ref_pose_yaw = ref.Ref_Theta(idx);  % ja vem pronto no .mat, nao precisa calcular
        % NOTA: usando Ref_V_Lancado (volta lancada/rolling) como referencia
        % de velocidade — troque para Ref_V_Estatico se o objetivo for
        % largada parada em vez de volta em andamento.
        ref_vel = ref.Ref_V_Lancado(idx);

        % 3. injeta no workspace do modelo — via Inport blocks conectados
        %    diretamente aos dois blocos Stanley (ver instrucoes no chat)
        assignin('base', 'pose_x', state.x);
        assignin('base', 'pose_y', state.y);
        assignin('base', 'pose_yaw', rad2deg(state.heading_rad));  % blocos trabalham em GRAUS
        assignin('base', 'curr_vel', state.speed_mps);
        assignin('base', 'ref_pose_x', ref_pose_x);
        assignin('base', 'ref_pose_y', ref_pose_y);
        assignin('base', 'ref_pose_yaw', rad2deg(ref_pose_yaw));
        assignin('base', 'ref_vel', ref_vel);

        % 4. avanca um passo de simulacao
        set_param(MODEL_NAME, 'SimulationCommand', 'step');

        % 5. le os comandos calculados — SteerCmd em GRAUS, AccelCmd/DecelCmd
        %    em m/s^2 (portas separadas, so uma delas != 0 por vez)
        steer_cmd_deg = get_param([MODEL_NAME '/steer_cmd'], 'RuntimeObject').OutputPort(1).Data;
        accel_cmd = get_param([MODEL_NAME '/accel_cmd'], 'RuntimeObject').OutputPort(1).Data;
        decel_cmd = get_param([MODEL_NAME '/decel_cmd'], 'RuntimeObject').OutputPort(1).Data;

        % 6. converte pro contrato do container3 (radianos, torque/freio
        %    normalizados -1..1 / 0..1 — ver physics.py)
        steer_cmd = deg2rad(steer_cmd_deg);
        torque_cmd = max(-1, min(1, accel_cmd * MASS_KG / MAX_MOTOR_FORCE_N));
        brake_cmd = max(0, min(1, decel_cmd * MASS_KG / MAX_BRAKE_FORCE_N));

        % 7. manda pro container3
        cmd = struct("torque_cmd", torque_cmd, "brake_cmd", brake_cmd, "steer_cmd", steer_cmd);
        resp = webwrite(DIL_URL + "/step", cmd);

        if resp.lap_closed
            fprintf("Volta fechada! lap_count=%d\n", resp.lap_count);
        end

        pause(DT);
    end
catch ME
    fprintf("Parado: %s\n", ME.message);
end

webwrite(DIL_URL + "/export", struct());
set_param(MODEL_NAME, 'SimulationCommand', 'stop');