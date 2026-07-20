% vcu_bridge.m — Roda no PC com Simulink (fora do Docker, fora do servidor).
%
% Loop: lê o estado do carro no Container 3 (HTTP), passa pro modelo
% Simulink, pega os comandos calculados, manda de volta via /step.

DIL_URL = "http://localhost:8090";  % Docker Desktop publica a porta 8090 em localhost
MODEL_NAME = "vcu_control";          % Nome do .slx, sem extensão
DT = 0.02;                           % 50 Hz (deve bater com physics.py)

% Parâmetros do carro (devem bater com container3_dil/dil_container/physics.py)
MASS_KG = 220.0;
MAX_MOTOR_FORCE_N = 4000.0;
MAX_BRAKE_FORCE_N = 6000.0;

% 1. Verifica existência do arquivo de trajetória
REF_PATH_FILE = fullfile("mod_din_mlt", "output", "Trajetoria_Stanley_vovozinha.mat");
if ~isfile(REF_PATH_FILE)
    % Fallback para Trajetoria_Stanley.mat caso o nome com vovozinha não exista
    REF_PATH_FILE = fullfile("mod_din_mlt", "output", "Trajetoria_Stanley.mat");
end

if ~isfile(REF_PATH_FILE)
    error("Arquivo de trajetória não encontrado em 'mod_din_mlt/output/'. Execute o container mod-din-mlt primeiro.");
end

ref = load(REF_PATH_FILE);

% 2. Carrega e compila o modelo Simulink
if ~exist(MODEL_NAME, 'file') && ~bdIsLoaded(MODEL_NAME)
    error("O arquivo do modelo '%s.slx' não foi encontrado na pasta atual (%s) nem no Path do MATLAB.", MODEL_NAME, pwd);
end

load_system(MODEL_NAME);

% Compila o modelo de forma síncrona (inicia pausado no t=0)
fprintf("Compilando e inicializando o modelo Simulink '%s'...\n", MODEL_NAME);
set_param(MODEL_NAME, 'SimulationCommand', 'pause');

while true
    status = get_param(MODEL_NAME, 'SimulationStatus');
    if strcmp(status, 'paused') || strcmp(status, 'running')
        break;
    elseif strcmp(status, 'stopped')
        error("O Simulink parou durante a compilação do modelo '%s'. Verifique se há erros no diagrama.", MODEL_NAME);
    end
    pause(0.1);
end
fprintf("Modelo compilado e pronto (Status: %s).\n", status);

% 3. Localiza os blocos de saída UMA ÚNICA VEZ antes de entrar no loop (otimização de performance)
steer_b = find_system(MODEL_NAME, 'Type', 'Block', 'Name', 'steer_cmd');
accel_b = find_system(MODEL_NAME, 'Type', 'Block', 'Name', 'accel_cmd');
decel_b = find_system(MODEL_NAME, 'Type', 'Block', 'Name', 'decel_cmd');

if isempty(steer_b) || isempty(accel_b) || isempty(decel_b)
    fprintf("\n[ERRO DE BLOCO] Um ou mais blocos de saída ('steer_cmd', 'accel_cmd', 'decel_cmd') não foram encontrados!\n");
    fprintf("Blocos disponíveis no modelo '%s':\n", MODEL_NAME);
    disp(find_system(MODEL_NAME, 'Type', 'Block'));
    set_param(MODEL_NAME, 'SimulationCommand', 'stop');
    error("Ajuste os nomes dos blocos no Simulink para corresponderem.");
end

steer_path = steer_b{1};
accel_path = accel_b{1};
decel_path = decel_b{1};

% Reset do episódio no container3
try
    webwrite(DIL_URL + "/reset", struct("source_label", "piloto"));
catch
    warning("Não foi possível conectar ao DIL em %s. Verifique se o container3-dil está rodando.", DIL_URL);
end

% 4. Loop de controle em tempo real (50 Hz)
try
    while true
        t_start = tic;

        % A. Lê estado atual do carro
        state = webread(DIL_URL + "/state");

        % B. Encontra o waypoint mais próximo na trajetória de referência
        dists = hypot(ref.Ref_X - state.x, ref.Ref_Y - state.y);
        [~, idx] = min(dists);
        
        ref_pose_x   = ref.Ref_X(idx);
        ref_pose_y   = ref.Ref_Y(idx);
        ref_pose_yaw = ref.Ref_Theta(idx);
        ref_vel      = ref.Ref_V_Lancado(idx);

        % C. Injeta variáveis no workspace base do MATLAB para os blocos do Simulink
        assignin('base', 'pose_x', state.x);
        assignin('base', 'pose_y', state.y);
        assignin('base', 'pose_yaw', rad2deg(state.heading_rad));  % Blocos trabalham em GRAUS
        assignin('base', 'curr_vel', state.speed_mps);
        assignin('base', 'ref_pose_x', ref_pose_x);
        assignin('base', 'ref_pose_y', ref_pose_y);
        assignin('base', 'ref_pose_yaw', rad2deg(ref_pose_yaw));
        assignin('base', 'ref_vel', ref_vel);

        % D. Avança um passo de simulação no Simulink
        set_param(MODEL_NAME, 'SimulationCommand', 'step');

        % E. Lê os sinal dos blocos de saída via RuntimeObject
        steer_rto = get_param(steer_path, 'RuntimeObject');
        accel_rto = get_param(accel_path, 'RuntimeObject');
        decel_rto = get_param(decel_path, 'RuntimeObject');

        if isempty(steer_rto)
            error("RuntimeObject do bloco '%s' não está ativo. O Simulink pode ter parado.", steer_path);
        end

        steer_cmd_deg = steer_rto.InputPort(1).Data;
        accel_cmd     = accel_rto.InputPort(1).Data;
        decel_cmd     = decel_rto.InputPort(1).Data;

        % F. Converte comandos para o contrato do container3 (-1..1 / 0..1 / radianos)
        steer_cmd  = deg2rad(steer_cmd_deg);
        torque_cmd = max(-1, min(1, accel_cmd * MASS_KG / MAX_MOTOR_FORCE_N));
        brake_cmd  = max(0, min(1, decel_cmd * MASS_KG / MAX_BRAKE_FORCE_N));

        % G. Envia comandos ao container3
        cmd = struct("torque_cmd", torque_cmd, "brake_cmd", brake_cmd, "steer_cmd", steer_cmd);
        resp = webwrite(DIL_URL + "/step", cmd);

        if resp.lap_closed
            fprintf("Volta fechada! Voltas concluídas: %d\n", resp.lap_count);
        end

        % Mantém a cadência de 50 Hz compensando o tempo de processamento
        elapsed = toc(t_start);
        pause_time = max(0, DT - elapsed);
        pause(pause_time);
    end
catch ME
    fprintf("\n[EXECUÇÃO INTERROMPIDA]: %s\n", ME.message);
end

% 5. Finalização limpa
try
    webwrite(DIL_URL + "/export", struct());
    fprintf("Telemetria exportada no container3.\n");
catch
end

if bdIsLoaded(MODEL_NAME)
    set_param(MODEL_NAME, 'SimulationCommand', 'stop');
    fprintf("Simulink '%s' parado de forma limpa.\n", MODEL_NAME);
end