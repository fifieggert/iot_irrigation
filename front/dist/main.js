"use strict";
const API_URL = APP_CONFIG.apiUrl.replace(/\/+$/, "");
const LIMIAR_LIGA = 30;
const LIMIAR_DESLIGA = 60;
const INTERVALO_MS = 5_000;
const SEM_SINAL_MS = 15_000;
const TOKEN_KEY = "irrigacao_token";
const STATUS = {
    "sem-sinal": ["i-offline", "Sem leituras do ESP32"],
    seco: ["i-alerta", "Irrigação necessária"],
    medio: ["i-info", "Umidade moderada"],
    ok: ["i-ok", "Umidade adequada"],
    irrigando: ["i-gotas", "Irrigando agora"],
};
const ALERTAS = {
    solo_seco: { texto: "Solo seco", tom: "aviso" },
    seguranca: { texto: "Segurança", tom: "critico" },
    sensor: { texto: "Sensor", tom: "critico" },
    comando: { texto: "Comando", tom: "" },
};
const $ = (id) => document.getElementById(id);
const app = document.querySelector(".app");
const botoes = [$("btnIrrigar"), $("btnParar"), $("btnAuto")];
let temLeitura = false;
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}
async function api(caminho, init = {}) {
    const headers = new Headers(init.headers);
    const token = getToken();
    if (token)
        headers.set("Authorization", `Bearer ${token}`);
    const resposta = await fetch(API_URL + caminho, { ...init, headers }).catch(() => {
        throw new Error("Não foi possível falar com a API");
    });
    if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => null);
        throw new Error(typeof corpo?.detail === "string" ? corpo.detail : `Erro ${resposta.status} da API`);
    }
    // 204/empty-safe.
    return resposta.status === 204 ? undefined : resposta.json();
}
// Login OAuth2 (campos username/password em form-urlencoded).
async function login(email, senha) {
    const body = new URLSearchParams({ username: email, password: senha });
    const resposta = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
    });
    if (!resposta.ok)
        throw new Error("E-mail ou senha inválidos");
    const { access_token } = (await resposta.json());
    localStorage.setItem(TOKEN_KEY, access_token);
}
async function garantirLogin() {
    if (getToken())
        return true;
    const email = window.prompt("E-mail de acesso ao painel:");
    if (!email)
        return false;
    const senha = window.prompt("Senha:");
    if (!senha)
        return false;
    try {
        await login(email, senha);
        return true;
    }
    catch (erro) {
        avisar(erro.message);
        return false;
    }
}
function avisar(mensagem) {
    $("banner").hidden = !mensagem;
    $("banner").textContent = mensagem;
}
function definirStatus(nivel) {
    const [icone, texto] = STATUS[nivel];
    $("statusIcone").setAttribute("href", `#${icone}`);
    $("statusTexto").textContent = texto;
}
function mostrarLeitura(leitura) {
    const umidade = Math.round(leitura.umidade);
    const ligada = leitura.estado_bomba === "on";
    const semSinal = Date.now() - Date.parse(leitura.created_at) > SEM_SINAL_MS;
    const nivel = umidade <= LIMIAR_LIGA ? "seco" : umidade < LIMIAR_DESLIGA ? "medio" : "ok";
    app.dataset.nivel = semSinal ? "sem-sinal" : nivel;
    definirStatus(semSinal ? "sem-sinal" : ligada ? "irrigando" : nivel);
    $("valor").textContent = `${umidade}%`;
    $("barraPreenchimento").style.width = `${Math.max(0, Math.min(100, umidade))}%`;
    $("barra").setAttribute("aria-valuenow", String(umidade));
    $("bombaModo").textContent = `Bomba ${ligada ? "ligada" : "desligada"} · Modo ${leitura.modo === "auto" ? "automático" : "manual"}`;
}
function mostrarAlertas(logs) {
    $("semAlertas").hidden = logs.length > 0;
    $("alertas").replaceChildren(...logs.map((log) => {
        // O backend grava a descricao do alerta como "[tipo] mensagem".
        const [, tipo = "", texto = log.descricao] = /^\[([^\]]*)\]\s*(.*)$/.exec(log.descricao) ?? [];
        const rotulo = ALERTAS[tipo] ?? { texto: tipo.replace(/_/g, " "), tom: "" };
        const hora = document.createElement("time");
        hora.dateTime = log.created_at;
        hora.textContent = new Date(log.created_at).toLocaleString("pt-BR");
        const etiqueta = document.createElement("span");
        etiqueta.className = `alert-tipo ${rotulo.tom}`;
        etiqueta.textContent = rotulo.texto ? `${rotulo.texto}: ` : "";
        const item = document.createElement("li");
        item.append(hora, etiqueta, texto);
        return item;
    }));
}
async function atualizar() {
    try {
        const [leituras, alertas] = await Promise.all([
            api("/api/v1/telemetry/soil/history?limit=1"),
            api("/api/v1/logs?tipo=ALERT&limit=8"),
        ]);
        avisar(null);
        const leitura = leituras[0];
        if (leitura) {
            temLeitura = true;
            mostrarLeitura(leitura);
        }
        mostrarAlertas(alertas.items);
    }
    catch (erro) {
        avisar(`${erro.message} (${API_URL}). Tentando novamente…`);
        if (!temLeitura) {
            app.dataset.nivel = "sem-sinal";
            $("statusIcone").setAttribute("href", "#i-offline");
            $("statusTexto").textContent = "Sem conexão com a API";
        }
    }
}
async function enviar(comando) {
    if (!(await garantirLogin()))
        return;
    botoes.forEach((botao) => (botao.disabled = true));
    try {
        await api("/api/v1/command/pump", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ comando }),
        });
    }
    catch (erro) {
        // Token expirado/invalido: limpa e pede login de novo na proxima acao.
        if (erro.message.includes("expirado") || erro.message.includes("inválid")) {
            localStorage.removeItem(TOKEN_KEY);
        }
        avisar(erro.message);
    }
    finally {
        botoes.forEach((botao) => (botao.disabled = false));
    }
}
$("btnIrrigar").addEventListener("click", () => void enviar("on"));
$("btnParar").addEventListener("click", () => void enviar("off"));
$("btnAuto").addEventListener("click", () => void enviar("auto"));
void atualizar();
setInterval(() => void atualizar(), INTERVALO_MS);
//# sourceMappingURL=main.js.map