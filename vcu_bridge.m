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

% Trajetoria de referencia do MLT (Container 2), ja pensada pra Stanley
% (repare no nome do arquivo). Carrega UMA VEZ, nao a cada loop.
REF_PATH_FILE = "..\mod_din_mlt\output\Trajetoria_Stanley_vovozinha.mat";
ref = load(REF_PATH_FILE);
% ref deve conter algo como ref.x, ref.y, ref.v_ref (ajustar nomes dos
% campos reais depois de conferir o .mat com `load(REF_PATH_FILE)` e
% `fieldnames(ref)` no MATLAB) — injete isso no workspace/bloco do Stanley
% controller ANTES de iniciar o loop, ex:
% set_param([MODEL_NAME '/ref_path_x'], 'Value', mat2str(ref.x));
% set_param([MODEL_NAME '/ref_path_y'], 'Value', mat2str(ref.y));

load_system(MODEL_NAME);
set_param(MODEL_NAME, 'SimulationCommand', 'start');

% reset do episodio no container3
webwrite(DIL_URL + "/reset", struct("source_label", "piloto"));

try
    while true
        % 1. le estado atual do carro
        state = webread(DIL_URL + "/state");

        % 2. injeta no workspace do modelo (ajustar nomes de bloco/sinal
        %    reais do seu .slx — esses sao placeholders)
        set_param([MODEL_NAME '/car_x'], 'Value', num2str(state.x));
        set_param([MODEL_NAME '/car_y'], 'Value', num2str(state.y));
        set_param([MODEL_NAME '/car_speed'], 'Value', num2str(state.speed_mps));
        set_param([MODEL_NAME '/car_heading'], 'Value', num2str(state.heading_rad));
        set_param([MODEL_NAME '/car_yaw_rate'], 'Value', num2str(state.yaw_rate_rad_s));

        % 3. avanca um passo de simulacao
        set_param(MODEL_NAME, 'SimulationCommand', 'step');

        % 4. le os comandos calculados dos DOIS blocos Stanley separados
        %    (ajustar nomes reais de bloco/porta do seu .slx)
        steer_cmd  = get_param([MODEL_NAME '/Lateral Controller Stanley'], 'RuntimeObject').OutputPort(1).Data;
        torque_cmd = get_param([MODEL_NAME '/Longitudinal Controller Stanley'], 'RuntimeObject').OutputPort(1).Data;
        brake_cmd  = get_param([MODEL_NAME '/Longitudinal Controller Stanley'], 'RuntimeObject').OutputPort(2).Data;
        % ^ presumindo que o controlador longitudinal tem 2 saidas (torque, freio)
        %   separadas — se for uma saida so (ex: -1..1, negativo=freio),
        %   ajuste a divisao entre torque_cmd/brake_cmd aqui antes de mandar.

        % 5. manda pro container3
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
