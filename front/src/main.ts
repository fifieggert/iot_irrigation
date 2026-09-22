declare const APP_CONFIG: { apiUrl: string };

const API_URL = APP_CONFIG.apiUrl.replace(/\/+$/, "");
const LIMIAR_LIGA = 30;
const LIMIAR_DESLIGA = 60;
const INTERVALO_MS = 5_000;
const SEM_SINAL_MS = 15_000;

interface Telemetria {
  umidade: number;
  estado_bomba: string;
  modo: string | null;
  timestamp: string;
}

interface Alerta {
  mensagem: string;
  timestamp: string;
}

type Comando = "on" | "off" | "auto";

const STATUS = {
  "sem-sinal": ["i-offline", "Sem leituras do ESP32"],
  seco: ["i-alerta", "Irrigação necessária"],
  medio: ["i-info", "Umidade moderada"],
  ok: ["i-ok", "Umidade adequada"],
  irrigando: ["i-gotas", "Irrigando agora"],
} as const;

const ALERTAS = {
  solo_seco: { texto: "Solo seco", tom: "aviso" },
  seguranca: { texto: "Segurança", tom: "critico" },
  sensor: { texto: "Sensor", tom: "critico" },
  comando: { texto: "Comando", tom: "" },
} as Record<string, { texto: string; tom: string }>;

const $ = (id: string) => document.getElementById(id)!;
const app = document.querySelector<HTMLElement>(".app")!;
const botoes = [$("btnIrrigar"), $("btnParar"), $("btnAuto")] as HTMLButtonElement[];
let temLeitura = false;

async function api<T>(caminho: string, init?: RequestInit): Promise<T> {
  const resposta = await fetch(API_URL + caminho, init).catch(() => {
    throw new Error("Não foi possível falar com a API");
  });
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new Error(typeof corpo?.detail === "string" ? corpo.detail : `Erro ${resposta.status} da API`);
  }
  return resposta.json();
}

function avisar(mensagem: string | null): void {
  $("banner").hidden = !mensagem;
  $("banner").textContent = mensagem;
}

function definirStatus(nivel: keyof typeof STATUS): void {
  const [icone, texto] = STATUS[nivel];
  $("statusIcone").setAttribute("href", `#${icone}`);
  $("statusTexto").textContent = texto;
}

function mostrarLeitura(leitura: Telemetria): void {
  const umidade = Math.round(leitura.umidade);
  const ligada = leitura.estado_bomba === "on";
  const semSinal = Date.now() - Date.parse(leitura.timestamp) > SEM_SINAL_MS;
  const nivel = umidade <= LIMIAR_LIGA ? "seco" : umidade < LIMIAR_DESLIGA ? "medio" : "ok";

  app.dataset.nivel = semSinal ? "sem-sinal" : nivel;
  definirStatus(semSinal ? "sem-sinal" : ligada ? "irrigando" : nivel);

  $("valor").textContent = `${umidade}%`;
  $("barraPreenchimento").style.width = `${Math.max(0, Math.min(100, umidade))}%`;
  $("barra").setAttribute("aria-valuenow", String(umidade));
  $("bombaModo").textContent = `Bomba ${ligada ? "ligada" : "desligada"} · Modo ${leitura.modo === "auto" ? "automático" : "manual"}`;
}

function mostrarAlertas(alertas: Alerta[]): void {
  $("semAlertas").hidden = alertas.length > 0;

  $("alertas").replaceChildren(
    ...alertas.map((alerta) => {
      // O backend grava o alerta como "[tipo] mensagem"
      const [, tipo = "", texto = alerta.mensagem] = /^\[([^\]]*)\]\s*(.*)$/.exec(alerta.mensagem) ?? [];
      const rotulo = ALERTAS[tipo] ?? { texto: tipo.replace(/_/g, " "), tom: "" };

      const hora = document.createElement("time");
      hora.dateTime = alerta.timestamp;
      hora.textContent = new Date(alerta.timestamp).toLocaleString("pt-BR");

      const etiqueta = document.createElement("span");
      etiqueta.className = `alert-tipo ${rotulo.tom}`;
      etiqueta.textContent = rotulo.texto ? `${rotulo.texto}: ` : "";

      const item = document.createElement("li");
      item.append(hora, etiqueta, texto);
      return item;
    }),
  );
}

async function atualizar(): Promise<void> {
  try {
    const [[leitura], alertas] = await Promise.all([
      api<Telemetria[]>("/api/telemetry?limit=1"),
      api<Alerta[]>("/api/alerts?limit=8"),
    ]);
    avisar(null);
    if (leitura) {
      temLeitura = true;
      mostrarLeitura(leitura);
    }
    mostrarAlertas(alertas);
  } catch (erro) {
    avisar(`${(erro as Error).message} (${API_URL}). Tentando novamente…`);
    if (!temLeitura) {
      app.dataset.nivel = "sem-sinal";
      $("statusIcone").setAttribute("href", "#i-offline");
      $("statusTexto").textContent = "Sem conexão com a API";
    }
  }
}

async function enviar(comando: Comando): Promise<void> {
  botoes.forEach((botao) => (botao.disabled = true));
  try {
    await api("/api/bomba", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comando }),
    });
  } catch (erro) {
    avisar((erro as Error).message);
  } finally {
    botoes.forEach((botao) => (botao.disabled = false));
  }
}

$("btnIrrigar").addEventListener("click", () => void enviar("on"));
$("btnParar").addEventListener("click", () => void enviar("off"));
$("btnAuto").addEventListener("click", () => void enviar("auto"));

void atualizar();
setInterval(() => void atualizar(), INTERVALO_MS);
