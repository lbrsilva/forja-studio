'use strict';
/* Estúdio Local — interface nova (página única com rotas por hash; sem framework e sem nada da internet).
   Rotas: #/ (início), #/imagem, #/video, #/apresentador (pessoa falando), #/musica.
   Regra: todo texto vindo do servidor passa por esc() ou textContent. */

// ================================================================ utilidades
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const semAcento = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '');
const norm = (s) => semAcento(s).toLowerCase();
const IGUAL = 'Igual ao vídeo';
const ENQ = { 'Igual ao vídeo (recomendado)': true, 'Original': false };
const POR_PAGINA = 24;
// endereço novo a cada carga: o navegador nunca reaproveita a tela antiga do painel guardada no cache
// O endereço do painel de música vem do servidor ("musica_url" em /api/sistema e /api/inicio): quem define a porta
// é o ESTUDIO_MUSICA_URL, e o estúdio liga o painel nessa mesma porta. O padrão só vale até a primeira resposta.
const MUSICA_PADRAO = 'http://127.0.0.1:8190';
const MUSICA_CARGA = Date.now();
function musicaBase() {
  const u = (G.sistema && G.sistema.musica_url) || (G.inicio && G.inicio.musica_url) || MUSICA_PADRAO;
  return String(u).replace(/\/+$/, '');
}
// ?estudio= diz ao painel de quem ele pode aceitar recado (a origem desta página)
const musicaUrl = () => `${musicaBase()}/?embed=1&estudio=${encodeURIComponent(location.origin)}&t=${MUSICA_CARGA}`;
// O que falta para a música funcionar nesta máquina (motor, modelo): vem de quem respondeu por último
function musicaEstado() {
  return (G.rota === 'inicio' && G.inicio && G.inicio.musica_estado) || (G.sistema && G.sistema.musica_estado)
    || (G.inicio && G.inicio.musica_estado) || null;
}
const seg = (s) => `${(+s).toFixed(1).replace('.', ',')} s`;
const num = (n, casas = 1) => Number(n).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
const dois = (n) => String(n).padStart(2, '0');
const ehVideo = (arq) => /\.(mp4|webm|mov|mkv)$/i.test(arq || '');
const ehAudio = (arq) => /\.(wav|flac|mp3|ogg|m4a|aac)$/i.test(arq || '');
const gb = (v) => (v == null || v === '' ? null : +v > 100000 ? +v / 1073741824 : +v);  // aceita bytes ou GB

function fmt(s) {
  if (s == null || !isFinite(s)) return '—';
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60), r = s % 60;
  if (m >= 60) return `${Math.floor(m / 60)} h ${dois(m % 60)} min`;
  return m ? `${m} min ${dois(r)} s` : `${r} s`;
}
function quando(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000), hoje = new Date();
  const h = `${dois(d.getHours())}:${dois(d.getMinutes())}`;
  const dia = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dif = Math.round((dia(hoje) - dia(d)) / 86400000);
  if (dif === 0) return `hoje ${h}`;
  if (dif === 1) return `ontem ${h}`;
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}${d.getFullYear() !== hoje.getFullYear() ? '/' + d.getFullYear() : ''} ${h}`;
}
function dataHora(ts) {
  if (!ts) return null;
  const d = new Date(ts * 1000);
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()} às ${dois(d.getHours())}:${dois(d.getMinutes())}`;
}
function duracaoMusica(s) {
  if (s == null || !isFinite(s)) return '';
  s = Math.round(s);
  return `${Math.floor(s / 60)}:${dois(s % 60)}`;
}
// Algumas chaves dos presets vêm sem acento (são valores enviados ao servidor): só o RÓTULO na tela ganha acento.
const ACENTOS = [[/\bRapido\b/g, 'Rápido'], [/\brapido\b/g, 'rápido'], [/\bMaxima\b/g, 'Máxima'], [/\bmaxima\b/g, 'máxima'],
  [/\bpadrao\b/g, 'padrão'], [/\bTraco artistico\b/g, 'Traço artístico'], [/\bVideo\b/g, 'Vídeo'], [/\bvideo\b/g, 'vídeo'],
  [/\bResolucao\b/g, 'Resolução'], [/\bresolucao\b/g, 'resolução'], [/\bIlustracao\b/g, 'Ilustração'], [/\bReferencia\b/g, 'Referência']];
const rot = (s) => (s == null ? '' : ACENTOS.reduce((t, [r, v]) => t.replace(r, v), String(s)));
const nomeCurto = (n) => rot(String(n || '').replace(/\s*\([^)]*\)/g, '').trim());
// 11/11/2026 - a traducao da tela. A REGRA: o PORTUGUES fica escrito AQUI, no codigo, e
// e ele que aparece se a traducao faltar. O outro idioma so troca por cima. O dicionario
// mora em idioma.js. {n} vira o numero: T("ia.trocar", "Trocar IA - {n}", { n: 4 }).
// TX(frase) traduz pelo texto em portugues, sem chave inventada. Embrulha a FUNCAO que
// mostra (aviso, o chip da maquina, o titulo da secao), nao cada chamada - assim as 43
// chamadas de aviso() continuam escritas em portugues e passam a falar tres linguas.
const TX = (pt) => (window.I18N ? window.I18N.tx(pt) : pt);
const T = (chave, pt, troca) => {
  let s = window.I18N ? window.I18N.t(chave, pt) : pt;
  if (troca) Object.keys(troca).forEach((k) => { s = s.split('{' + k + '}').join(troca[k]); });
  return s;
};
function pintarIcones(raiz = document) {
  $$('[data-ic]', raiz).forEach((el) => { if (!el.firstElementChild) el.innerHTML = ic(el.dataset.ic); });
}

async function api(url, opt = {}) { return (await apiCompleta(url, opt)).dados; }
// igual a api(), mas devolve também os cabeçalhos da resposta (ex.: X-Total de /api/trabalhos)
async function apiCompleta(url, opt = {}) {
  const { timeout, ...resto } = opt;
  const ctl = timeout ? new AbortController() : null;
  const t = ctl ? setTimeout(() => ctl.abort(), timeout) : null;
  try {
    const r = await fetch(url, ctl ? { ...resto, signal: ctl.signal } : resto);
    const txt = await r.text();
    if (!r.ok) { const e = new Error(msgErro(txt, r.status)); e.status = r.status; throw e; }
    return { dados: txt ? JSON.parse(txt) : {}, headers: r.headers };
  } catch (e) {
    if (e.name === 'AbortError') { const x = new Error(TX('O estúdio demorou demais para responder.')); x.status = 0; throw x; }
    if (e instanceof TypeError) { const x = new Error(TX('Sem resposta do estúdio (o servidor está ligado?).')); x.status = 0; throw x; }
    throw e;
  } finally { if (t) clearTimeout(t); }
}
function msgErro(txt, status) {
  let m = String(txt || '').trim();
  if (/^\{/.test(m)) { try { const j = JSON.parse(m); if (j && typeof j.erro === 'string') m = j.erro; } catch (e) { /* texto comum */ } }
  if (/^</.test(m)) m = '';  // página HTML de erro
  if (/^500 Internal Server Error/i.test(m)) m = TX('O servidor do estúdio teve um erro interno (500).');
  m = m.replace(/^\d{3}:\s*/, '');
  if (!m || /^Not Found$/i.test(m)) m = status === 404 ? TX('Não encontrado (404).') : status >= 500 ? `Erro no servidor (${status}).` : `Erro ${status}.`;
  return m;
}

// ================================================================ estado global e rotas
const filtroNovo = () => ({ ia: null, estado: 'todos', busca: '', mostrar: POR_PAGINA });
const G = {
  rota: null, presets: null, novo: false, fichas: {}, fichasMusica: [], vozes: [],
  sistema: null, inicio: null, cab: null, jobs: {}, cards: new Map(), visiveis: [],
  gal: { imagem: filtroNovo(), video: filtroNovo(), apresentador: filtroNovo() },
  jobsCarregado: {}, lupa: { lista: [], idx: 0, saida: 0 }, listaRecentes: [], musRecentes: [], audio: null, tocando: null,
  dicaIdx: null,
  // galeria: quantas pedir ao servidor por aba e quantas ficaram de fora (X-Total); -1 = servidor antigo cortou em 120
  pedir: {}, faltam: {},
  sumidos: new Set(),  // trabalhos cujo arquivo não está mais no HD (confirmado com 404)
  // painel de música embutido: falhas seguidas da checagem e se o iframe já carregou uma vez
  mus: { falhas: 0, carregou: false },
};
const PEDIR_PADRAO = 1000, PEDIR_MAX = 5000;
const ROTAS = {
  imagem: { aba: 'imagem', tipo: 't-imagem', icone: 'imagem', titulo: 'Imagem', sobre: 'Criar imagem', criacoes: 'Criações de imagem',
    gerar: 'Gerar imagem', vazio: 'Nenhuma imagem ainda. Escolha uma IA, descreva a ideia e clique em Gerar imagem.' },
  video: { aba: 'video', tipo: 't-video', icone: 'video', titulo: 'Vídeo', sobre: 'Criar vídeo', criacoes: 'Criações de vídeo',
    gerar: 'Gerar vídeo', vazio: 'Nenhum vídeo ainda. Escolha uma IA, descreva a cena e clique em Gerar vídeo.' },
  apresentador: { aba: 'video', tipo: 't-voz', icone: 'apresentador', titulo: 'Pessoa falando', sobre: 'Apresentador',
    criacoes: 'Pessoas falando', gerar: 'Gerar pessoa falando',
    vazio: 'Nenhum vídeo de pessoa falando ainda. Envie uma foto de frente, escreva o texto e clique em Gerar.' },
};
const TITULOS = { inicio: 'Início', imagem: 'Imagem', video: 'Vídeo', apresentador: 'Pessoa falando', voz: 'Narração', canal: 'Canal automático', plano: 'Plano-sequência', musica: 'Música', fila: 'Fila', tudo: 'Minhas criações', configuracoes: 'Configurações' };
// IA recomendada em cada seção (CATALOGO_IAS.md: "Quem usar em cada caso")
// 02/11/2026: a recomendada passou a ser a que o historico mostra em uso de verdade
// (Krea 2 Turbo: 696 geracoes; LTX 2.5 texto: a mais usada que funciona SO com texto).
const RECOMENDADA = { imagem: 'krea2', video: 'ltx25_t2v', apresentador: 'apresentador', plano: 'h3_contexto', musica: 'yue2-int8' };
const ehGerador = (r) => r === 'imagem' || r === 'video' || r === 'apresentador';
const ehApresentador = (p) => !!p && (p.tipo === 'apresentador' || p.id === 'apresentador');
const tipoDaRota = (r) => (ROTAS[r] ? ROTAS[r].tipo : r === 'musica' ? 't-musica' : 't-imagem');
const todosPresets = () => (G.presets ? [...(G.presets.imagem || []), ...(G.presets.video || [])] : []);
const acharPreset = (id) => todosPresets().find((p) => p.id === id) || null;

function presetsDa(rota) {
  if (!G.presets) return [];
  if (rota === 'imagem') return G.presets.imagem || [];
  const v = G.presets.video || [];
  // o Plano-sequência é uma tela só para a h3_contexto; o cartão do Início mostra ela
  if (rota === 'plano') return v.filter((p) => p.id === 'h3_contexto');
  if (rota === 'apresentador') return v.filter(ehApresentador);
  // 02/11/2026: o plano-sequencia SAI da lista da aba Video. Escolhido ali, o gerador comum
  // nao mostra duracao nem tamanho do quadro e manda uma tomada mal configurada: a tela dele e #/plano.
  if (rota === 'video') return v.filter((p) => !ehApresentador(p) && p.id !== 'h3_contexto');
  return [];
}
function rotaDoJob(j) {
  if (j.aba === 'imagem') return 'imagem';
  const p = acharPreset(j.preset);
  return (p ? ehApresentador(p) : j.preset === 'apresentador') ? 'apresentador' : 'video';
}

// ================================================================ fichas das IAs (texto da tela)
function fichaDe(id) { return G.fichas[id] || (acharPreset(id) || {}).ficha || null; }
function fichaOuPreset(p) {
  if (!p) return null;
  const f = fichaDe(p.id);
  if (f) return f;
  const aba = (G.presets.imagem || []).includes(p) ? 'imagem' : 'video';
  return { id: p.id, aba, nome: p.nome, parcial: true, tags: (p.tags || []).map(rot), resumo_curto: rot(p.descricao || ''),
    categoria: p.categoria || (ehApresentador(p) ? 'Pessoa falando' : aba === 'imagem' ? 'Imagem' : 'Vídeo') };
}
function tempoCurto(f) {
  const t = String((f && f.tempo_tipico) || '');
  if (!t) return '';
  let s = t.replace(/\s*\([^)]*\)/g, '').split(/(?<=[.;])\s/)[0].replace(/[.;]$/, '').trim();
  // "266 s, dos quais 248 s são para carregar do HD" → "266 s (quase tudo é carregar do HD)": arredondados para minutos,
  // os dois números ficariam iguais ("~4 min, dos quais ~4 min"), o que confunde
  s = s.replace(/(\d+)(?:–(\d+))?(\s?s),?\s*dos quais\s+(\d+)(?:–(\d+))?\s?s\s+(?:são|é|foram)\s+(?:só\s+)?(?:para\s+)?carregar(?:ndo)?\s+do\s+HD/,
    (m, x, y, u, a, b) => {
      const frac = (b ? +b : +a) / (y ? +y : +x);
      return `${x}${y ? '–' + y : ''}${u} (${frac >= 0.75 ? 'quase tudo é' : frac >= 0.5 ? 'a maior parte é' : 'inclui'} carregar do HD)`;
    });
  // "1065 s" vira "~18 min" (só números grandes; "5,4 s" e "15–27 s" ficam como estão)
  const mi = (x) => Math.max(1, Math.round(x / 60));
  s = s.replace(/(\d+)(?:–(\d+))?\s?s\b/g, (m, x, y) => ((y ? +y : +x) < 90 ? m : y ? `~${mi(+x)}–${mi(+y)} min` : `~${mi(+x)} min`));
  if (s.length > 66) s = s.slice(0, 64).replace(/[\s,;:–-]+\S*$/, '') + '…';
  return s;
}
function htmlNotas(f) {
  const barras = (n) => [1, 2, 3, 4, 5].map((i) => `<b${i <= n ? ' class="on"' : ''}></b>`).join('');
  const deCinco = (n) => T('ia.deCinco', '{n} de 5', { n });
  const um = (cls, rotulo, n) => (n ? `<span class="notas ${cls}" title="${rotulo}: ${deCinco(n)}">${rotulo}<i aria-hidden="true">${barras(n)}</i><span class="sr-only">${deCinco(n)}</span></span>` : '');
  return um('v', T('ia.velocidade', 'Velocidade'), +f.nota_velocidade || 0)
       + um('q', T('ia.qualidade', 'Qualidade'), +f.nota_qualidade || 0);
}
const tipoDaFicha = (f) => (f.aba === 'musica' ? 't-musica' : f.aba === 'imagem' ? 't-imagem'
  : (f.id === 'apresentador' || f.categoria === 'Pessoa falando') ? 't-voz' : 't-video');
const ICONE_TIPO = { 't-imagem': 'imagem', 't-video': 'video', 't-voz': 'apresentador', 't-musica': 'musica' };
const ROTA_TIPO = { 't-imagem': 'imagem', 't-video': 'video', 't-voz': 'apresentador', 't-musica': 'musica' };

async function carregarFichas() {
  const P = G.presets;
  // servidor novo (contrato [A]): presets trazem "ficha" e há "musica_fichas"; senão, usa só o que o preset tem
  G.novo = !!(P.musica_fichas || todosPresets().some((p) => p.ficha !== undefined));
  let ias = null;
  if (G.novo) {
    try { const r = await api('/api/fichas', { timeout: 8000 }); ias = r.ias || r; } catch (e) { ias = null; }
  }
  G.fichas = {};
  if (ias && typeof ias === 'object') Object.values(ias).forEach((f) => { if (f && f.id) G.fichas[f.id] = f; });
  todosPresets().forEach((p) => { if (p.ficha && !G.fichas[p.id]) G.fichas[p.id] = p.ficha; });
  (P.musica_fichas || []).forEach((f) => { if (f && f.id && !G.fichas[f.id]) G.fichas[f.id] = f; });
  G.fichasMusica = Object.values(G.fichas).filter((f) => f.aba === 'musica');
}

// qual IA gerou (campo "ia" do servidor novo; senão, monta a partir do trabalho)
function iaDe(j) {
  const ia = j.ia || {};
  const f = fichaDe(j.preset);
  const ap = rotaDoJob(j) === 'apresentador';
  const nome = rot(ia.nome || (f && f.nome) || j.nome || j.preset || 'IA');
  let motor = ia.motor || j.motor_usado || null;
  if (ap && !motor) motor = 'motor não registrado';
  let voz = ia.voz || null;
  if (ap && !voz) voz = j.audio ? 'áudio pronto enviado' : `Chatterbox Multilingual · ${j.voz_nome || (j.voz ? 'voz clonada' : 'voz padrão')}`;
  return { nome, curto: nomeCurto(nome), motor, voz, resumo: ia.resumo || null };
}
function seloTexto(j) {
  const ia = iaDe(j);
  return ia.curto + (ia.motor && ia.motor !== 'motor não registrado' ? ` · ${ia.motor}` : '');
}
const altDe = (j) => `${iaDe(j).curto}: ${String(j.prompt || 'sem prompt').slice(0, 140)}`;
const decorrido = (j) => ((j.progresso && j.progresso.decorrido != null) ? j.progresso.decorrido : (j.fim ? j.fim - (j.inicio || j.criado) : null));
const podeReusar = (j) => j.preset_existe !== false && presetsDa(rotaDoJob(j)).some((p) => p.id === j.preset);
// o arquivo sumiu do HD: o servidor avisa (arquivo_existe:false) ou a mídia deu 404 aqui
const sumiu = (j) => j.arquivo_existe === false || G.sumidos.has(j.id);
const prontoComArquivo = (j) => j.estado === 'concluido' && (j.saidas || []).length > 0 && !sumiu(j);
const ROT_MODO = { prompt: 'Só texto', referencia: 'Com imagem', personagem: 'Personagem + movimento' };
// Os rotulos acima passam por TX() na hora de desenhar (ver chips e rotuloModo).
// "Chatterbox Multilingual · Minha voz" → "voz: Chatterbox · Minha voz" (regra: sempre mostrar qual IA fez a voz)
const vozCurta = (j) => { const v = iaDe(j).voz; return v ? `voz: ${String(v).replace('Chatterbox Multilingual', 'Chatterbox')}` : null; };

function fichaTec(j) {
  // ficha técnica curta (1 linha); no Apresentador a voz vem primeiro para não sumir no corte da linha
  const ap = rotaDoJob(j) === 'apresentador';
  return [ap ? vozCurta(j) : null, ap ? null : ROT_MODO[j.modo], rot(j.formato), j.tamanho && `${j.tamanho[0]}×${j.tamanho[1]}`,
    j.resolucao && nomeCurto(j.resolucao),
    j.imagens && j.imagens.length && `${j.imagens.length} referência${j.imagens.length > 1 ? 's' : ''}`,
    j.duracao && (j.segundos_video ? `${seg(j.segundos_video)} (${j.segmentos} trechos)` : rot(j.duracao)),
    ap && j.segundos_audio && `${seg(j.segundos_audio)} de fala`, ap && j.idioma,
    rot(j.estilo), rot(j.qualidade), j.seed != null && j.seed !== '' && `semente ${j.seed}`].filter(Boolean).join(' · ');
}
function nomeArquivo(j, i = 0) {
  // <aaaa-mm-dd>_<ia>[-motor]_<id>.<ext>, sem acento quebrado
  const s = (j.saidas || [])[i] || {};
  const ext = (String(s.arquivo || '').split('.').pop() || 'png').toLowerCase();
  const d = new Date((j.criado || Date.now() / 1000) * 1000);
  const ia = iaDe(j);
  const base = [ia.curto, ia.motor && ia.motor !== 'motor não registrado' ? ia.motor : ''].filter(Boolean).join('-');
  const limpo = semAcento(base).replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'estudio';
  return `${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}_${limpo}_${j.id}${i ? '_' + (i + 1) : ''}.${ext}`;
}
const urlMidia = (j, i = 0) => `/api/midia/${encodeURIComponent(j.id)}/${i}`;

// ================================================================ avisos flutuantes e janelas
function aviso(msg, tipo = 'ok', ms = 5500) {
  msg = TX(msg);   // ver TX(): a frase em portugues e a propria chave
  const el = document.createElement('div');
  el.className = 'aviso-toast' + (tipo === 'erro' ? ' erro-t' : tipo === 'aviso' ? ' aviso-t' : '');
  el.innerHTML = ic(tipo === 'erro' ? 'alerta' : tipo === 'aviso' ? 'info' : 'ok') + `<span>${esc(msg)}</span>`;
  $('#avisos').appendChild(el);
  setTimeout(() => { el.classList.add('sumindo'); setTimeout(() => el.remove(), 350); }, ms);
}
function confirmar({ titulo, texto, lista = [], rodape = '', sim = 'Confirmar', nao = 'Voltar', icone = 'alerta', perigo = true }) {
  // lista: [{ txt, cls }] (cls: 'fica' | 'alerta'), tudo por textContent
  return new Promise((resolver) => {
    const d = $('#dlgConfirmar');
    $('#confTitulo').textContent = titulo;
    $('#confTexto').textContent = texto;
    const ul = $('#confLista');
    ul.innerHTML = '';
    lista.forEach((x) => {
      const li = document.createElement('li');
      if (x.cls) li.className = x.cls;
      li.textContent = x.txt;
      ul.appendChild(li);
    });
    ul.hidden = !lista.length;
    $('#confRodape').textContent = rodape;
    $('#confRodape').hidden = !rodape;
    $('#confIc').innerHTML = ic(icone);
    $('#confIc').className = 'conf-ic' + (perigo ? '' : ' neutro');
    $('#confSim').textContent = sim;
    $('#confSim').className = perigo ? 'bt-perigo' : 'gerar';
    $('#confNao').textContent = nao;
    let feito = false;
    const origem = document.activeElement;
    const fim = (v) => {
      if (feito) return;
      feito = true;
      if (d.open) d.close();
      d.onkeydown = null;
      if (origem && document.contains(origem) && origem.focus) origem.focus({ preventScroll: true });
      resolver(v);
    };
    $('#confSim').onclick = () => fim(true);
    $('#confNao').onclick = () => fim(false);
    d.oncancel = (e) => { e.preventDefault(); fim(false); };
    d.onkeydown = (e) => { if (e.key === 'Escape') { e.preventDefault(); fim(false); } };
    d.onclose = () => fim(false);
    d.showModal();
    $('#confNao').focus();  // o foco começa no botão seguro
  });
}
function abrirFicha(f) {
  if (!f) return;
  const t = tipoDaFicha(f), rota = ROTA_TIPO[t];
  const sec = (cls, icone, titulo, txt) => (txt ? `<section class="ficha-sec ${cls}"><h3>${ic(icone)}${titulo}</h3><p>${esc(txt)}</p></section>` : '');
  const podeUsar = ehGerador(rota) && presetsDa(rota).some((p) => p.id === f.id);
  const notas = htmlNotas(f);
  $('#fichaCorpo').innerHTML = `
    <div class="ficha-cab ${t}">
      <span class="painel-ic">${ic(ICONE_TIPO[t])}</span>
      <div><span class="ia-cat">${esc(f.categoria || '')}</span><h2 id="fichaNome">${esc(rot(f.nome))}</h2>${f.resumo_curto ? `<p>${esc(f.resumo_curto)}</p>` : ''}</div>
      <button type="button" class="ic-bt" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    </div>
    ${notas ? `<div class="ficha-notas">${notas}</div>` : ''}
    <div class="ficha-grade">
      ${sec('largo', 'info', TX('O que faz'), f.o_que_faz)}
      ${sec('bom', 'ok', TX('Melhor para'), f.melhor_para)}
      ${sec('ruim', 'alerta', TX('Evite para'), f.evite_para)}
      ${sec('largo', 'relogio', TX('Tempo típico (medido nesta máquina)'), f.tempo_tipico)}
      ${sec('largo', 'fila', 'Limites', f.limites)}
      ${sec('dica', 'dica', 'Dica de prompt', f.dica_prompt)}
    </div>
    ${f.parcial ? '<p class="nota">A ficha completa desta IA aparece quando o servidor do estúdio for atualizado.</p>' : ''}
    ${(f.tags || []).length ? `<div class="tags">${f.tags.map((x) => `<span class="tag">${esc(rot(x))}</span>`).join('')}</div>` : ''}
    <div class="janela-acoes">
      ${podeUsar ? `<button type="button" class="gerar" data-usar="${esc(f.id)}" data-rota="${rota}">${ic('ok')}Usar esta IA</button>` : ''}
      <button type="button" class="bt-sec" data-fechar>Fechar</button>
    </div>`;
  const d = $('#dlgFicha');
  if (!d.open) { fichaOrigem = document.activeElement; d.showModal(); }
  d.scrollTop = 0;
  const foco = $('[data-usar]', d) || $('[data-fechar]', d);
  if (foco) foco.focus({ preventScroll: true });
}
let fichaOrigem = null;
function fecharFicha(devolverFoco = true) {
  const d = $('#dlgFicha');
  if (d.open) d.close();
  const o = fichaOrigem;
  fichaOrigem = null;
  if (devolverFoco && o && document.contains(o) && o.focus) o.focus({ preventScroll: true });
}
function usarIA(id, rota) {
  fecharFicha(false);
  const est = ESTADOS[rota] || (ESTADOS[rota] = estadoNovo(rota));
  est.sel = id; est.formato = est.duracao = est.resolucao = null; est.trocando = false;
  if (G.rota !== rota) { location.hash = '#/' + rota; return; }
  aplicarPreset();
  aviso(`IA escolhida: ${nomeCurto((acharPreset(id) || {}).nome)}.`);
}

// ================================================================ pulso: cabeçalho + máquina (a cada 5 s)
// "A home funciona sempre": se uma leitura falhar, a tela continua mostrando o que já tinha (nada some nem pisca) e
// tenta de novo sozinha em 3 s; só depois de 2 falhas seguidas aparece o aviso "sem resposta, tentando de novo".
let pulsoGen = 0, pulsoT = null;
const FALHAS_AVISO = 2;
async function pulso(forcar) {
  // com a aba escondida o pulso para (só a 1ª leitura de cada tela acontece mesmo assim)
  const gen = ++pulsoGen;
  clearTimeout(pulsoT);
  if (!document.hidden || forcar === true) {
    try {
      if (G.rota === 'inicio') {
        await carregarInicio();
        if (gen !== pulsoGen) return;
        G.falhas = 0;
        renderInicioVivo();
      } else {
        await carregarInicio().then(renderMaquina).catch(() => {});
        // o cabeçalho usa o estado REAL do estúdio (todas as abas), lido agora: nunca a lista guardada de outra seção
        const [s, lista] = await Promise.all([api('/api/sistema', { timeout: 9000 }),
          api('/api/trabalhos?limite=20', { timeout: 9000 }).catch(() => null)]);
        if (gen !== pulsoGen) return;
        G.falhas = 0;
        G.sistema = s;
        G.cab = cabDeSistema(s, Array.isArray(lista) ? estudioDeLista(lista) : null);
      }
      renderCabecalho();
      if (G.rota === 'musica') atualizarMusica();
      if (ehGerador(G.rota)) checarMudancaSistema();
    } catch (e) {
      if (gen !== pulsoGen) return;
      G.falhas = (G.falhas || 0) + 1;
      if (G.falhas >= FALHAS_AVISO || !G.cab) { G.cab = { erro: true }; renderCabecalho(); }
      if (G.rota === 'inicio') renderSemResposta();
    }
  }
  if (gen !== pulsoGen) return;
  pulsoT = setTimeout(pulso, G.falhas ? 3000 : 5000);
}
// Cabeçalho: UMA fonte só para "o que está gerando": a fila do estúdio (trabalho rodando + quantos esperam).
// A fila da ComfyUI entra só como "ocupada por fora" (algo que não veio do estúdio).
function estudioDeLista(lista) {
  const ativos = lista.filter((j) => j.estado === 'fila' || j.estado === 'rodando');
  return { rodando: ativos.find((j) => j.estado === 'rodando') || null, naFila: ativos.filter((j) => j.estado === 'fila').length };
}
function cabDeSistema(s, est) {
  return { comfy: !!s.comfy, comfyLigando: !!s.comfy_ligando, vramLivre: gb(s.vram_livre), vramTotal: gb(s.vram_total),
    filaComfy: s.fila == null ? null : +s.fila,
    rodando: est ? est.rodando : null, naFila: est ? est.naFila : null, texto: !!(s.texto && s.texto.na_placa) };
}
function cabDeInicio(I) {
  const S = I.sistema || {}, F = I.fila || {}, sv = S.servicos || {}, v = (I.servicos || {}).video || {};
  return { comfy: sv.video == null ? null : !!sv.video, comfyLigando: v.estado === 'ligando',
    vramLivre: gb(S.vram_livre), vramTotal: gb(S.vram_total),
    filaComfy: S.fila_comfy == null ? null : +S.fila_comfy, rodando: F.rodando || null, naFila: +F.na_fila || 0,
    texto: !!(I.texto && I.texto.na_placa) };
}
function renderCabecalho() {
  const c = G.cab || {}, p = $('#maqPonto'), t = $('#maqTxt'), a = $('#maqMini');
  // fio de progresso: a mesma porcentagem do texto, visivel de qualquer aba
  const fio = $('#topoProg'), pctFio = c.rodando ? Math.floor((c.rodando.progresso && c.rodando.progresso.pct) || 0) : 0;
  // o fio guarda a porcentagem numa variável: na barra de cima ela vira LARGURA, no trilho
  // lateral vira ALTURA (sobe pela borda). Quem escolhe é o CSS, não este código.
  if (fio) {
    fio.hidden = !c.rodando;
    fio.style.setProperty('--pct', c.rodando ? Math.max(2, pctFio) + '%' : '0%');
  }
  a.classList.toggle('gerando', !!c.rodando);
  G.rotaGerando = c.rodando ? rotaDoJob(c.rodando) : null;
  const fila = c.naFila ? ` · <b>${c.naFila}</b> na fila` : '';
  let titulo = TX('Sua máquina (abre o Início)');
  if (c.erro) {
    p.className = 'ponto off'; t.innerHTML = esc(TX('Estúdio sem resposta')) + '<span class="longo"> · ' + esc(TX('tentando de novo…')) + '</span>';
    titulo = TX('O estúdio não respondeu agora. A tela tenta de novo sozinha a cada poucos segundos.');
  }
  else if (c.rodando) {
    const r = c.rodando, pct = Math.floor((r.progresso && r.progresso.pct) || 0);
    p.className = 'ponto ocupado';
    t.innerHTML = `Gerando <b>${pct}%</b><span class="longo"> · ${esc(iaDe(r).curto)}</span>${fila}`;
    titulo = `Gerando agora: ${seloTexto(r)} (${pct}%)` + (c.naFila ? `. Mais ${c.naFila} esperando a vez na fila do estúdio.` : '');
  } else if (c.naFila) {
    p.className = 'ponto ocupado';
    t.innerHTML = `Fila do estúdio <b>${c.naFila}</b>`;
    titulo = TX('Trabalhos do estúdio esperando a vez na placa de vídeo (uma geração por vez).');
  } else if (c.texto) {
    p.className = 'ponto ocupado';
    t.innerHTML = 'IA de texto<span class="longo"> na placa</span>';
    titulo = TX('A IA de texto está usando a placa de vídeo por alguns segundos (ela sai sozinha ao terminar).');
  } else if (c.comfy === false && c.comfyLigando) {
    p.className = 'ponto ocupado'; t.innerHTML = 'ComfyUI <b>ligando…</b>';
    titulo = TX('A ComfyUI de imagem e vídeo está ligando (leva 1–2 min).');
  } else if (c.comfy === false) {
    // desligada não é defeito: ponto cinza (vermelho é só para erro de verdade) e o Início tem o botão Ligar
    p.className = 'ponto parado'; t.innerHTML = 'ComfyUI <b>desligada</b>';
    titulo = TX('A ComfyUI de imagem e vídeo está desligada. Clique para ir ao Início e ligar.');
  } else if (c.filaComfy) {
    p.className = 'ponto ocupado';
    t.innerHTML = `ComfyUI ocupada<span class="longo"> por fora</span> · <b>${c.filaComfy}</b>`;
    titulo = TX('A ComfyUI de vídeo está gerando algo que não foi pedido pelo estúdio.');
  } else {
    p.className = 'ponto on';
    const vram = c.vramLivre != null ? `${G.gpuMemoria === 'unificada' ? 'GPU' : 'VRAM'} <b>${num(c.vramLivre)} GB</b><span class="longo"> livres</span> · ` : '';
    t.innerHTML = `${vram}Livre`;
    titulo = TX('Nada gerando agora. Clique para ver a sua máquina no Início.');
  }
  a.title = titulo;
}
// a lista da seção aberta é mais nova que o pulso (atualiza a cada 1,5 s gerando): acerta o cabeçalho com ela
function cabecalhoDaGaleria(lista) {
  const c = G.cab;
  if (!c || c.erro) return;
  const r = lista.find((j) => j.estado === 'rodando');
  if (r && (!c.rodando || c.rodando.id === r.id)) { c.rodando = r; renderCabecalho(); }
  else if (!r && c.rodando && lista.some((j) => j.id === c.rodando.id)) pulso();  // terminou agora: relê tudo na hora
}

// ================================================================ roteador
function rotaDoHash() {
  const h = location.hash.replace(/^#\/?/, '').split(/[/?]/)[0];
  return ['imagem', 'video', 'apresentador', 'musica', 'voz', 'canal', 'plano', 'tudo', 'fila', 'configuracoes'].includes(h) ? h : 'inicio';
}
// "#conteudo" (link "Pular para o conteúdo") e outras âncoras não são rotas: não trocam a tela
const hashEhRota = () => !location.hash || location.hash === '#' || location.hash.startsWith('#/');
function focarTitulo(rolar = false) {
  const r = G.rota, h = r === 'inicio' ? $('#inicioTitulo') : r === 'musica' ? $('#musTitulo')
    : r === 'voz' ? $('#vozTitulo') : r === 'canal' ? $('#canalTitulo') : r === 'plano' ? $('#planoTitulo')
    : r === 'tudo' ? $('#tudoTitulo') : r === 'fila' ? $('#filaTitulo')
    : r === 'configuracoes' ? $('#configTitulo') : $('#rotaTitulo');
  if (h) h.focus({ preventScroll: !rolar });
}
function irPara() {
  if (G.rota && !hashEhRota()) return;
  const r = rotaDoHash(), antes = G.rota;
  if (r === 'musica' && semMusica()) { location.hash = '#/'; return; }
  // o Início aparece na hora; as outras seções precisam da lista de IAs (vem do servidor): esperam por ela
  if (ehGerador(r) && !G.presets) {
    G.irDepois = true;
    aviso(TX('Carregando as IAs do estúdio… a seção abre sozinha em instantes.'), 'aviso');
    return;
  }
  if (antes && ehGerador(antes) && ESTADOS[antes]) salvarCampos(ESTADOS[antes]);
  G.rota = r;
  $$('#nav a').forEach((a) => { if (a.dataset.rota === r) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  $('#vInicio').hidden = r !== 'inicio';
  $('#vGerador').hidden = !ehGerador(r);
  $('#vMusica').hidden = r !== 'musica';
  // Narração (voz local). Vive no voz.js, que é um arquivo à parte de propósito: se ele faltar
  // ou quebrar, o resto do estúdio continua inteiro.
  $('#vVoz').hidden = r !== 'voz';
  $('#vCanal').hidden = r !== 'canal';
  if (r === 'canal' && window.CANAL) CANAL.abrir();
  $('#vPlano').hidden = r !== 'plano';
  if (r === 'plano' && window.PLANO) PLANO.abrir();
  $('#vTudo').hidden = r !== 'tudo';
  $('#vFila').hidden = r !== 'fila';
  $('#vConfig').hidden = r !== 'configuracoes';
  if (r === 'configuracoes' && window.CONFIG) CONFIG.abrir();
  // 07/11/2026: ESTA linha nasceu sem o "window.X &&" que todas as vizinhas tem, e o
  // fila.js carrega DEPOIS do app.js - entao ela estourava "FILA is not defined" em
  // TODA abertura do painel, dentro de iniciar(), e matava o resto: os cartoes ficavam
  // em "Carregando as IAs..." para sempre e o catalogo nascia vazio. Eu conferi por
  // HTTP e nao pela TELA, e por isso nao vi. O dono viu.
  if (window.FILA) { if (r === 'fila') FILA.abrir(); else FILA.fechar(); }
  if (r === 'tudo' && window.TUDO) TUDO.abrir();
  document.body.classList.toggle('rota-voz', r === 'voz');
  document.body.classList.toggle('rota-inicio', r === 'inicio');
  if (r === 'voz' && window.VOZ) VOZ.abrir();
  document.body.classList.toggle('rota-musica', r === 'musica');
  document.title = r === 'inicio' ? 'JerS · Forja Studio' : `${TITULOS[r]} · Forja Studio`;
  if (r !== 'inicio' && G.audio && !G.audio.paused) G.audio.pause();
  if (!ehGerador(r)) pararGaleria();
  if (r === 'inicio') abrirInicio();
  else if (ehGerador(r)) abrirGerador(r);
  else if (r === 'voz' || r === 'canal' || r === 'plano' || r === 'tudo' || r === 'configuracoes') medirTopo();  // voz.js / canal.js se viram sozinhos
  else { medirTopo(); atualizarMusica(true); }
  if (antes) {
    window.scrollTo(0, 0);
    focarTitulo();
  }
  pulso(true);
}
// a Música ocupa exatamente o resto da tela (sem 2ª barra de rolagem): mede a altura real do cabeçalho
function medirTopo() {
  // Com o trilho lateral (telas largas) nao existe cabecalho em cima: a Musica ocupa a altura
  // inteira. No celular o trilho vira barra horizontal de novo, e af a altura dele conta.
  const rail = window.matchMedia('(min-width: 981px)').matches;
  if (rail) { document.documentElement.style.setProperty('--topo-real', '0px'); return; }
  const h = $('.topo').getBoundingClientRect().height;
  if (h) document.documentElement.style.setProperty('--topo-real', `${h}px`);
}

// ================================================================ INÍCIO
const ESCOLHAS = [
  { rota: 'imagem', tipo: 't-imagem', icone: 'imagem', titulo: 'Imagem',
    frase: 'Fotos realistas, ilustrações, cartazes com texto escrito certo e transformação de uma imagem sua.' },
  { rota: 'video', tipo: 't-video', icone: 'video', titulo: 'Vídeo',
    frase: 'Texto ou imagem viram vídeo: com som, emendando cenas ou copiando o movimento de um vídeo real.' },
  { rota: 'apresentador', tipo: 't-voz', icone: 'apresentador', titulo: 'Pessoa falando',
    frase: 'Uma foto de frente e um texto viram alguém falando para a câmera, com voz e boca sincronizada.' },
  { rota: 'plano', tipo: 't-video', icone: 'video', titulo: 'Plano-sequência',
    frase: 'Pessoa de verdade numa tomada contínua, sem corte: a cena sai inteira, de 16 a 32 segundos.' },
  { rota: 'voz', tipo: 't-voz', icone: 'onda', titulo: 'Narração',
    frase: 'Texto vira voz falada no seu computador, de graça: criar uma voz pela descrição ou clonar a sua.' },
  { rota: 'musica', tipo: 't-musica', icone: 'musica', titulo: 'Música',
    frase: 'Músicas com letra cantada, trilhas instrumentais e covers (YuE2 e Stable Audio 3).' },
];

// ---------------------------------------------------------------- as chaves de API
// 11/11/2026. A REGRA DESTA TELA: ela NUNCA mostra a chave guardada, nem traz ela do
// servidor. Mostra só SE existe uma. Trazer de volta um segredo que o próprio navegador
// mandou não serve para nada e só aumenta a chance de ele vazar num print ou num log.
//
// Quem já tem a chave guardada vê "guardada" e o campo em branco: escrever por cima troca,
// e salvar em branco remove. Assim ninguém precisa colar de novo o que já colou.
async function lerChaves() {
  try {
    const d = await api('/api/chaves');
    G.chaves = d.chaves || [];
    renderChaves();
  } catch (e) { /* servidor antigo: a seção simplesmente não aparece */ }
}

function renderChaves() {
  const onde = $('#chavesLista');
  if (!onde) return;
  const lista = G.chaves || [];
  $('#blocoChaves').hidden = !lista.length;
  if (!lista.length) return;
  onde.innerHTML = lista.map((c) => {
    const passos = (c.antes || []).map(([txt, url], i) =>
      `<li><a href="${esc(url)}" target="_blank" rel="noopener">${esc(TX(txt))}</a></li>`).join('');
    const estado = c.tem
      ? `<span class="chave-ok">${ic('ok')}${esc(TX('guardada'))}</span>`
      : `<span class="chave-nao">${esc(TX('não tem nenhuma — e tudo bem'))}</span>`;
    return `<div class="chave-cartao" data-chave="${esc(c.id)}">
      <div class="chave-topo"><h3>${esc(c.nome)}</h3>${estado}</div>
      <p class="fraco">${esc(TX(c.para_que))}</p>
      ${passos ? `<ol class="chave-passos">${passos}</ol>`
               : `<p class="fraco"><a href="${esc(c.onde_criar)}" target="_blank" rel="noopener">${esc(TX('Onde criar a chave'))}</a></p>`}
      <div class="chave-linha">
        <input type="password" class="chave-campo" autocomplete="off" spellcheck="false"
               placeholder="${esc(c.tem ? TX('já tem uma guardada — cole outra para trocar') : TX('cole aqui'))}">
        <button type="button" class="bt-sec" data-salvar="${esc(c.id)}">${ic('ok')}${esc(TX('Salvar'))}</button>
        ${c.tem ? `<button type="button" class="bt-sec" data-apagar="${esc(c.id)}">${esc(TX('Remover'))}</button>` : ''}
      </div>
      <p class="fraco chave-onde">${esc(TX('fica só no seu computador, em'))} <code>${esc(c.arquivo)}</code></p>
    </div>`;
  }).join('');
  pintarIcones(onde);
}

async function salvarChave(id, valor) {
  const cartao = $(`[data-chave="${id}"]`);
  const bt = cartao && cartao.querySelector('[data-salvar]');
  if (bt) bt.disabled = true;
  try {
    const d = await api('/api/chaves', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, valor }),
    });
    aviso(d.mensagem || 'Pronto.', d.ok === false ? 'aviso' : 'ok', 8000);
    const campo = cartao && cartao.querySelector('.chave-campo');
    if (campo) campo.value = '';   // nunca deixar o segredo na tela depois de salvar
    lerChaves();
    // chave nova do ElevenLabs: recarrega a lista para as vozes da nuvem aparecerem
    // agora, e nao so quando a pessoa abrir a aba Narracao de novo.
    if (id === 'elevenlabs' && typeof carregarVozes === 'function') carregarVozes();
  } catch (e) {
    aviso(e.message, 'erro', 9000);
  } finally {
    if (bt) bt.disabled = false;
  }
}

document.addEventListener('click', (ev) => {
  const bs = ev.target.closest && ev.target.closest('[data-salvar]');
  if (bs) {
    const cartao = bs.closest('[data-chave]');
    const campo = cartao && cartao.querySelector('.chave-campo');
    const valor = campo ? campo.value.trim() : '';
    if (!valor) { aviso('Cole a chave no campo antes de salvar.', 'aviso'); return; }
    salvarChave(bs.dataset.salvar, valor);
    return;
  }
  const ba = ev.target.closest && ev.target.closest('[data-apagar]');
  if (ba && confirm(TX('Remover esta chave? O estúdio continua funcionando sem ela.'))) {
    salvarChave(ba.dataset.apagar, '');
  }
});

function abrirInicio() {
  renderEscolhas(true);
  renderCatalogo();
  lerChaves();
  if (G.dicaIdx == null) proximaDica();
  if (G.inicio) renderInicioVivo();
}
const semMusica = () => (G.presets && G.presets.tem_musica === false) || (G.inicio && G.inicio.tem_musica === false);
function aplicarTemMusica() {
  const tem = !semMusica();
  document.querySelectorAll('[data-rota="musica"]').forEach((a) => { a.hidden = !tem; });
  if (!tem && G.rota === 'musica') location.hash = '#/';
}
async function carregarInicio() {
  let I = null;
  try { I = await api('/api/inicio', { timeout: 9000 }); }
  catch (e) { if (e.status !== 404) throw e; }
  if (I && typeof I === 'object') {
    // resposta incompleta (o servidor teve um problema para montar): conta como falha e mantém o que já estava na tela
    if (I.incompleto && G.inicio) throw new Error(TX('Resposta incompleta do estúdio.'));
    I.sistema = I.sistema || {};
    I.fila = I.fila || {};
    I.contagem = I.contagem || {};
    I.parcial = false;
    // servidor de antes da "Home com botões de ligar" (sem "servicos"): a tela funciona, só sem os botões de ligar
    I.legado = !('servicos' in I);
    G.relogioDif = (+I.agora || Date.now() / 1000) - Date.now() / 1000;
    G.inicio = I;
    G.gpuMemoria = I.sistema.gpu_memoria;
    G.cab = cabDeInicio(I);
    aplicarTemMusica();
    return;
  }
  // servidor bem antigo (sem /api/inicio): monta o que der com /api/sistema e /api/trabalhos
  const [s, ji, jv] = await Promise.all([api('/api/sistema', { timeout: 9000 }),
    api('/api/trabalhos?aba=imagem', { timeout: 9000 }).catch(() => []), api('/api/trabalhos?aba=video', { timeout: 9000 }).catch(() => [])]);
  G.sistema = s;
  const todos = [...ji, ...jv];
  const concl = todos.filter(prontoComArquivo).sort((a, b) => (b.fim || b.criado) - (a.fim || a.criado));
  G.inicio = {
    parcial: true, legado: true,
    sistema: { gpu: s.gpu, vram_total: s.vram_total, vram_livre: s.vram_livre,
      servicos: { video: !!s.comfy, painel_musica: !!s.musica }, fila_comfy: s.fila },
    fila: { rodando: todos.find((j) => j.estado === 'rodando') || null, na_fila: todos.filter((j) => j.estado === 'fila').length, musica_ocupada: null },
    contagem: { imagens: ji.filter(prontoComArquivo).length, videos: jv.filter(prontoComArquivo).length, musicas: null },
    recentes: concl.slice(0, 8).map((j) => ({ ...j, midia: urlMidia(j) })),
    musicas_recentes: await musicasDireto(),
  };
  G.cab = cabDeInicio(G.inicio);
}
let musCache = { t: 0, lista: [] };
async function musicasDireto() {
  // (servidor antigo) só no endereço de produção (8194) o painel libera CORS; em outra porta nem tenta
  if (location.port !== '8194') return [];
  if (Date.now() - musCache.t < 30000) return musCache.lista;
  musCache.t = Date.now();
  try { musCache.lista = await api(musicaBase() + '/api/recentes?n=6', { timeout: 2000 }); } catch (e) { musCache.lista = []; }
  if (!Array.isArray(musCache.lista)) musCache.lista = [];
  return musCache.lista;
}

// Serviço de cada cartão: imagem, vídeo e pessoa falando usam a ComfyUI; a música usa o painel dela + a MESMA
// ComfyUI. Cartão com serviço desligado ganha um aviso pequeno que liga na hora (o cartão continua abrindo).
// A Narração não depende de nenhum serviço que o estúdio ligue: quem liga o VoiceStudio é a
// própria tela dela (lista vazia = nunca mostra aviso de "desligado" no cartão do Início).
const SERV_DO_CARTAO = { imagem: ['video'], video: ['video'], apresentador: ['video'], voz: ['voz'], canal: [], plano: ['video'], musica: ['painel_musica', 'video'] };
const ACAO_DO_SERV = { voz: 'voz', video: 'video', painel_musica: 'musica', hermes: 'hermes', telegram: 'telegram' };
function estadoDoGrupo(chaves) {
  const S = servicosDe(G.inicio);
  const est = chaves.map((k) => S.find((s) => s.chave === k)).filter(Boolean);
  if (!est.length) return null;
  const erro = est.find((s) => s.estado === 'erro');
  if (erro) return { estado: 'erro', mensagem: erro.mensagem };
  const lig = est.filter((s) => s.estado === 'ligando');
  if (lig.length) return { estado: 'ligando', desde: Math.min(...lig.map((s) => +s.desde || agoraServidor())) };
  const off = est.filter((s) => s.estado === 'desligado');
  if (off.length) return { estado: 'desligado', parcial: off.length < est.length };
  return { estado: 'ligado' };
}
function avisoCartao(e) {
  const g = estadoDoGrupo(SERV_DO_CARTAO[e.rota]);
  if (!g) return '';
  const musica = e.rota === 'musica', voz = e.rota === 'voz';
  const acao = musica ? 'musica' : voz ? 'voz' : 'video';
  const quem = musica ? 'a música' : voz ? 'a voz local' : 'o motor de imagem e vídeo';
  if (g.estado === 'ligando') {
    return `<span class="escolha-aviso ligando">${ic('relogio')}<span>Ligando… <span data-desde="${esc(g.desde)}">${esc(fmt(agoraServidor() - g.desde))}</span></span></span>`;
  }
  if (g.estado === 'erro' && podeLigar(acao)) {
    return `<button type="button" class="escolha-aviso erro" data-ligar="${acao}" title="${esc(g.mensagem || '')}" aria-label="${esc(e.titulo)}: ${esc(quem)} não ligou. Clique para tentar de novo.">${ic('alerta')}<span>Não ligou. Tentar de novo</span></button>`;
  }
  // 14/11/2026: a chave fica SEMPRE no cartão. Antes só aparecia um aviso quando estava
  // desligado; ligado, não havia como desligar por aqui.
  const ligado = g.estado === 'ligado';
  const rot = ligado ? 'ligado' : g.parcial ? 'parte desligada' : 'desligado';
  if (!podeLigar(acao) || (G.inicio && G.inicio.legado)) return `<span class="escolha-aviso ${ligado ? 'lig' : 'desligado'}"><span>${rot}</span></span>`;
  const attr = ligado ? `data-desligar="${musica ? 'painel' : voz ? 'voz' : 'video'}"` : `data-ligar="${acao}"`;
  return `<span class="escolha-aviso ${ligado ? 'lig' : 'desligado'}"><span>${rot}</span>`
    + `<button type="button" class="chave${ligado ? ' on' : ''}" role="switch" aria-checked="${ligado}" ${attr} `
    + `aria-label="${esc(e.titulo)}: ${ligado ? 'desligar' : 'ligar'} ${esc(quem)}"><span class="sr-only">${ligado ? 'Desligar' : 'Ligar'}</span></button></span>`;
}
/* Qual IA da seção é a mais RÁPIDA e qual é a mais CAPRICHADA (notas 1 a 5 da ficha).
   Empate desempata pela outra nota. Quando a mesma IA ganha nas duas, sai uma linha só —
   dizer duas vezes o mesmo nome parece defeito. */
function destaques(lista) {
  const com = (lista || []).filter((f) => f && (f.nota_velocidade || f.nota_qualidade));
  if (com.length < 2) return null;
  const por = (a, b) => (x, y) => (y[a] || 0) - (x[a] || 0) || (y[b] || 0) - (x[b] || 0);
  const vel = [...com].sort(por('nota_velocidade', 'nota_qualidade'))[0];
  const qua = [...com].sort(por('nota_qualidade', 'nota_velocidade'))[0];
  return { vel, qua, mesma: vel.id === qua.id };
}
function htmlDestaques(lista) {
  const d = destaques(lista);
  if (!d) return '';
  const tag = (cls, icone, rot, f) =>
    `<span class="nota-tag ${cls}">${ic(icone)}<span>${rot}: <b>${esc(nomeCurto(f.nome))}</b></span></span>`;
  if (d.mesma) return `<span class="escolha-notas">${tag('dupla', 'raio', TX('A mais rápida e a mais caprichada'), d.vel)}</span>`;
  return `<span class="escolha-notas">${tag('rapida', 'velocidade', TX('Mais rápida'), d.vel)}`
    + `${tag('fina', 'estrela', 'Mais caprichada', d.qua)}</span>`;
}

/* ---------------------------------------------------------------- Novidades
   Vem de /api/novidades (arquivo estudio/novidades.json). Mostra 3 e abre o resto no
   botão. Se o servidor não tiver a rota — versão antiga — o bloco some em vez de dar erro. */
const ETIQUETA_NOV = { novidade: 'novidade', ias: 'IAs', dica: 'dica', aviso: 'aviso' };
const NOV_INICIAIS = 5;

function dataCurta(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  return m ? `${m[3]}/${m[2]}/${m[1].slice(2)}` : '';
}
function renderNovidades() {
  const bloco = $('#blocoNovidades'), lista = $('#novLista');
  if (!bloco || !lista) return;
  const todas = G.novidades || [];
  bloco.hidden = todas.length === 0;
  if (!todas.length) return;
  bloco.classList.toggle('todas', !!G.novTodas);
  const mostrar = G.novTodas ? todas : todas.slice(0, NOV_INICIAIS);
  lista.innerHTML = mostrar.map((n, i) => {
    const et = ETIQUETA_NOV[n.etiqueta] || n.etiqueta || '';
    return `<details class="nov ${n.destaque && i === 0 ? 'destaque' : ''}">
      <summary>
        <span class="nov-cab">
          ${et ? `<span class="nov-et et-${esc(n.etiqueta || 'novidade')}">${esc(et)}</span>` : ''}
          <span class="nov-data">${esc(dataCurta(n.data))}</span>
        </span>
        <h3>${esc(n.titulo)}</h3>
      </summary>
      ${n.texto ? `<p>${esc(n.texto)}</p>` : ''}
    </details>`;
  }).join('');
  const bt = $('#novVerTodas');
  if (bt) {
    bt.hidden = todas.length <= NOV_INICIAIS;
    bt.textContent = G.novTodas ? 'Ver menos' : `Ver todas (${todas.length})`;
  }
}
async function carregarNovidades() {
  try {
    const d = await api('/api/novidades', { timeout: 9000 });
    G.novidades = Array.isArray(d) ? d : [];
  } catch (e) { G.novidades = []; }   // servidor antigo: o bloco simplesmente não aparece
  renderNovidades();
}

// a tira ao vivo embaixo do título da Forja: a máquina de verdade, não enfeite
function renderHeroi() {
  const el = $('#heroiTiras');
  if (!el) return;
  const S = (G.inicio && G.inicio.sistema) || G.sistema || {};
  const c = (G.inicio && G.inicio.contagem) || {};
  const ias = G.presets ? (presetsDa('imagem').length + presetsDa('video').length
    + presetsDa('apresentador').length + presetsDa('plano').length) : 0;
  const feitas = ['imagens', 'videos', 'musicas'].reduce((t, k) => t + (+c[k] || 0), 0);
  const cab = G.cab || {};
  const tiras = [];
  // 14/11/2026: dizia "17 IAs prontas" contando o CATALOGO, com 4 instaladas. A placa e a
  // memoria sairam daqui: agora moram nos medidores de "Sua máquina", logo ao lado.
  const estados = Object.values(G.ias || {});
  if (estados.length) {
    const prontas = estados.filter((e) => e.instalada).length;
    tiras.push(`<span class="heroi-tira">${ic('brilho')}<span><b>${prontas}</b> de ${estados.length} IAs instaladas</span></span>`);
  } else if (ias) tiras.push(`<span class="heroi-tira">${ic('brilho')}<span><b>${ias}</b> IAs no catálogo</span></span>`);
  if (feitas) tiras.push(`<span class="heroi-tira">${ic('ok')}<span><b>${num(feitas, 0)}</b> criações até agora</span></span>`);
  tiras.push(`<span class="heroi-tira viva"><i class="ponto ${cab.rodando ? 'ocupado' : 'on'}"></i>`
    + `<span>${cab.rodando ? 'forjando agora' : 'placa livre'}</span></span>`);
  const html = tiras.join('');
  if (el._sig !== html) { el._sig = html; el.innerHTML = html; }
}

function renderEscolhas(forcar) {
  const cont = (G.inicio && G.inicio.contagem) || {};
  const avisos = ESCOLHAS.map((e) => { const g = estadoDoGrupo(SERV_DO_CARTAO[e.rota]); return g ? [g.estado, g.parcial, g.mensagem] : null; });
  const sig = JSON.stringify([cont, Object.keys(G.fichas).length, !!G.presets, avisos, podeLigar('video'), podeLigar('musica'),
    Object.keys(G.ias || {}).filter((k) => G.ias[k].instalada)]);
  if (!forcar && sig === renderEscolhas.sig) return;
  renderEscolhas.sig = sig;
  // botão focado (teclado) volta a ter o foco depois de redesenhar: guarda em qual cartão ele estava
  const focado = document.activeElement && document.activeElement.closest('#escolhas [data-ligar]');
  const foco = focado ? $$('#escolhas .escolha-caixa').indexOf(focado.closest('.escolha-caixa')) : -1;
  // a Música é um projeto separado: sem ele, o cartão e o link somem em vez de dar erro
  const temMusica = !G.inicio || G.inicio.tem_musica !== false;
  document.querySelectorAll('[data-rota="musica"]').forEach((a) => { a.hidden = !temMusica; });
  // mesma ideia da Musica: o cartao do Plano-sequencia so existe se a IA dele estiver
  // instalada. No pacote do GitHub ela nao viaja, e um cartao que nao abre parece defeito.
  const temPlano = !G.presets || presetsDa('plano').length > 0;
  const visiveis = ESCOLHAS.filter((e) => (temMusica || e.rota !== 'musica') && (temPlano || e.rota !== 'plano'));
  $('#escolhas').dataset.n = visiveis.length;      // o CSS escolhe as colunas para nao sobrar cartao sozinho
  $('#escolhas').innerHTML = visiveis.map((e) => {
    const todas = e.rota === 'musica' ? G.fichasMusica : presetsDa(e.rota).map(fichaOuPreset);
    // 14/11/2026: o cartao recomendava IA que nem estava no disco ("Recomendada: LTX 2.5"
    // numa instalacao sem ele). Sem informacao de instalacao (servidor antigo), vale a lista toda.
    const sei = (f) => G.ias && G.ias[f.id];
    const lista = todas.filter((f) => !sei(f) || G.ias[f.id].instalada);
    const controladas = todas.filter(sei).length;
    const nenhuma = controladas > 0 && lista.length === 0;
    const rec = lista.find((f) => f.id === RECOMENDADA[e.rota]) || lista[0];
    const n = todas.length;
    const qtd = e.rota === 'imagem' ? cont.imagens : e.rota === 'video' ? cont.videos : e.rota === 'musica' ? cont.musicas : null;
    const tempo = rec ? tempoCurto(rec) : '';
    const quantas = !n ? '' : controladas ? `${lista.length} de ${n} IAs instaladas` : `${n} IA${n > 1 ? 's' : ''}`;
    const pe = [quantas, qtd ? `${qtd} criaç${qtd === 1 ? 'ão' : 'ões'}` : ''].filter(Boolean).join(' · ');
    // o aviso de serviço desligado é IRMÃO do link (botão dentro de link não é permitido), posicionado sobre o cartão
    return `<div class="escolha-caixa">
      <a class="escolha ${e.tipo}${nenhuma ? ' sem-ia' : ''}" href="#/${e.rota}" aria-label="${esc(TX(e.titulo))}: ${esc(TX(e.frase))}">
      <span class="escolha-ic">${ic(e.icone)}</span>
      <h2>${esc(TX(e.titulo))}</h2>
      <p class="escolha-frase">${esc(TX(e.frase))}</p>
      <span class="escolha-rec">
        ${nenhuma ? `<span class="linha-ic falta">${ic('baixar')}<span>Nenhuma IA desta seção está instalada ainda.</span></span>` : ''}
        ${rec ? `<span class="linha-ic">${ic('estrela')}<span>Recomendada: <b>${esc(nomeCurto(rec.nome))}</b></span></span>` : ''}
        ${tempo ? `<span class="linha-ic">${ic('relogio')}<span>${esc(tempo)}</span></span>` : ''}
        ${!G.presets && e.rota !== 'musica' && e.rota !== 'voz' ? `<span class="linha-ic">${ic('relogio')}<span>Carregando as IAs…</span></span>` : ''}
      </span>
      ${htmlDestaques(lista)}
      <span class="escolha-pe"><span>${esc(pe)}</span><span class="escolha-ir">${ic('seta')}</span></span>
    </a>${avisoCartao(e)}</div>`;
  }).join('');
  if (foco >= 0) { const b = $$('#escolhas .escolha-caixa')[foco]; const bt = b && b.querySelector('[data-ligar]'); if (bt) bt.focus(); }
}

function renderInicioVivo() {
  renderHeroi();
  renderEscolhas();
  renderRecentes();
  renderMaquina();
}

function renderRecentes() {
  const I = G.inicio || {};
  const est = (I.recentes || []).map((j) => ({ t: j.fim || j.criado || 0, j }));
  const mus = (Array.isArray(I.musicas_recentes) ? I.musicas_recentes : []).map((m) => ({ t: +m.criado || 0, m }));
  const itens = [...est, ...mus].sort((a, b) => b.t - a.t).slice(0, 12);
  const sig = itens.map((x) => (x.j ? x.j.id + (sumiu(x.j) ? '!' : '') : 'm' + x.m.id)).join(',');
  const total = itens.length;
  $('#contConta').textContent = total ? `${total} criaç${total === 1 ? 'ão' : 'ões'} mais recente${total === 1 ? '' : 's'}` : '';
  if (sig === renderRecentes.sig) return;
  renderRecentes.sig = sig;
  $('#recentes').classList.toggle('vazia', !itens.length);
  // o visualizador só percorre o que tem arquivo no HD
  G.listaRecentes = itens.filter((x) => x.j && !sumiu(x.j)).map((x) => x.j);
  G.musRecentes = itens.filter((x) => x.m).map((x) => x.m);
  if (!itens.length) {
    $('#recentes').innerHTML = `<div class="vazio-inicio">
      <span class="vazio-ic">${ic('brilho')}</span>
      <p><b>Nada criado ainda</b></p>
      <p class="fraco">O que você gerar aparece aqui, para abrir de novo com um clique.</p>
      <span class="vazio-acoes"><a class="bt-sec" href="#/imagem">${ic('imagem')}Criar uma imagem</a><a class="bt-sec" href="#/video">${ic('video')}Criar um vídeo</a></span>
    </div>`;
    return;
  }
  let iE = 0, iM = 0;
  const semArquivo = `<span class="recente-sumiu">${ic('alerta')}<small>Arquivo não encontrado no HD</small></span>`;
  $('#recentes').innerHTML = itens.map((x) => {
    if (x.j) {
      const j = x.j, rota = rotaDoJob(j), s = (j.saidas || [])[0] || {}, url = j.midia || urlMidia(j);
      const levou = decorrido(j), voz = rota === 'apresentador' ? vozCurta(j) : null;
      const selo = `<span class="selo"><span>${esc(seloTexto(j))}</span></span>`;
      const txt = `<span class="recente-txt"><b>${esc(j.prompt || '(sem prompt)')}</b><small>${voz ? esc(voz) + ' · ' : ''}${esc(quando(j.fim || j.criado))}${levou != null ? ' · levou ' + esc(fmt(levou)) : ''}</small></span>`;
      if (sumiu(j)) {
        return `<div class="recente ${tipoDaRota(rota)} sem-arquivo" data-id="${esc(j.id)}"><span class="recente-midia">${semArquivo}${selo}</span>${txt}</div>`;
      }
      const idx = iE++;
      const midia = ehVideo(s.arquivo)
        ? `<video src="${esc(url)}#t=0.1" muted playsinline preload="metadata" aria-hidden="true"></video>`
        : `<img src="${esc(url)}" alt="" loading="lazy" decoding="async">`;
      return `<button type="button" class="recente ${tipoDaRota(rota)}" data-lupa="${idx}" data-id="${esc(j.id)}" aria-label="Ver ${esc(seloTexto(j))}${voz ? ' (' + esc(voz) + ')' : ''}: ${esc(String(j.prompt || '').slice(0, 80))}">
        <span class="recente-midia">${midia}${selo}</span>${txt}
      </button>`;
    }
    const m = x.m, idx = iM++;
    const det = [duracaoMusica(m.duracao_s), m.instrumental ? 'instrumental' : 'com voz', quando(m.criado)].filter(Boolean).join(' · ');
    return `<div class="recente t-musica">
      <span class="recente-midia"><span class="recente-arte">${ic('onda')}</span><span class="selo"><span>${esc(m.motor_nome || m.motor_id || 'Música')}</span></span>
        <button type="button" class="recente-play" data-tocar="${idx}" aria-label="Tocar ${esc(m.titulo || 'música')}">${ic('play')}</button></span>
      <a class="recente-txt" href="#/musica"><b>${esc(m.titulo || 'Música sem título')}</b><small>${esc(det)}</small></a>
    </div>`;
  }).join('');
  // mídia que não carrega: confirma com o servidor e, se sumiu mesmo (404), troca por um aviso (sem quadro preto)
  $$('#recentes [data-id] .recente-midia img, #recentes [data-id] .recente-midia video').forEach((el) => {
    el.addEventListener('error', () => {
      const id = el.closest('[data-id]').dataset.id;
      confirmarSumico(id, () => { renderRecentes.sig = null; renderRecentes(); });
    }, { once: true });
  });
  atualizarBotoesPlay();
}
// a mídia deu erro: só marca como "sumiu" se o servidor responder 404 (servidor reiniciando não conta)
async function confirmarSumico(id, depois) {
  if (G.sumidos.has(id)) return;
  try {
    const r = await fetch(urlMidia({ id }), { method: 'HEAD', cache: 'no-store' });
    if (r.status !== 404) return;
  } catch (e) { return; }
  G.sumidos.add(id);
  if (depois) depois();
}
function tocar(idx) {
  const m = G.musRecentes[idx];
  if (!m || !m.url) return;
  if (!G.audio) {
    G.audio = new Audio();
    ['play', 'pause', 'ended'].forEach((ev) => G.audio.addEventListener(ev, atualizarBotoesPlay));
    G.audio.addEventListener('error', () => {
      if (!G.audio.getAttribute('src')) return;
      // não ficou tocando: o botão volta para "Tocar"
      G.tocando = null;
      G.audio.removeAttribute('src');
      atualizarBotoesPlay();
      aviso('Não consegui tocar essa música (o painel de música está ligado?).', 'erro');
    });
  }
  const a = G.audio;
  if (G.tocando === m.id && !a.paused) { a.pause(); return; }
  if (G.tocando !== m.id) { a.src = m.url; G.tocando = m.id; }
  a.play().catch(() => {});
}
function atualizarBotoesPlay() {
  $$('[data-tocar]').forEach((b) => {
    const m = G.musRecentes[+b.dataset.tocar];
    const on = !!(m && G.audio && G.tocando === m.id && !G.audio.paused);
    b.innerHTML = ic(on ? 'pausa' : 'play');
    b.setAttribute('aria-label', `${on ? 'Pausar' : 'Tocar'} ${(m && m.titulo) || 'música'}`);
  });
}

function medidor(usado) {
  const f = Math.max(0, Math.min(1, usado || 0));
  return `<div class="medidor${f > 0.9 ? ' alto' : f > 0.75 ? ' medio' : ''}" aria-hidden="true"><i style="width:${(f * 100).toFixed(1)}%"></i></div>`;
}
function linhaMaq(icone, rotulo, valor, extra = '') {
  return `<div class="maq-linha"><span class="ic-caixa">${ic(icone)}</span><div><div class="maq-rot"><span>${rotulo}</span><b>${valor}</b></div>${extra}</div></div>`;
}
function renderMaquina() {
  const I = G.inicio;
  if (!I) return;
  const S = I.sistema || {}, F = I.fila || {};
  renderSemResposta();
  // placa, memórias e discos (a placa aparece mesmo com a ComfyUI desligada: o servidor lê no nvidia-smi)
  const h = [];
  // 14/11/2026: era uma coluna de 5 linhas e 869 px. Agora sao medidores lado a lado, e o
  // disco deixou de se chamar "E: (projeto)" com os numeros do C:.
  const win = !I.plataforma || I.plataforma === 'windows';
  const uni = S.gpu_memoria === 'unificada';
  const medida = (rotulo, forte, fraco, usado, alerta = '') =>
    `<div class="medida"><div class="medida-topo"><span>${rotulo}</span><b>${forte}</b></div>`
    + `${usado != null ? medidor(usado) : ''}<small>${fraco}</small>${alerta}</div>`;
  h.push(`<p class="maq-gpu">${ic('placa')}<span>${esc(S.gpu || (uni ? 'Chip (GPU) não encontrado' : 'Placa de vídeo não encontrada'))}</span></p>`);
  const vT = gb(S.vram_total), vL = gb(S.vram_livre);
  if (vT) h.push(medida(uni ? 'Memória da GPU' : 'Memória da placa', `${num(vL)} GB`, `livres de ${num(vT)} GB`, 1 - vL / vT));
  const rT = gb(S.ram_total_gb), rL = gb(S.ram_livre_gb);
  if (rT) h.push(medida('Memória RAM', `${num(rL)} GB`, `livres de ${num(rT, 0)} GB`, 1 - rL / rT));
  const disco = (d, rotulo) => {
    if (!d || d.livre_gb == null) return;
    const pouco = d.livre_gb < 50;
    h.push(medida(win ? `${rotulo} (${esc(d.unidade)}:)` : rotulo, `${num(d.livre_gb, 0)} GB`,
      d.total_gb ? `livres de ${num(d.total_gb, 0)} GB` : 'livres', d.total_gb ? 1 - d.livre_gb / d.total_gb : null,
      pouco ? `<p class="maq-alerta">${ic('alerta')}<span>Menos de 50 GB: vídeo e modelo novo podem não caber.</span></p>` : ''));
  };
  if (S.disco_ias || S.disco_painel) {
    const mesmo = S.disco_ias && S.disco_painel && S.disco_ias.unidade === S.disco_painel.unidade;
    if (mesmo) disco(S.disco_ias, 'Disco');
    else { disco(S.disco_ias, 'Disco das IAs'); disco(S.disco_painel, 'Disco do painel'); }
  } else if (win) {      // servidor antigo: so sabe o disco do painel (que chamava de "E:") e o C:
    const eT = gb(S.disco_e_total_gb), eL = gb(S.disco_e_livre_gb), cL = gb(S.disco_c_livre_gb);
    if (eL != null) h.push(medida('Disco do painel', `${num(eL, 0)} GB`, eT ? `livres de ${num(eT, 0)} GB` : 'livres', eT ? 1 - eL / eT : null));
    if (cL != null && cL !== eL) h.push(medida('Disco C:', `${num(cL, 0)} GB`, 'livres', null));
  }
  const hw = h.join('');
  if (hw !== renderMaquina.hw) { $('#maqHw').innerHTML = hw; renderMaquina.hw = hw; }
  renderServicos();
  renderTextoMaq();
  let fila;
  if (F.rodando) {
    const r = F.rodando, g = r.progresso || {}, pct = Math.floor(g.pct || 0);
    fila = `<div class="fila-box"><p>${ic('raio')} Gerando agora: <b>${esc(seloTexto(r))}</b></p>
      <div class="barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="Progresso"><i style="width:${pct}%"></i></div>
      <small>${pct}%${g.fase ? ' · ' + esc(g.fase) : ''}${g.restante != null ? ' · falta ~' + esc(fmt(g.restante)) : ''}</small></div>`;
  } else {
    fila = `<div class="fila-box"><p>Nada gerando agora no estúdio.</p></div>`;
  }
  const extras = [];
  if (+F.na_fila) extras.push(`${F.na_fila} esperando na fila`);
  if (S.fila_comfy) extras.push(`ComfyUI com ${S.fila_comfy} na fila`);
  if (F.musica_ocupada === true) extras.push('música gerando agora (a placa está ocupada)');
  if (F.musica_ocupada === false && I.tem_musica !== false) extras.push('música livre');
  const filaHtml = '<a class="fila-abrir" href="#/fila">Abrir a fila</a>' + linhaMaq('fila', 'Fila', '', fila + (extras.length ? `<p class="nota" style="margin-top:6px">${esc(extras.join(' · '))}</p>` : ''));
  if (filaHtml !== renderMaquina.fila) { $('#maqFila').innerHTML = filaHtml; renderMaquina.fila = filaHtml; }
  const ocupado = !!F.rodando || +F.na_fila > 0;
  const bl = $('#btLiberar');
  bl.setAttribute('aria-disabled', String(ocupado));
  bl.title = ocupado ? 'Espere a geração terminar para liberar a memória.' : '';
  $('#maqParcial').hidden = !I.parcial;
  $('#liberarTextoNota').hidden = !!I.legado;
  const auto = +I.liberar_memoria_min || 0;
  // motor desligado = nada carregado na placa: dizer "libera em 10 min" ali seria prometer o que já aconteceu
  const motorOff = ((I.servicos || {}).video || {}).estado === 'desligado';
  $('#maqAuto').textContent = motorOff ? TX('já está livre: o motor está desligado')
    : I.memoria_liberada ? 'já está liberada'
    : auto > 0 ? `libera sozinha em ${num(auto, 0)} min` : '';
}
// aviso discreto quando o estúdio não responde: a tela continua com o que já tinha e tenta de novo sozinha
function renderSemResposta() {
  const sem = (G.falhas || 0) >= FALHAS_AVISO;
  const el = $('#maqSemResposta');
  if (el) el.hidden = !sem;
  $('#maqAoVivo').classList.toggle('parado', sem);
  if (sem && !G.inicio) {
    renderRecentes.sig = null;
    $('#recentes').innerHTML = '<p class="vazio-inicio">Sem resposta do estúdio agora. Tentando de novo sozinho…</p>';
  }
}

// ---------------------------------------------------------------- serviços: "Ligar" em cada um e "Ligar tudo"
const agoraServidor = () => Date.now() / 1000 + (G.relogioDif || 0);
const ORDEM_SERV = ['video', 'painel_musica', 'voz', 'hermes', 'telegram'];
const NOME_SERV = { voz: 'Voz e clone de voz (VoiceStudio)', video: 'Imagem e vídeo (ComfyUI)', painel_musica: 'Painel de música', hermes: 'Hermes (IA que conversa)', telegram: 'Telegram do Hermes (avisos no celular)' };
const LEGADO_MSG = 'Esta versão do servidor do estúdio ainda não liga os serviços pelo Início. Feche o estúdio pelo atalho “Desligar Estúdio” (com nada gerando) e abra de novo para ativar os botões.';
// [{chave, nome, estado, desde, mensagem, lento, porta}] do /api/inicio; servidor antigo: só ligado/desligado
function servicosDe(I) {
  if (!I) return [];
  const novo = !I.legado && I.servicos && typeof I.servicos === 'object';
  const sv = (I.sistema || {}).servicos || {};
  return ORDEM_SERV.map((k) => {
    if (novo && I.servicos[k]) return { chave: k, nome: NOME_SERV[k], ...I.servicos[k] };
    if (sv[k] == null) return null;
    return { chave: k, nome: NOME_SERV[k], estado: sv[k] ? 'ligado' : 'desligado' };
  }).filter(Boolean);
}
// o botão Ligar funciona? Servidor novo: sempre. Antigo: só a música com o painel desligado (/api/musica/ligar)
function podeLigar(acao) {
  const I = G.inicio;
  if (!I) return false;
  if (!I.legado) return true;
  return acao === 'musica' && ((I.sistema || {}).servicos || {}).painel_musica === false;
}
// 14/11/2026 (padronizar): no cartão vai o nome CURTO, para todos caberem na mesma fileira e do mesmo
// tamanho. O nome inteiro (com "ComfyUI", "VoiceStudio") fica na dica do mouse e no leitor de tela.
const NOME_CURTO_MOTOR = { video: 'Imagem e vídeo', painel_musica: 'Música', voz: 'Voz', hermes: 'Hermes', telegram: 'Telegram' };
const ICONE_DO_MOTOR = { voz: 'onda', video: 'video', painel_musica: 'musica', comfy_musica: 'musica', ace: 'musica', hermes: 'servidor', telegram: 'enviar' };
function linhaServico(s) {
  const acao = ACAO_DO_SERV[s.chave] || 'video';
  const legado = G.inicio && G.inicio.legado;
  const cab = (cls, estado, direita, msg = '') => `<div class="servico motor ${cls}">
      <span class="motor-ic">${ic(ICONE_DO_MOTOR[s.chave] || 'servidor')}</span>
      <div class="motor-txt"><b class="servico-nome" title="${esc(TX(s.nome))}${s.porta ? ` · ${esc(TX('porta'))} ${esc(s.porta)}` : ''}">${esc(TX(NOME_CURTO_MOTOR[s.chave] || s.nome))}</b>
        <small class="servico-estado">${estado}</small></div>
      <span class="motor-acao">${direita}</span>${msg}</div>`;
  const chave = (ligado, attr, rotulo) => `<button type="button" class="chave${ligado ? ' on' : ''}" role="switch" aria-checked="${ligado}" ${attr}
      aria-label="${esc(rotulo)}: ${esc(TX(s.nome))}"><span class="sr-only">${esc(rotulo)}</span></button>`;
  if (s.estado === 'ligado') {
    const alvoD = ALVO_DESLIGAR[s.chave];
    const btD = alvoD && !legado ? chave(true, `data-desligar="${alvoD}" title="${esc(TX('Desliga para liberar memória; liga de novo pelo botão Ligar'))}"`, TX('Desligar')) : '';
    const abrir = s.chave === 'hermes'
      ? `<a class="bt-ligar" href="${esc(s.url || 'http://127.0.0.1:9119/?profile=default')}" target="_blank" rel="noopener" aria-label="${esc(TX('Abrir o Hermes no navegador'))}" title="${esc(TX('Abrir o painel do Hermes'))}">${ic('seta')}<span>${esc(TX('Abrir'))}</span></a>` : '';
    return cab('on', s.lento ? 'ligado, respondendo devagar' : 'ligado', abrir + btD);
  }
  if (s.estado === 'ligando') {
    const d = +s.desde || agoraServidor();
    const demora = s.demorando && s.mensagem ? `<p class="servico-msg demora">${ic('relogio')}<span>${esc(s.mensagem)}</span></p>` : '';
    return cab('ligando', `ligando… <span data-desde="${esc(d)}">${esc(fmt(agoraServidor() - d))}</span>`,
      '<span class="chave on ocupada" aria-hidden="true"></span>', demora);
  }
  const erro = s.estado === 'erro';
  const bt = podeLigar(acao) ? chave(false, `data-ligar="${acao}" data-servico="${esc(s.chave)}"`, erro ? 'Tentar ligar de novo' : 'Ligar') : '';
  if (s.estado === 'em espera') {  // economia de memória: liga sozinho quando precisa (não é defeito)
    return cab('espera', 'em espera', bt, `<p class="servico-msg em-espera">${ic('relogio')}<span>${esc(s.mensagem || 'Liga sozinho quando precisar.')}</span></p>`);
  }
  if (erro) return cab('erro', 'não ligou', bt, `<p class="servico-msg">${ic('alerta')}<span>${esc(s.mensagem || 'Não ligou.')}</span></p>`);
  return cab('off', 'desligado', bt);
}
function renderServicos() {
  const I = G.inicio, lista = servicosDe(I);
  $('#maqServLinha').hidden = !lista.length;
  if (!lista.length) return;
  const sig = JSON.stringify([lista.map((s) => [s.chave, s.estado, s.mensagem || '', !!s.lento, !!s.demorando, Math.round(+s.desde || 0)]),
    podeLigar('video'), podeLigar('musica')]);
  if (sig !== renderServicos.sig) {
    renderServicos.sig = sig;
    const focado = document.activeElement && document.activeElement.closest('#maqServ [data-servico]');
    const foco = focado ? focado.dataset.servico : null;
    $('#maqServ').innerHTML = lista.map(linhaServico).join('');
    // na bancada do herói as explicações ficam lado a lado: duas iguais seguidas viram uma só.
    const vistos = new Set();
    $$('#maqServ .servico-msg').forEach((el) => {
      const t = el.textContent.trim();
      if (vistos.has(t)) el.remove(); else vistos.add(t);
    });
    if (foco) { const b = $(`#maqServ [data-servico="${foco}"]`); if (b) b.focus(); }
  }
  // "Ligar tudo" só quando algum dos serviços está desligado (a IA de texto tem o próprio "Ligar agora"; em espera
  // ela não conta, senão o botão aparecia com tudo ligado, logo depois de o dono desligá-la de propósito)
  const off = lista.some((s) => !['hermes', 'telegram', 'voz'].includes(s.chave) && (s.estado === 'desligado' || s.estado === 'erro'));
  $('#btLigarTudo').hidden = I.legado || !off;
  // atalhos por grupo: "Ligar imagem e vídeo" (ComfyUI) e "Ligar música" (o painel de música + a mesma ComfyUI)
  const est = (k) => (lista.find((s) => s.chave === k) || {}).estado;
  const desl = (k) => ['desligado', 'erro'].includes(est(k));
  const verVideo = !I.legado && desl('video');
  const verMusica = !I.legado && desl('painel_musica');
  $('#btLigarVideo').hidden = !verVideo;
  $('#btLigarMusicaGrupo').hidden = !verMusica;
  $('#maqGrupos').hidden = !(verVideo || verMusica);
  const algumLigado = lista.some((s) => s.estado === 'ligado' && !['painel_musica', 'hermes', 'telegram', 'voz'].includes(s.chave))
    || ((I.texto || {}).simples || {}).estado === 'pronta';
  $('#btDesligarTudo').hidden = I.legado || !algumLigado;
  const nota = $('#maqServNota');
  nota.hidden = !(I.legado && off && !podeLigar('musica'));
  nota.textContent = nota.hidden ? '' : TX(LEGADO_MSG);
}
const LIGANDO_CLIQUE = new Set();  // trava contra dois cliques (o servidor também não liga em dobro)
const FRASE_LIGAR = { voz: 'Ligando a voz local (uns 30 segundos)…', video: 'Ligando a ComfyUI de imagem e vídeo (leva 1–2 min)…', musica: 'Ligando a música (o painel e a ComfyUI)…',
  texto: 'Ligando a IA de texto no processador…', hermes: 'Ligando o Hermes (painel web, uns 6 s)…', telegram: 'Ligando o Telegram do Hermes (uns 20 s)…', tudo: 'Ligando o que estava desligado…' };
const ALVO_DESLIGAR = { voz: 'voz', video: 'video', painel_musica: 'painel', hermes: 'hermes' };
async function desligarServico(alvo, bt) {
  if (alvo === 'tudo' && !confirm(TX('Desligar todas as IAs para liberar memória? (A página continua aberta. Para usar de novo, clique em Ligar.)'))) return;
  const antes = bt ? bt.innerHTML : null;
  if (bt) { bt.disabled = true; const sp = bt.querySelector('span'); if (sp) sp.textContent = TX('Desligando…'); }
  try {
    const r = await api('/api/servicos/desligar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ servico: alvo }), timeout: 60000 });
    if (G.inicio && r) {
      if (r.servicos && Object.keys(r.servicos).length) G.inicio.servicos = r.servicos;
      if (r.texto && G.inicio.texto) G.inicio.texto.simples = r.texto;
    }
    // r.mensagem vem do servidor: fica em portugues ate o server.py ser traduzido.
    aviso((r && r.mensagem) || TX('Desligado.'), 'ok');
  } catch (e) {
    aviso(e.status === 404 ? 'Para ter o botão Desligar, feche e abra o estúdio de novo.' : e.message, 'erro', 8000);
  } finally {
    if (bt && bt.isConnected) { bt.disabled = false; bt.innerHTML = antes; }
    renderServicos.sig = null;
    renderEscolhas.sig = null;
  }
}
async function ligarServico(acao, bt) {
  if (LIGANDO_CLIQUE.has(acao)) return;
  if (G.inicio && G.inicio.legado) {
    if (acao === 'musica' && podeLigar('musica')) { ligarMusica(bt); return; }
    aviso(LEGADO_MSG, 'aviso', 10000);
    return;
  }
  LIGANDO_CLIQUE.add(acao);
  const btAntes = bt ? bt.innerHTML : null;
  if (bt) {
    bt.disabled = true;
    bt.setAttribute('aria-busy', 'true');
    const sp = bt.querySelector('span');
    if (sp) sp.textContent = 'Ligando…';
  }
  try {
    const r = await api('/api/servicos/ligar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ servico: acao }), timeout: 30000 });
    if (G.inicio && r) {
      if (r.servicos && Object.keys(r.servicos).length) G.inicio.servicos = r.servicos;
      if (r.texto && G.inicio.texto) G.inicio.texto.simples = r.texto;
    }
    aviso(r && r.ligando && r.ligando.length ? FRASE_LIGAR[acao] : 'Já estava ligado (ou ligando).', 'ok');
  } catch (e) {
    if (e.status === 404) { if (G.inicio) G.inicio.legado = true; aviso(LEGADO_MSG, 'aviso', 10000); }
    else aviso('Não consegui ligar agora: ' + e.message, 'erro');
  } finally {
    LIGANDO_CLIQUE.delete(acao);
    if (bt && bt.isConnected) { bt.disabled = false; bt.removeAttribute('aria-busy'); bt.innerHTML = btAntes; }
    renderServicos.sig = null;
    renderEscolhas.sig = null;
    renderTextoMaq.sig = null;
    if (G.inicio) renderInicioVivo();
    pulso();
  }
}

// ---------------------------------------------------------------- IA de texto: Pronta / Em espera / Ligando…
const TAREFA_ROT = { melhorar_prompt: 'melhorar prompt', letra: 'letra', roteiro: 'texto/roteiro', traduzir: 'tradução',
  descrever_imagem: 'descrever imagem', livre: 'pergunta' };
function textoSimplesDe(T) {
  if (T.simples && T.simples.estado) return T.simples;
  // servidor antigo: deduz do estado detalhado (sem os botões de ligar/desligar)
  const C = T.processador || {};
  if (!T.instalado) return { estado: 'erro', mensagem: 'A IA de texto não está instalada por completo.', legado: true };
  if (T.na_placa) return { estado: 'na placa agora', legado: true };
  if (C.ligado) return { estado: 'pronta', processador_ligado: true, legado: true };
  return { estado: 'em espera', legado: true };
}
function renderTextoMaq() {
  const I = G.inicio, T = I && I.texto;
  $('#maqTextoLinha').hidden = !T;
  if (!T) return;
  // 14/11/2026: numa instalacao nova esta linha dizia "Não ligou", em vermelho, com o
  // caminho de um .exe. Nao e erro: e uma IA opcional que ainda nao foi baixada.
  const naoInst = T.instalado === false;
  $('#btTextoInstalar').hidden = !naoInst;
  $('#textoDetalhes').hidden = naoInst;
  $('#textoOpcoes').hidden = naoInst;
  if (naoInst) {
    if (renderTextoMaq.sig === 'nao-instalada') return;
    renderTextoMaq.sig = 'nao-instalada';
    $('#textoStatus').innerHTML = `<i class="ponto parado" aria-hidden="true"></i><span><b>Não instalada</b> · opcional</span>`;
    $('#textoExtra').innerHTML = '<span>Melhora o seu prompt, traduz e descreve imagem, tudo na sua máquina.</span>';
    $('#textoExtra').hidden = false;
    $('#btTextoLigar').hidden = true;
    $('#btTextoDesligar').hidden = true;
    $('#textoAcoes').hidden = false;
    $('#textoNotaRam').hidden = true;
    $('#textoSempreRot').hidden = true;
    return;
  }
  const s = textoSimplesDe(T), legado = !!s.legado || !!I.legado;
  const P = T.placa || {}, C = T.processador || {}, M = T.modelos || {}, u = T.ultimo, vr = T.vram_depois_de_descarregar;
  const nomes = Object.values(M).map((m) => `${m.nome}${m.instalado ? '' : ' (falta baixar)'}`).join(' e ');
  const pref = I.preferencias || null;
  const sig = JSON.stringify([s.estado, s.mensagem || '', Math.round(+s.desde || 0), s.fase || '', !!s.processador_ligado, s.pode_ligar,
    !!s.escrevendo, !!s.desligar_pendente, legado, P, C, u, vr && vr.liberou, nomes, T.em_uso && T.em_uso.fase, pref && pref.texto_sempre_ligada]);
  if (sig === renderTextoMaq.sig) return;
  renderTextoMaq.sig = sig;
  // linha de estado, em palavras simples (vermelho só para erro de verdade)
  let st;
  if (s.estado === 'pronta') {
    st = `<i class="ponto on" aria-hidden="true"></i><span><b class="t-ok">Pronta</b>${s.escrevendo ? ' — escrevendo agora…' : ' — responde na hora, sem esperar carregar'}</span>`;
  } else if (s.estado === 'ligando') {
    const d = +s.desde || agoraServidor();
    st = `<i class="ponto ocupado" aria-hidden="true"></i><span><b class="t-aviso">Ligando…</b> <span data-desde="${esc(d)}">${esc(fmt(agoraServidor() - d))}</span></span>`;
  } else if (s.estado === 'na placa agora') {
    st = `<i class="ponto ocupado" aria-hidden="true"></i><span><b class="t-aviso">Na placa agora</b> — escrevendo; sai da placa sozinha ao terminar</span>`;
  } else if (s.estado === 'erro') {
    st = `<i class="ponto off" aria-hidden="true"></i><span><b class="t-erro">Não ligou</b></span>`;
  } else {
    st = `<i class="ponto parado" aria-hidden="true"></i><span><b>Em espera</b> — liga sozinha quando você usar</span>`;
  }
  $('#textoStatus').innerHTML = st;
  const extra = [];
  if (s.estado === 'ligando') extra.push(esc(s.fase || 'Carregando o Qwen3.5-9B no processador (do HD leva de 40 s a alguns minutos)') + '…');
  if (s.estado === 'erro' && s.mensagem) extra.push(`<span class="t-erro">${esc(s.mensagem)}</span>`);
  if (s.desligar_pendente) extra.push('Desliga sozinha assim que terminar o texto que está escrevendo.');
  if (legado) extra.push('Os botões Ligar agora e Desligar aparecem depois que o estúdio for reiniciado (atalho “Desligar Estúdio” com nada gerando e depois “Estúdio Local”).');
  $('#textoExtra').innerHTML = extra.map((x) => `<span>${x}</span>`).join('');
  $('#textoExtra').hidden = !extra.length;
  // botões
  const podeL = !legado && s.pode_ligar !== false && (s.estado === 'em espera' || s.estado === 'erro' || (s.estado === 'na placa agora' && !s.processador_ligado));
  const podeD = !legado && (s.processador_ligado || s.estado === 'ligando' || s.estado === 'pronta');
  const bl = $('#btTextoLigar'), bd = $('#btTextoDesligar');
  bl.hidden = !podeL;
  bl.querySelector('span').textContent = s.estado === 'erro' ? 'Tentar de novo' : 'Ligar agora';
  bd.hidden = !podeD;
  $('#textoAcoes').hidden = !podeL && !podeD;
  $('#textoNotaRam').hidden = legado;
  // preferência "sempre ligada"
  const cb = $('#chkTextoSempre');
  $('#textoSempreRot').hidden = legado || !pref;
  if (pref && !G.prefPendente && document.activeElement !== cb) cb.checked = !!pref.texto_sempre_ligada;
  // detalhes técnicos (portas etc.): recolhidos; o <details> não é recriado, então continua aberto se o dono abriu
  const det = [
    `<div class="servico"><i class="ponto ${P.carregado || (T.em_uso && T.em_uso.onde === 'placa') ? 'ocupado' : P.ligado ? 'on' : 'parado'}" aria-hidden="true"></i><span>Na placa (porta ${esc(P.porta || 8180)})</span><span class="servico-estado">${P.carregado ? esc(P.carregado) + ' carregado' : P.ligado ? 'ligada, sem modelo' : 'desligada'}</span></div>`,
    `<div class="servico"><i class="ponto ${C.ligado ? 'on' : 'parado'}" aria-hidden="true"></i><span>No processador (porta ${esc(C.porta || 8181)})</span><span class="servico-estado">${C.ligado ? esc(C.carregado || 'ligado') : 'desligado'}</span></div>`,
  ];
  if (T.em_uso && T.em_uso.fase) det.push(`<p class="nota">${esc(T.em_uso.fase)}…</p>`);
  if (u) det.push(`<p class="nota">Último pedido (${esc(TAREFA_ROT[u.tarefa] || u.tarefa)}): ${esc(u.modelo)} ${u.onde === 'placa' ? 'na placa' : 'no processador'} em ${esc(fmt(u.segundos))}${u.tokens_por_segundo ? ` · ${num(u.tokens_por_segundo, 0)} tokens/s` : ''} · ${esc(quando(u.quando))}</p>`);
  if (vr && vr.depois_mib != null) det.push(`<p class="nota">${vr.liberou ? 'Descarregada da placa no fim (conferido: a memória voltou).' : 'Atenção: a memória da placa não voltou toda depois do texto.'}</p>`);
  det.push(`<p class="nota">${esc(nomes)}. “Pronta” = o Qwen3.5-9B fica carregado no processador (memória do computador). Com a placa de vídeo livre, cada pedido roda na placa (mais rápido) e sai dela logo depois; com a placa ocupada, roda no processador sem atrapalhar a geração.</p>`);
  $('#textoDet').innerHTML = det.join('');
}
async function textoAcao(acao) {
  const bt = acao === 'ligar' ? $('#btTextoLigar') : $('#btTextoDesligar');
  if (bt.getAttribute('aria-busy') === 'true') return;  // dois cliques não fazem nada em dobro
  bt.disabled = true;
  bt.setAttribute('aria-busy', 'true');
  try {
    const r = await api(`/api/texto/${acao}`, { method: 'POST', timeout: 30000 });
    if (r && r.texto && G.inicio && G.inicio.texto) G.inicio.texto.simples = r.texto;
    aviso((r && r.mensagem) || (acao === 'ligar' ? 'Ligando a IA de texto…' : 'IA de texto desligada.'), 'ok');
  } catch (e) {
    if (e.status === 404) aviso(LEGADO_MSG, 'aviso', 10000);
    else aviso((acao === 'ligar' ? 'Não consegui ligar a IA de texto: ' : 'Não consegui desligar a IA de texto: ') + e.message, 'erro');
  } finally {
    bt.disabled = false;
    bt.removeAttribute('aria-busy');
    renderTextoMaq.sig = null;
    renderServicos.sig = null;
    if (G.inicio) renderInicioVivo();
    pulso();
  }
}
async function mudarSempreLigada(ev) {
  const cb = ev.currentTarget, v = cb.checked;
  G.prefPendente = true;
  cb.disabled = true;
  try {
    const r = await api('/api/preferencias', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto_sempre_ligada: v }), timeout: 10000 });
    if (G.inicio) G.inicio.preferencias = r;
    aviso(v ? 'Combinado: a IA de texto liga sozinha sempre que o estúdio abrir.'
      : 'Combinado: ao abrir o estúdio, a IA de texto fica em espera (liga sozinha quando você usar).', 'ok');
  } catch (e) {
    cb.checked = !v;
    aviso((e.status === 404 ? LEGADO_MSG : 'Não consegui guardar a preferência: ' + e.message), 'erro');
  } finally {
    G.prefPendente = false;
    cb.disabled = false;
    renderTextoMaq.sig = null;
  }
}
// ---------------------------------------------------------------- REPARAR (14/11/2026)
// Para quando "as IAs não respondem": o servidor encerra os motores ligados, reinicia o próprio
// painel e religa os mesmos motores. A tela espera o painel voltar, recarrega, e só então diz
// o que aconteceu com cada motor (o recado atravessa o recarregamento no sessionStorage).
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
async function repararEstudio(bt, mesmoAssim) {
  if (!mesmoAssim) {
    const sim = await confirmar({
      titulo: TX('Reparar o estúdio?'),
      texto: TX('Reinicia o painel e os motores que estão ligados, e confere se cada um voltou a responder. Leva de 1 a 2 minutos.'),
      lista: [{ txt: TX('As IAs baixadas, a sua conta e as suas criações não são tocadas'), cls: 'fica' },
        { txt: TX('Motor que está desligado continua desligado'), cls: 'fica' }],
      sim: TX('Reparar'), icone: 'reusar', perigo: false });
    if (!sim) return;
  }
  if (bt) bt.disabled = true;
  let r = null, d = null;
  try {
    r = await fetch('/api/reparar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mesmo_assim: !!mesmoAssim }) });
    d = await r.json().catch(() => ({}));
  } catch (e) {
    if (bt) bt.disabled = false;
    aviso('Não consegui falar com o estúdio para reparar. Feche o Forja e abra de novo pelo ícone.', 'erro', 9000);
    return;
  }
  if (r.status === 409 && d && Array.isArray(d.em_uso)) {
    if (bt) bt.disabled = false;
    const vai = await confirmar({
      titulo: TX('Tem trabalho em andamento'),
      texto: TX('O reparo interrompe o que está rodando agora:'),
      lista: d.em_uso.map((x) => ({ txt: TX(x), cls: 'alerta' })),
      sim: TX('Reparar mesmo assim'), nao: TX('Esperar terminar'), icone: 'alerta', perigo: true });
    if (vai) repararEstudio(bt, true);
    return;
  }
  if (!r.ok) {
    if (bt) bt.disabled = false;
    aviso((d && d.erro) || 'O estúdio não conseguiu começar o reparo.', 'erro', 9000);
    return;
  }
  aviso('Reparando… o painel reinicia e esta página volta sozinha.', 'ok', 60000);
  try { sessionStorage.setItem('forjaReparo', JSON.stringify({ religar: d.religar || [], quando: Date.now() })); } catch (e) { /* sem recado depois */ }
  await dormir(4000);
  for (let i = 0; i < 60; i++) {
    try { const x = await fetch('/api/conta/estado', { cache: 'no-store' }); if (x.ok) break; } catch (e) { /* ainda voltando */ }
    await dormir(1500);
  }
  location.reload();
}
// depois do recarregamento: acompanha os motores que o reparo religou e diz o resultado
async function resultadoDoReparo() {
  let p = null;
  try { p = JSON.parse(sessionStorage.getItem('forjaReparo') || 'null'); sessionStorage.removeItem('forjaReparo'); } catch (e) { return; }
  if (!p || Date.now() - p.quando > 180000) return;
  const quais = Array.isArray(p.religar) ? p.religar : [];
  if (!quais.length) { aviso('Reparo concluído: o painel foi reiniciado. Nenhum motor estava ligado, então nenhum foi religado.', 'ok', 12000); return; }
  const nome = (k) => NOME_CURTO_MOTOR[k] || k;
  aviso('Painel reiniciado. Religando: ' + quais.map(nome).join(', ') + '…', 'ok', 8000);
  const fim = Date.now() + 240000;
  while (Date.now() < fim) {
    await dormir(3000);
    const S = (G.inicio && G.inicio.servicos) || {};
    const est = quais.map((k) => ({ k, e: (S[k] || {}).estado, m: (S[k] || {}).mensagem }));
    const ruim = est.find((x) => x.e === 'erro');
    if (ruim) { aviso('Reparo: ' + nome(ruim.k) + ' não voltou. ' + (ruim.m || ''), 'erro', 20000); return; }
    if (est.every((x) => x.e === 'ligado')) { aviso('Reparo concluído: o painel foi reiniciado e ' + quais.map(nome).join(', ') + ' voltou a responder.', 'ok', 15000); return; }
  }
  aviso('Reparo: o painel voltou, mas algum motor ainda não respondeu depois de 4 minutos. Veja o estado em Motores.', 'aviso', 20000);
}
// "ligando… 12 s": o tempo corre na tela a cada segundo, sem esperar a próxima leitura do servidor
function tiquetaque() {
  if (document.hidden || G.rota !== 'inicio') return;
  const agora = agoraServidor();
  $$('#vInicio [data-desde]').forEach((el) => { const d = +el.dataset.desde; if (d) el.textContent = fmt(agora - d); });
}
function montarMaquina() {
  $('#maqCorpo').innerHTML = `
    <p class="maq-sem-resposta" id="maqSemResposta" role="status" hidden>${ic('relogio')}<span>Sem resposta do estúdio agora. A tela mostra o que já tinha e tenta de novo sozinha…</span></p>
    <div id="maqHw"><p class="fraco">Verificando…</p></div>
    <div class="maq-linha" id="maqServLinha" hidden>
      <span class="ic-caixa">${ic('servidor')}</span>
      <div>
        <div class="maq-rot maq-rot-bt"><span>Motores</span>
          <button type="button" class="bt-ligar bt-reparar" id="btReparar" title="${esc(TX('As IAs não respondem? Reinicia o painel e os motores ligados.'))}">${ic('reusar')}<span>${esc(TX('Reparar'))}</span></button><button type="button" class="bt-ligar bt-ligar-tudo" id="btLigarTudo" data-ligar="tudo" hidden aria-label="${esc(TX('Ligar tudo o que está desligado'))}">${ic('ligar')}<span>${esc(TX('Ligar tudo'))}</span></button><button type="button" class="bt-desligar bt-desligar-tudo" id="btDesligarTudo" data-desligar="tudo" hidden aria-label="${esc(TX('Desligar todas as IAs para liberar memória'))}">${ic('ligar')}<span>${esc(TX('Desligar tudo'))}</span></button></div>
        <div class="servicos-grupos" id="maqGrupos" hidden><button type="button" class="bt-ligar bt-ligar-grupo" id="btLigarVideo" data-ligar="video" hidden aria-label="${esc(TX('Ligar a IA de imagem e vídeo (ComfyUI)'))}">${ic('ligar')}<span>${esc(TX('Ligar imagem e vídeo'))}</span></button><button type="button" class="bt-ligar bt-ligar-grupo" id="btLigarMusicaGrupo" data-ligar="musica" hidden aria-label="${esc(TX('Ligar a música (o painel de música e a ComfyUI)'))}">${ic('ligar')}<span>${esc(TX('Ligar música'))}</span></button></div>
        <div class="servicos" id="maqServ"></div>
        <p class="nota" id="maqServNota" hidden></p>
      </div>
    </div>
    <div class="maq-linha motor motor-texto" id="maqTextoLinha" hidden>
      <span class="motor-ic">${ic('texto')}</span>
      <div class="motor-txt"><b>IA de texto</b><small class="texto-status" id="textoStatus"></small></div>
      <span class="motor-acao texto-acoes" id="textoAcoes">
        <button type="button" class="chave" role="switch" aria-checked="false" id="btTextoLigar" hidden aria-label="Ligar a IA de texto"><span class="sr-only">Ligar agora</span></button>
        <button type="button" class="chave on" role="switch" aria-checked="true" id="btTextoDesligar" hidden aria-label="Desligar a IA de texto"><span class="sr-only">${esc(TX('Desligar'))}</span></button>
        <button type="button" class="bt-motor" id="btTextoInstalar" data-prep-ir="blocoPreparar" hidden><span>Instalar</span></button>
      </span>
      <p class="texto-extra nota" id="textoExtra" hidden></p>
      <details class="mini-ajuda" id="textoOpcoes"><summary>Opções</summary>
        <p class="nota" id="textoNotaRam">Fica na memória do computador, uns 8 GB, sem ocupar a placa de vídeo.</p>
        <label class="marcar" id="textoSempreRot" hidden><input type="checkbox" id="chkTextoSempre"><span>Deixar sempre ligada ao abrir o estúdio</span></label>
        <details class="maq-detalhes" id="textoDetalhes"><summary>Detalhes</summary><div class="maq-det-corpo" id="textoDet"></div></details>
      </details>
    </div>
    <div id="maqFila"></div>
    <div class="liberar motor">
      <span class="motor-ic">${ic('raio')}</span>
      <div class="motor-txt"><b title="Memória da placa de vídeo e da RAM">Memória</b><small id="maqAuto"></small></div>
      <span class="motor-acao"><button type="button" class="bt-motor" id="btLiberar">Liberar</button></span>
      <details class="mini-ajuda"><summary>O que isso faz</summary>
        <p class="nota">Tira os modelos da placa de vídeo e da RAM. Use antes de gerar música, quando o PC estiver lento ou ao terminar uma série. Só funciona com nada gerando; a próxima geração carrega o modelo de novo (demora mais).<span id="liberarTextoNota"> A IA de texto “Pronta” continua ligada (para tirar, use a chave dela).</span></p>
        <p class="nota" id="maqParcial" hidden>Algumas informações (RAM, discos, serviços da música) aparecem quando o servidor do estúdio for atualizado.</p>
      </details>
    </div>`;
  // 02/11/2026: os botões de ligar/desligar as IAs sobem para o alto da página (os "fornos").
  // A linha inteira é MOVIDA, não copiada: mesmos ids, mesmos botões, mesmo código. O clique
  // continua funcionando porque quem escuta é o #vInicio, e o herói também vive dentro dele.
  const fornos = $('#forjaFornos'), linhaServ = $('#maqServLinha');
  if (fornos && linhaServ) fornos.appendChild(linhaServ);
  // 14/11/2026 (inicio v3): IA de texto, fila e memoria descem para a mesma bancada. Movidas,
  // nao copiadas - os ids continuam os mesmos e todo o resto do codigo nem percebe.
  const bancada = $('#bancada');
  // v3.2: IA de texto e memória viram cartões da grade de motores; a fila vai para a faixa dela
  const motores = $('#motores') || bancada, faixa = $('#filaFaixa') || bancada;
  if (motores) ['#maqTextoLinha', '#maqCorpo .liberar'].forEach((s) => { const no = $(s); if (no) motores.appendChild(no); });
  if (faixa) { const no = $('#maqFila'); if (no) faixa.appendChild(no); }
  $('#btLiberar').onclick = liberarMemoria;
  $('#btTextoLigar').onclick = () => textoAcao('ligar');
  $('#btTextoDesligar').onclick = () => textoAcao('desligar');
  $('#chkTextoSempre').addEventListener('change', mudarSempreLigada);
}
async function liberarMemoria() {
  const bt = $('#btLiberar');
  if (bt.getAttribute('aria-disabled') === 'true') { aviso('Tem geração rodando ou na fila: espere terminar para liberar a memória.', 'aviso'); return; }
  bt.disabled = true;
  try {
    const r = await api('/api/liberar-memoria', { method: 'POST', timeout: 30000 });
    aviso(r.motivo || (r.ok ? 'Memória liberada: os modelos foram descarregados.' : 'Não deu para liberar agora.'), r.ok ? 'ok' : 'aviso');
  } catch (e) {
    aviso(e.status === 404 ? 'Esta versão do servidor do estúdio ainda não tem o botão de liberar memória.' : 'Não consegui liberar: ' + e.message, 'erro');
  }
  bt.disabled = false;
  pulso();
}
async function ligarMusica(bt) {
  const txt = bt.innerHTML;
  bt.disabled = true;
  bt.innerHTML = `${ic('relogio')}Ligando… (até 40 s)`;
  const st = $('#ligarMusicaStatus');
  if (st) st.textContent = 'Ligando o painel de música…';
  try {
    const r = await api('/api/musica/ligar', { method: 'POST', timeout: 70000 });
    if (r.estado && G.sistema) G.sistema.musica_estado = r.estado;
    if (!r.musica) aviso(r.erro || 'O painel de música não respondeu a tempo. Tente de novo em instantes.', 'aviso', 9000);
    else if (r.erro_comfy) aviso('Painel de música ligado, mas a ComfyUI não ligou: ' + r.erro_comfy, 'aviso', 10000);
    else if (r.comfy === 'ligando') aviso('Painel de música ligado. A ComfyUI está ligando (1 a 2 min); a primeira música espera na fila.', 'ok', 7000);
    else aviso('Painel de música ligado.', 'ok');
    if (st) st.textContent = '';
  } catch (e) {
    aviso('Não consegui ligar a música: ' + e.message, 'erro');
    if (st) st.textContent = '';
  }
  bt.disabled = false;
  bt.innerHTML = txt;
  pulso();
  if (G.rota === 'musica') atualizarMusica(true);
}

function proximaDica() {
  const todas = Object.values(G.fichas).filter((f) => f.dica_prompt);
  if (!todas.length) { $('#dicaFaixa').hidden = true; return; }
  $('#dicaFaixa').hidden = false;
  G.dicaIdx = G.dicaIdx == null ? Math.floor(Math.random() * todas.length) : (G.dicaIdx + 1) % todas.length;
  const f = todas[G.dicaIdx], t = $('#dicaTxt');
  t.classList.add('trocando');
  setTimeout(() => {
    $('#dicaRot').textContent = `Dica · ${nomeCurto(f.nome)}`;
    t.textContent = f.dica_prompt;
    t.classList.remove('trocando');
  }, 220);
}

function renderCatalogo() {
  const cols = [
    { titulo: 'Imagem', tipo: 't-imagem', icone: 'imagem', lista: presetsDa('imagem').map(fichaOuPreset) },
    { titulo: 'Vídeo', tipo: 't-video', icone: 'video', lista: presetsDa('video').map(fichaOuPreset) },
    { titulo: 'Pessoa falando', tipo: 't-voz', icone: 'apresentador', lista: presetsDa('apresentador').map(fichaOuPreset) },
    { titulo: 'Música', tipo: 't-musica', icone: 'musica', lista: G.fichasMusica, musica: true },
  ];
  // 14/11/2026: a lista nao dizia quais IAs ja estavam no disco. Agora a instalada fica
  // verde e sobe para o alto da coluna; a que falta diz quanto falta baixar.
  const ias = G.ias || {}, pg = G.iasProgresso || {};
  $('#catalogo').innerHTML = cols.map((c) => {
    const sei = c.lista.filter((f) => ias[f.id]);
    const prontas = sei.filter((f) => ias[f.id].instalada).length;
    const ordem = [...c.lista].sort((a, b) => (ias[b.id] && ias[b.id].instalada ? 1 : 0) - (ias[a.id] && ias[a.id].instalada ? 1 : 0));
    const conta = sei.length ? `${prontas} de ${sei.length} instaladas` : '';
    const item = (f) => {
      const e = ias[f.id];
      let cls = '', est = '';
      if (e && e.instalada) { cls = ' instalada'; est = `<span class="cat-estado">${ic('ok')}instalada</span>`; }
      else if (e && pg.baixando && pg.baixando.ia === e.nome) { cls = ' baixando'; est = `<span class="cat-estado">${andamentoDaIA(pg.baixando).pc}%</span>`; }
      else if (e && (pg.fila || []).includes(e.nome)) { cls = ' baixando'; est = '<span class="cat-estado">na fila</span>'; }
      else if (e) { cls = ' falta'; est = e.gb_falta ? `<span class="cat-estado">falta ${num(e.gb_falta, 1)} GB</span>` : '<span class="cat-estado">não instalada</span>'; }
      return `<li><button type="button" class="cat-item${cls}" data-ficha="${esc(f.id)}">
        <span class="cat-nome"><b>${esc(nomeCurto(f.nome))}</b>${est}</span>${f.resumo_curto ? `<small>${esc(f.resumo_curto)}</small>` : ''}</button></li>`;
    };
    return `<div class="cat-col ${c.tipo}">
    <h3>${ic(c.icone)}<span>${esc(c.titulo)}</span>${conta ? `<small>${esc(conta)}</small>` : ''}</h3>
    ${c.lista.length ? `<ul>${ordem.map(item).join('')}</ul>`
      : `<p class="nota">${!G.presets ? 'Carregando as IAs do estúdio…' : c.tipo === 't-musica' ? 'As fichas dos motores de música aparecem quando o servidor do estúdio for atualizado. Abra a Música para ver os motores.' : 'Nenhuma IA nesta seção.'}</p>`}
  </div>`;
  }).join('');
}

// ================================================================ GERADOR: estado por seção
const ESTADOS = {};
let E = null;
function estadoNovo(rota) {
  return { rota, sel: null, modo: null, estilo: null, formato: null, duracao: null, resolucao: null, qualidade: null,
    up: { imagem: null, video: null, voz: null, audio: null }, refs: [], enquadrar: true, enq: { chave: null, res: null },
    idioma: null, motor: null, vozId: null, prompt: '', seed: '', forca: 0.6, trocando: null,
    texto: { caixa: null, status: '', ocupado: false } };  // IA de texto: caixa de antes/depois desta seção
}
function salvarCampos(est) {
  est.prompt = $('#prompt').value;
  est.seed = $('#seed').value;
  est.forca = +$('#forca').value;
}
function restaurarCampos() {
  $('#prompt').value = E.prompt || '';
  $('#seed').value = E.seed || '';
  $('#forca').value = E.forca || 0.6;
  $('#forcaVal').textContent = num(+$('#forca').value, 2);
  $('#nomeVoz').value = '';
  $('#buscaIA').value = '';
  esconderErro();
  renderUploads();
  renderTexto();
}
function presetAtual() {
  const lista = presetsDa(G.rota);
  return lista.find((p) => p.id === E.sel) || lista[0] || null;
}

function abrirGerador(rota) {
  const R = ROTAS[rota], lista = presetsDa(rota);
  if (!ESTADOS[rota]) ESTADOS[rota] = estadoNovo(rota);
  E = ESTADOS[rota];
  if (!E.sel || !lista.some((p) => p.id === E.sel)) {
    // padrão: a última IA usada (se for desta seção, o modelo já está carregado), senão a recomendada
    const ult = G.sistema && G.sistema.ultimo_preset;
    E.sel = (lista.find((p) => p.id === ult) || lista.find((p) => p.id === RECOMENDADA[rota]) || lista[0] || {}).id || null;
  }
  // começa recolhido: mostra a IA escolhida (a recomendada na 1ª visita) e o botão "Trocar IA"; a caixa de texto fica à vista
  if (E.trocando === null) E.trocando = false;
  $('#vGerador').className = 'vista gerador ' + R.tipo;
  $('#rotaIc').innerHTML = ic(R.icone);
  $('#rotaTitulo').textContent = TX(R.titulo);
  $('#rotaSobre').textContent = TX(R.sobre);
  $('#tituloCriacoes').textContent = TX(R.criacoes);
  restaurarCampos();
  if (!lista.length) {
    $('#iaAtual').innerHTML = '<p class="nota">Nenhuma IA disponível nesta seção.</p>';
    $('#gerar').disabled = true;
  } else {
    $('#gerar').disabled = false;
    aplicarPreset();
  }
  renderBotaoGerar();
  const F = G.gal[rota];
  $('#buscaCri').value = F.busca;
  $('#grade').innerHTML = '';
  G.cards.clear();
  $('#filtroEstado')._sig = $('#filtroIA')._sig = null;
  G.jobs[rota] = G.jobs[rota] || [];
  renderGaleria();
  atualizar();
}
function renderBotaoGerar() {
  // o botão diz COM QUAL IA vai gerar (no Apresentador só existe uma)
  const p = ehGerador(G.rota) && E ? presetAtual() : null;
  const nome = p && G.rota !== 'apresentador' ? nomeCurto((fichaOuPreset(p) || {}).nome || p.nome) : '';
  $('#gerarTxt').innerHTML = esc((ROTAS[G.rota] || {}).gerar || 'Gerar') + (nome ? ` <span class="gerar-com">com ${esc(nome)}</span>` : '');
}

function chips(el, valores, atual, aoEscolher, rotulo = rot) {
  const foco = el.contains(document.activeElement) ? document.activeElement.dataset.v : null;
  el.innerHTML = '';
  valores.forEach((v) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.v = v;
    b.textContent = TX(rotulo(v));   // um funil so: todo botaozinho de ajuste passa aqui
    b.setAttribute('aria-pressed', String(v === atual));
    b.onclick = () => aoEscolher(v);
    el.appendChild(b);
  });
  if (foco != null) { const b = [...el.children].find((x) => x.dataset.v === foco); if (b) b.focus(); }
}

// -------------------------------------------------- IA instalada ou "falta instalar"
// 06/11/2026. A plataforma passou a instalar sozinha (~5,6 GB) e as IAs vem DEPOIS, uma
// por uma. Entao cada cartao de IA precisa dizer se ela esta no disco - e, se nao estiver,
// quanto pesa e um botao para baixar. Sem isso a pessoa escolhe uma IA que nao existe na
// maquina dela e leva um erro no meio do trabalho, sem entender por que.
function faixaInstalar(id) {
  const e = (G.ias || {})[id];
  if (!e || !e.conhecida || e.instalada) return '';
  // 11/11/2026: ate hoje o erro do download era GUARDADO e nunca mostrado. O LTX 2.5
  // parava com 401 (o repositorio da Lightricks pede conta) e o cartao so voltava a
  // dizer "Falta instalar", sem uma palavra. Falha calada e pior que erro na cara.
  const pg = G.iasProgresso || {};
  // 14/11/2026: o erro vem com o NOME da IA e aqui era comparado com o ID - nunca batia, e
  // o motivo nunca aparecia. Agora cada IA tem o seu erro (pg.erros), mesmo com a fila andando.
  const meuErro = erroDaIA(pg, e.nome);
  if (meuErro && !(pg.baixando && pg.baixando.ia === e.nome)) {
    return `<p class="ia-falta sem-link" role="alert">${ic('alerta')}<span>${esc(meuErro)}</span></p>`;
  }
  const pr = pg.baixando;
  if (pr && pr.ia === e.nome) {
    const a = andamentoDaIA(pr);
    return `<div class="ia-baixando"><div class="ia-barra"><i style="width:${a.pc}%"></i></div>
      <span>${esc(T('ia.baixando', 'Baixando… {pc}%', { pc: a.pc }))} <b>${esc(gbCurto(a.feito))}</b> ${esc(T('ia.de', 'de'))} ${esc(gbCurto(a.total))}${a.qual}</span></div>`;
  }
  if (!e.da_para_baixar) {
    return `<span class="ia-falta sem-link" title="${esc(T('ia.semLinkDica', 'Faltam {n} arquivo(s) sem endereço de download conhecido. Veja IAS-INSTALADAS.md.', { n: e.sem_link.length }))}">
      ${ic('alerta')}<span>${esc(T('ia.faltaMao', 'Falta instalar — {gb} GB, baixar à mão', { gb: e.gb_falta }))}</span></span>`;
  }
  return `<button type="button" class="ia-falta" data-instalar="${esc(id)}"
    aria-label="${esc(T('ia.faltaDica', '{q} ainda não está instalada. {gb} GB. Clique para baixar.', { q: e.nome, gb: e.gb_falta }))}">
    ${ic('baixar')}<span>${esc(T('ia.faltaAntes', 'Falta instalar —'))} <b>${e.gb_falta} GB</b></span></button>`;
}
function botaoRemoverIA(id) {
  const e = (G.ias || {})[id];
  if (!e || !e.conhecida || !e.instalada) return '';
  const rotulo = T('ia.remover', 'Remover {q} do computador', { q: e.nome });
  return `<button type="button" class="ia-lixo" data-remover="${esc(id)}" title="${esc(rotulo)}" aria-label="${esc(rotulo)}">${ic('lixo')}</button>`;
}
async function removerIA(id) {
  const e = (G.ias || {})[id];
  const nome = e ? e.nome : id;
  let junto = false;
  const chamar = async (confirmar) => {
    const r = await fetch('/api/ias/remover', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, confirmar, junto }) });
    const d = await r.json().catch(() => ({}));
    return { ok: r.ok, d };
  };
  let plano;
  try { plano = await chamar(false); } catch (err) { aviso(T('ia.semEstudio', 'Não consegui falar com o estúdio.'), 'erro'); return false; }
  if (!plano.ok) { aviso(plano.d.erro || plano.d.mensagem || T('ia.naoRemoveu', 'Não deu para remover.'), 'erro'); return false; }
  let p = plano.d;
  if (!p.apagar.length && p.manter.length) {
    const donos = [...new Set(p.manter.flatMap((x) => x.usado_por))];
    const ok = await confirmar({
      titulo: T('ia.juntoTitulo', 'Remover também {d}?', { d: donos.join(', ') }),
      texto: T('ia.juntoTexto', 'Todos os arquivos de "{q}" são compartilhados com {d}. Para liberar espaço, as duas precisam sair: {d} deixará de estar instalada.', { q: nome, d: donos.join(', ') }),
      sim: T('ia.juntoSim', 'Ver o que será apagado'), nao: T('ia.voltar', 'Voltar'), icone: 'alerta' });
    if (!ok) return false;
    junto = true;
    plano = await chamar(false);
    if (!plano.ok) { aviso(plano.d.erro || T('ia.naoRemoveu', 'Não deu para remover.'), 'erro'); return false; }
    p = plano.d;
  }
  if (!p.apagar.length) {
    aviso(T('ia.nadaApagar', 'Nada a apagar: os arquivos desta IA não estão no disco.'), 'aviso');
    return false;
  }
  const lista = [
    ...p.apagar.map((x) => ({ txt: `${T('ia.vaiApagar', 'Apaga')}: ${x.arquivo} (${x.gb.toLocaleString('pt-BR')} GB)`, cls: 'alerta' })),
    ...p.manter.map((x) => ({ txt: `${T('ia.fica', 'Fica')}: ${x.arquivo} — ${T('ia.usadoPor', 'usado por')} ${x.usado_por.join(', ')}`, cls: 'fica' })),
  ];
  const sim = await confirmar({
    titulo: T('ia.removerTitulo', 'Remover "{q}" do computador?', { q: nome }),
    texto: T('ia.removerTexto', 'Isso apaga {gb} GB do disco. Para usar esta IA de novo, será preciso baixar tudo outra vez.', { gb: p.gb.toLocaleString('pt-BR') }),
    lista, sim: T('ia.removerSim', 'Remover do computador'), icone: 'lixo',
  });
  if (!sim) return false;
  try {
    const r = await chamar(true);
    aviso(r.ok ? T('ia.removida', '{q} removida: {gb} GB liberados.', { q: nome, gb: (r.d.liberou_gb || 0).toLocaleString('pt-BR') })
               : (r.d.mensagem || T('ia.naoRemoveu', 'Não deu para remover.')), r.ok ? 'ok' : 'erro');
    await lerIAs();
    return r.ok;
  } catch (err) {
    aviso(T('ia.semEstudio', 'Não consegui falar com o estúdio.'), 'erro');
    return false;
  }
}
window.removerIA = removerIA;
function gbCurto(b) {
  if (!b) return '0';
  const gb = b / 1024 / 1024 / 1024;
  return gb >= 1 ? gb.toFixed(1) + ' GB' : Math.round(b / 1024 / 1024) + ' MB';
}
async function instalarIA(id) {
  const e = (G.ias || {})[id];
  if (!e) return;
  // Confirmar porque e um download de dezenas de GB: clicar sem querer nao pode custar
  // 40 GB de internet de alguem.
  if (!confirm(T('ia.confirmaBaixar',
      'Baixar "{q}"?\n\nSão {gb} GB. Dá para usar o estúdio enquanto baixa, e se parar no '
      + 'meio continua de onde parou.', { q: e.nome, gb: e.gb_falta }))) return;
  try {
    const r = await fetch('/api/ias/instalar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    const d = await r.json().catch(() => ({}));
    // d.mensagem vem do servidor: continua em portugues ate o server.py ser traduzido.
    aviso(d.mensagem || (r.ok ? T('ia.comecando', 'Começando a baixar.')
                              : T('ia.naoComecou', 'Não deu para começar.')), r.ok ? 'ok' : 'erro');
    lerIAs();
  } catch (err) {
    aviso(T('ia.semEstudio', 'Não consegui falar com o estúdio.'), 'erro');
  }
}

async function lerIAs() {
  try {
    const r = await fetch('/api/ias');
    if (!r.ok) return;
    const d = await r.json();
    G.ias = d.ias || {};
    G.aprovadasIds = d.aprovadas || [];
    G.iasProgresso = d.progresso || {};
    if (G.iasProgresso.baixando) {
      clearTimeout(G.iasTimer);
      G.iasTimer = setTimeout(lerIAs, 1500);   // só fica perguntando enquanto baixa
    }
    // O bloco das aprovadas PRIMEIRO, e protegido: o renderIAs() desenha os cartoes das
    // abas e estoura quando a pessoa esta na tela inicial (nao ha aba aberta). Com ele na
    // frente, o bloco nunca se redesenhava depois de trocar o disco nem durante o download.
    try { renderAprovadas(); } catch (e) { /* bloco ausente nesta tela */ }
    if (!G.iasProgresso.baixando && G.estavaBaixando) lerRequisitos();   // terminou: a lista muda
    G.estavaBaixando = !!G.iasProgresso.baixando;
    renderIAs();
  } catch (e) { /* sem rota: servidor antigo. A tela funciona, só sem o aviso. */ }
}

// ================================================= IAs aprovadas + onde instalar (13/11/2026)
// Tres passos na mesma caixa, na ordem em que a pessoa pensa: EM QUE DISCO, QUAIS, INSTALAR.
// O que ela marca fica em G.aprovSel: a tela se redesenha a cada 1,5 s enquanto baixa, e
// sem guardar a marcacao as caixinhas desmarcariam sozinhas no meio da escolha.
async function lerDestino() {
  try {
    const r = await fetch('/api/ias/destino');
    if (!r.ok) return;
    G.destino = await r.json();
    renderAprovadas();
    // enquanto o motor instala, perguntar de novo: a barra anda e o aviso some no fim
    const fase = (G.destino.motor || {}).fase;
    clearTimeout(G.motorTimer);
    if (fase && fase !== 'pronto') G.motorTimer = setTimeout(lerDestino, 1500);
  } catch (e) { /* servidor antigo, sem esta rota: o bloco simplesmente nao aparece */ }
}
// O erro de UMA ia. Servidor antigo so manda o ultimo (erro + erro_ia, com o nome).
function erroDaIA(pg, nome) {
  if (pg.erros && pg.erros[nome]) return pg.erros[nome];
  return pg.erro && pg.erro_ia === nome ? pg.erro : '';
}

// A porcentagem e da IA INTEIRA (todos os arquivos dela), nao do arquivo da vez: por arquivo
// ela chegava a 100 e voltava a 0, e parecia que o download tinha recomecado (14/11/2026).
// Servidor antigo nao manda ia_total: ai vale a conta por arquivo, como era.
function andamentoDaIA(pr) {
  const total = pr.ia_total || pr.total || 0;
  const feito = pr.ia_total ? (pr.ia_antes || 0) + (pr.baixados || 0) : (pr.baixados || 0);
  const pc = total ? Math.min(100, Math.floor((feito / total) * 100)) : 0;
  const qual = pr.de > 1 ? ' · ' + esc(T('ia.arquivo', 'arquivo {n} de {de}', { n: pr.numero, de: pr.de })) : '';
  return { pc, feito, total, qual };
}

// ============================================ Preparar esta maquina (14/11/2026)
// Cada pre-requisito numa linha: o estado, o que falta e, quando falta, o passo a passo e o
// botao. Regra do dono: nada que a pessoa precise baixar ou cadastrar pode morar so num manual.
async function lerRequisitos() {
  try {
    const r = await fetch('/api/requisitos');
    if (!r.ok) return;
    G.requisitos = await r.json();
    renderPreparar();
    try { renderAprovadas(); } catch (e) { /* a lista ainda nao esta na tela */ }
    clearTimeout(G.reqTimer);
    const andando = (G.requisitos.andamento || {}).id;
    // a fila dos extras (voz, texto): o servidor baixa um por vez; quando ele fica livre, vai o proximo
    if (!andando && G.extraFila && G.extraFila.length) { proximoExtra(); return; }
    if (andando) G.reqTimer = setTimeout(lerRequisitos, 1500);
  } catch (e) { /* servidor antigo: o bloco nao aparece */ }
}
async function proximoExtra() {
  const qual = (G.extraFila || []).shift();
  if (!qual) return;
  try {
    const r = await fetch('/api/requisitos/instalar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ qual }) });
    if (!r.ok) { const d = await r.json().catch(() => ({})); aviso(d.mensagem || 'Não deu para começar.', 'erro', 8000); }
  } catch (e) { aviso('Não consegui falar com o estúdio.', 'erro'); }
  lerRequisitos();
}
function renderPreparar() {
  const onde = $('#preparar'), bloco = $('#blocoPreparar'), d = G.requisitos;
  if (!onde || !bloco) return;
  bloco.hidden = !d || !(d.itens || []).length;
  if (bloco.hidden) return;
  // 14/11/2026 (inicio v3): enquanto FALTA algo, o bloco fica logo abaixo dos cartoes - e a
  // primeira coisa a fazer. Com tudo pronto, desce para depois do catalogo e sai da frente.
  const falta = (d.falta || []).length > 0;
  bloco.classList.toggle('tem-falta', falta);
  const antes = falta ? document.querySelector('#vInicio .inicio-duo') : $('#blocoChaves');
  if (antes && bloco.nextElementSibling !== antes) antes.parentNode.insertBefore(bloco, antes);
  const abertos = new Set([...onde.querySelectorAll('details[open][data-prep-como]')].map((x) => x.dataset.prepComo));
  const and = d.andamento || {};
  const ROTULO = { ok: 'pronto', falta: 'falta', aviso: 'atenção', opcional: 'opcional' };
  const FASE = { baixando: 'Baixando…', conferindo: 'Conferindo a assinatura do arquivo…',
    descompactando: 'Descompactando…', abrindo: 'Abrindo o instalador…', configurando: 'Configurando…' };
  const nFalta = (d.falta || []).length;
  $('#prepSub').textContent = nFalta
    ? T('prep.falta', 'Falta {n} passo(s) para o estúdio funcionar inteiro.', { n: nFalta })
    : TX('O essencial está pronto. O que aparece como opcional você instala se quiser.');
  onde.innerHTML = d.itens.map((it, i) => {
    const meu = and.id && (and.id === it.id || (and.id === 'voz' && it.id === 'voz'));
    let acao = '';
    if (meu) {
      const pc = and.fase === 'baixando' && and.total ? Math.floor((and.baixados / and.total) * 100) : null;
      const gb = (n) => (n / 1073741824).toFixed(1).replace('.', ',');
      const quanto = pc != null && and.total > 1073741824 ? ` · ${gb(and.baixados)} / ${gb(and.total)} GB` : '';
      acao = `<div class="prep-andando"><span>${esc(TX(FASE[and.fase] || 'Trabalhando…'))}${pc != null ? ` <b>${pc}%</b>` : ''}${quanto}</span>
        ${and.arquivo ? `<small class="prep-arq">${esc(and.arquivo)}</small>` : ''}
        <div class="ia-barra"><i style="width:${pc != null ? pc : 100}%"></i></div>
        <button type="button" class="bt-sec" data-prep-parar>${esc(TX('Parar'))}</button></div>`;
    } else if (it.botao) {
      const b = it.botao;
      const attr = b.acao === 'instalar' ? `data-prep-instalar="${esc(b.qual)}"`
        : b.acao === 'ir' ? `data-prep-ir="${esc(b.para)}"` : `data-prep-link="${esc(b.url)}"`;
      acao = `<button type="button" class="bt-sec prep-bt" ${attr} ${and.id ? 'disabled' : ''}>${ic(b.acao === 'instalar' ? 'baixar' : b.acao === 'link' ? 'externo' : 'baixo')}${esc(TX(b.rotulo))}</button>`;
    }
    const erro = and.erro && and.erro_de === it.id ? `<p class="aprov-erro" role="alert" style="text-align:left">${esc(and.erro)}</p>` : '';
    const pronto = and.pronto && and.pronto.id === it.id ? `<p class="prep-feito">${esc(and.pronto.recado)}</p>` : '';
    const lis = (it.passos || []).map((p) => `<li>${esc(TX(p))}</li>`).join('');
    // o que FALTA mostra os passos; o que e opcional ou ja funciona guarda os passos num "como fazer"
    const passos = !lis ? '' : it.estado === 'falta' ? `<ol class="prep-passos">${lis}</ol>`
      : `<details class="prep-como" data-prep-como="${esc(it.id)}"${abertos.has(it.id) ? ' open' : ''}><summary>Como fazer</summary><ol class="prep-passos">${lis}</ol></details>`;
    const link = it.link ? `<a class="prep-link" href="${esc(it.link.url)}" target="_blank" rel="noopener">${esc(TX(it.link.rotulo))}</a>` : '';
    return `<div class="prep-item prep-${esc(it.estado)}">
      <span class="prep-num">${i + 1}</span>
      <div class="prep-corpo">
        <div class="prep-topo"><b>${esc(TX(it.nome))}</b><span class="prep-selo">${esc(TX(ROTULO[it.estado] || it.estado))}</span></div>
        <p class="prep-resumo">${esc(TX(it.resumo))}</p>${passos}${erro}${pronto}${link}
      </div>
      <div class="prep-acao">${acao}</div></div>`;
  }).join('');
  pintarIcones(onde);
}
document.addEventListener('click', (ev) => {
  const alvo = ev.target.closest ? ev.target : null;
  if (!alvo) return;
  const inst = alvo.closest('[data-prep-instalar]');
  if (inst && !inst.disabled) {
    fetch('/api/requisitos/instalar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ qual: inst.dataset.prepInstalar }) })
      .then((r) => r.json().then((d) => { if (!r.ok) aviso(d.mensagem || 'Não deu para começar.', 'erro', 8000); }))
      .catch(() => aviso('Não consegui falar com o estúdio.', 'erro'))
      .then(lerRequisitos);
    return;
  }
  const ir = alvo.closest('[data-prep-ir]');
  if (ir) { const el = document.getElementById(ir.dataset.prepIr); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
  const lk = alvo.closest('[data-prep-link]');
  if (lk) { window.open(lk.dataset.prepLink, '_blank', 'noopener'); return; }
  if (alvo.closest('[data-prep-parar]')) fetch('/api/requisitos/parar', { method: 'POST' }).then(() => setTimeout(lerRequisitos, 800));
});

// O motor (a ComfyUI) ainda nao esta no disco: em vez de mandar ler um manual, um botao.
function htmlMotor(d) {
  if (d.motor_instalado) return '';
  const m = d.motor || {};
  const FASES = { baixando: 'Baixando o motor…', conferindo: 'Conferindo a assinatura do arquivo…',
    descompactando: 'Descompactando (leva alguns minutos)…', complementos: 'Instalando os complementos…' };
  if (m.fase && m.fase !== 'pronto') {
    const pc = m.fase === 'baixando' && m.total ? Math.floor((m.baixados / m.total) * 100) : null;
    return `<div class="aprov-aviso motor-andando" role="status">${ic('baixar')}<div style="flex:1">
      <span>${esc(TX(FASES[m.fase] || 'Instalando o motor…'))}${pc != null ? ` <b>${pc}%</b>` : ''}</span>
      <div class="ia-barra"><i style="width:${pc != null ? pc : 100}%"></i></div></div>
      <button type="button" class="bt-sec" data-motor-parar>${esc(TX('Parar'))}</button></div>`;
  }
  const semBotao = d.por_ambiente;
  return `<div class="aprov-aviso" role="status">${ic('alerta')}<div style="flex:1">
    <span>${esc(TX('O motor (a ComfyUI) ainda não está neste disco. Sem ele os modelos baixam, mas nada gera.'))}</span>
    ${m.erro ? `<p class="aprov-erro" role="alert" style="text-align:left;margin:6px 0 0">${esc(m.erro)}</p>` : ''}</div>
    ${semBotao ? '' : `<button type="button" class="bt-sec" data-motor-instalar>${ic('baixar')}${esc(T('aprov.motorBotao', 'Instalar o motor — {gb} GB', { gb: num(m.gb || 1.8, 1) }))}</button>`}</div>`;
}
async function instalarMotor() {
  const d = G.destino || {}, m = d.motor || {};
  if (!confirm(T('aprov.motorConfirma', 'Instalar o motor (ComfyUI {v}) no disco {u}:?\n\nBaixa {gb} GB e ocupa cerca de {p} GB depois de descompactado. Leva de 10 a 30 minutos, conforme a internet.',
      { v: m.versao || '', u: d.unidade || '', gb: num(m.gb || 1.8, 1), p: m.precisa_gb || 12 }))) return;
  try {
    const r = await fetch('/api/motor/instalar', { method: 'POST' });
    const resp = await r.json().catch(() => ({}));
    aviso(resp.mensagem || (r.ok ? 'Começando a instalar o motor.' : 'Não deu para começar.'), r.ok ? 'ok' : 'erro', 8000);
  } catch (e) { aviso('Não consegui falar com o estúdio.', 'erro'); }
  lerDestino();
}
function renderAprovadas() {
  const onde = $('#aprovadas'), bloco = $('#blocoAprovadas');
  if (!onde || !bloco) return;
  const d = G.destino, ias = G.ias || {}, ids = (G.aprovadasIds || []).filter((i) => ias[i]);
  bloco.hidden = !d || !ids.length;
  if (bloco.hidden) return;
  if (!G.aprovSel) G.aprovSel = new Set();
  const pg = G.iasProgresso || {}, ocupado = !!(pg.baixando || (pg.fila || []).length);
  const noPainel = (d.pasta_do_painel || '').slice(0, 1).toUpperCase();
  const motorAndando = !!((d.motor || {}).fase && d.motor.fase !== 'pronto');

  const discos = (d.discos || []).map((k) => {
    const sel = k.unidade === d.unidade;
    return `<button type="button" class="disco${sel ? ' sel' : ''}" data-disco="${esc(k.unidade)}" aria-pressed="${sel}"
      ${d.por_ambiente || ocupado || motorAndando ? 'disabled' : ''}>
      <b>${esc(k.unidade)}:</b><span>${esc(T('aprov.livres', '{gb} GB livres', { gb: num(k.livre_gb, 0) }))}</span>
      <small>${esc(T('aprov.deTotal', 'de {gb} GB', { gb: num(k.total_gb, 0) }))}${k.unidade === noPainel ? ' · ' + esc(TX('onde o painel está')) : ''}</small></button>`;
  }).join('');

  const comToken = [], comErro = [], comErroX = [];
  // 14/11/2026, pedido do dono: toda IA que tem preset no painel tem de poder ser baixada
  // por aqui. As aprovadas em cima; as que o projeto ainda nao testou a fundo, embaixo.
  const outras = Object.keys(ias).filter((i) => !ids.includes(i) && ias[i].conhecida !== false)
    .sort((a, b) => (ias[b].da_para_baixar ? 1 : 0) - (ias[a].da_para_baixar ? 1 : 0));
  const linha = (id) => {
    const e = ias[id], pr = pg.baixando;
    let estado, marcavel = false;
    if (e.instalada) estado = `<span class="aprov-ok">${ic('ok')}${esc(TX('instalada'))}</span>`;
    else if (pr && pr.ia === e.nome) {
      const a = andamentoDaIA(pr);
      estado = `<span class="aprov-baixando">${esc(T('ia.baixando', 'Baixando… {pc}%', { pc: a.pc }))}${a.qual}</span>`;
    } else if ((pg.fila || []).includes(e.nome)) estado = `<span class="aprov-baixando">${esc(TX('na fila'))}</span>`;
    else if (erroDaIA(pg, e.nome)) {
      marcavel = true;      // da para marcar e tentar de novo depois de resolver
      // 14/11/2026: o recado inteiro saia espremido aqui, por cima do nome. Na linha vai so
      // a etiqueta; a explicacao fica embaixo da lista, na largura toda (ver "recados").
      const token = (pg.erros_tipo || {})[e.nome] === 'token';
      (token ? comToken : comErro).push(e);
      estado = token ? `<span class="aprov-token">${ic('alerta')}falta o token</span>`
        : `<span class="aprov-erro">${ic('alerta')}não baixou</span>`;
    }
    else if (!e.da_para_baixar) estado = `<span class="aprov-breve">${esc(num(e.gb_falta, 1))} GB · baixar à mão</span>`;
    else { estado = `<span class="aprov-falta">${esc(T('aprov.falta', 'falta baixar {gb} GB', { gb: e.gb_falta }))}</span>`; marcavel = true; }
    if (!marcavel) G.aprovSel.delete(id);
    return `<label class="aprov-linha${marcavel ? '' : ' travada'}">
      <input type="checkbox" data-aprov="${esc(id)}" ${G.aprovSel.has(id) ? 'checked' : ''} ${marcavel && !ocupado ? '' : 'disabled'}>
      <span class="aprov-nome">${esc(nomeCurto(e.nome))}</span>${estado}</label>`;
  };
  const linhas = ids.map(linha).join('');
  const linhasO = outras.map(linha).join('');
  const todos = ids.concat(outras);

  // os recados, uma vez so e na largura toda
  const recados = [];
  if (comToken.length) {
    const nomes = comToken.map((e) => nomeCurto(e.nome)).join(' e ');
    const gbT = Math.max(...comToken.map((e) => e.gb_falta || 0));
    recados.push(`<div class="aprov-recado token" role="status">${ic('alerta')}<div>
      <b>${comToken.length > 1 ? 'Faltam' : 'Falta'} só o token do Hugging Face para ${esc(nomes)}</b>
      <p>O resto já baixou. Falta um arquivo${gbT ? ` de ${num(gbT, 1)} GB` : ''} que só desce com a sua conta do Hugging Face, que é de graça. Cole o token em “Configurações de API”; depois marque ${comToken.length > 1 ? 'as duas' : 'a IA'} aqui e clique em “Instalar as marcadas”.</p></div>
      <button type="button" class="bt-sec" data-prep-ir="blocoChaves">${ic('baixo')}Colocar o token</button></div>`);
  }
  comErro.forEach((e) => recados.push(`<div class="aprov-recado erro" role="alert">${ic('alerta')}<div>
      <b>${esc(nomeCurto(e.nome))} não baixou</b><p>${esc(erroDaIA(pg, e.nome))}</p></div></div>`));

  // 14/11/2026: voz, IA de texto e musica na mesma lista de marcar. Vem de /api/requisitos.
  if (!G.extraSel) G.extraSel = new Set();
  const req = G.requisitos || {}, and = req.andamento || {}, filaX = G.extraFila || [];
  const extras = req.extras || [];
  const linhasX = extras.map((x) => {
    let estado, pode = false;
    if (x.instalada) estado = `<span class="aprov-ok">${ic('ok')}${esc(TX('instalada'))}</span>`;
    else if (and.id === x.id) {
      const pc = and.fase === 'baixando' && and.total ? Math.floor((and.baixados / and.total) * 100) : null;
      estado = `<span class="aprov-baixando">${pc != null ? esc(T('ia.baixando', 'Baixando… {pc}%', { pc })) : 'Instalando…'}</span>`;
    } else if (filaX.includes(x.id)) estado = `<span class="aprov-baixando">${esc(TX('na fila'))}</span>`;
    else if (and.erro && and.erro_de === x.id) { pode = true; estado = `<span class="aprov-erro">${ic('alerta')}não baixou</span>`; comErroX.push([x, and.erro]); }
    else if (!x.pode) estado = '<span class="aprov-breve">em breve</span>';
    else { pode = true; estado = `<span class="aprov-falta">${esc(T('aprov.falta', 'falta baixar {gb} GB', { gb: num(x.gb, x.gb < 1 ? 2 : 1) }))}</span>`; }
    if (!pode) G.extraSel.delete(x.id);
    return `<label class="aprov-linha${pode ? '' : ' travada'}" title="${esc(x.nota || '')}">
      <input type="checkbox" data-extra="${esc(x.id)}" ${G.extraSel.has(x.id) ? 'checked' : ''} ${pode ? '' : 'disabled'}>
      <span class="aprov-nome">${esc(x.nome)}</span>${estado}</label>`;
  }).join('');
  comErroX.forEach(([x, msg]) => recados.push(`<div class="aprov-recado erro" role="alert">${ic('alerta')}<div>
      <b>${esc(x.nome)} não baixou</b><p>${esc(msg)}</p></div></div>`));
  const marcadasX = extras.filter((x) => G.extraSel.has(x.id));

  const marcadas = todos.filter((i) => G.aprovSel.has(i));
  const soma = marcadas.reduce((s, i) => s + (ias[i].gb_falta || 0), 0) + marcadasX.reduce((s, x) => s + (x.gb || 0), 0);
  const nMarcadas = marcadas.length + marcadasX.length;
  const disco = (d.discos || []).find((k) => k.unidade === d.unidade);
  const livre = disco ? disco.livre_gb : null;
  const naoCabe = livre != null && soma + 2 > livre;
  const faltam = ids.filter((i) => !ias[i].instalada && ias[i].da_para_baixar).length;
  const faltamO = outras.filter((i) => !ias[i].instalada && ias[i].da_para_baixar).length;

  onde.innerHTML = `
    <div class="aprov-passo"><h3>${esc(TX('1. Em que disco ficam as IAs'))}</h3>
      <div class="discos">${discos}</div>
      <p class="fraco aprov-onde">${esc(TX('As IAs ficam em'))} <code>${esc(d.modelos)}</code></p>
      ${d.por_ambiente ? `<p class="fraco">${esc(TX('Esta pasta está definida no arquivo caminhos.bat. Para escolher por aqui, apague a linha ESTUDIO_COMFY_DIR de lá.'))}</p>` : ''}
      ${htmlMotor(d)}
    </div>
    <div class="aprov-passo"><h3>${esc(TX('2. Quais você quer'))}</h3>
      <div class="aprov-lista">${linhas}</div>
      ${linhasX ? `<h4 class="aprov-sub">Voz e texto</h4><div class="aprov-lista">${linhasX}</div>` : ''}
      ${linhasO ? `<h4 class="aprov-sub">Ainda não testadas a fundo pelo projeto</h4>
        <p class="nota aprov-sub-nota">Têm preset no painel e podem funcionar bem, mas foram pouco usadas: baixe sabendo disso. A que diz “baixar à mão” não tem endereço público conhecido.</p>
        <div class="aprov-lista">${linhasO}</div>` : ''}
      ${recados.join('')}
      ${faltam > 1 && !ocupado ? `<button type="button" class="aprov-todas" data-marcar-todas>${esc(marcadas.length === faltam ? TX('Desmarcar todas') : TX('Marcar todas'))}</button>` : ''}
    </div>
    <div class="aprov-passo aprov-fim">
      <p class="aprov-total${naoCabe ? ' nao-cabe' : ''}">${nMarcadas
        ? esc(T('aprov.total', '{n} marcada(s): {gb} GB para baixar', { n: nMarcadas, gb: num(soma, 1) }))
          + (livre != null ? ' · ' + esc(T('aprov.livreNo', '{gb} GB livres no {u}:', { gb: num(livre, 0), u: d.unidade })) : '')
          + (naoCabe ? ' — ' + esc(TX('não cabe neste disco')) : '')
        : esc(faltam || faltamO || extras.some((x) => x.pode && !x.instalada) ? TX('Marque o que você quer baixar.') : TX('Tudo que dá para instalar por aqui já está instalado.'))}</p>
      ${ocupado
        ? `<button type="button" class="bt-sec" data-parar-download>${esc(TX('Parar o download'))}</button>`
        : `<button type="button" class="gerar aprov-instalar" data-instalar-aprovadas ${nMarcadas && !naoCabe ? '' : 'disabled'}>${ic('baixar')}<span>${esc(TX('3. Instalar as marcadas'))}</span></button>`}
    </div>`;
  pintarIcones(onde);
}
async function trocarDisco(unidade) {
  const d = G.destino || {};
  if (unidade === d.unidade) return;
  const noPainel = (d.pasta_do_painel || '').slice(0, 1).toUpperCase();
  try {
    const r = await fetch('/api/ias/destino', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      // o disco onde o painel ja esta = o padrao: os modelos ficam dentro da pasta dele
      body: JSON.stringify(unidade === noPainel ? { padrao: true } : { unidade }),
    });
    const resp = await r.json().catch(() => ({}));
    if (!r.ok) { aviso(resp.erro || 'Não deu para trocar o disco.', 'erro', 9000); return; }
    G.destino = resp;
    renderAprovadas();
    aviso(resp.recado || T('aprov.trocou', 'Pronto: as IAs passam a ficar no disco {u}:', { u: resp.unidade }), resp.recado ? 'aviso' : 'ok', resp.recado ? 12000 : 5500);
    lerIAs();   // o que esta "instalado" depende do disco: perguntar de novo
  } catch (e) { aviso('Não consegui falar com o estúdio.', 'erro'); }
}
async function instalarAprovadas() {
  const ias = G.ias || {}, ids = Object.keys(ias).filter((i) => G.aprovSel && G.aprovSel.has(i));
  const extras = ((G.requisitos || {}).extras || []).filter((x) => G.extraSel && G.extraSel.has(x.id));
  if (!ids.length && !extras.length) return;
  const soma = ids.reduce((s, i) => s + (ias[i].gb_falta || 0), 0) + extras.reduce((s, x) => s + (x.gb || 0), 0);
  // confirmar: sao dezenas de GB de internet de alguem
  if (!confirm(T('aprov.confirma', 'Baixar {n} IA(s)?\n\nSão {gb} GB no disco {u}:. Dá para usar o estúdio enquanto baixa, e se parar no meio continua de onde parou.',
      { n: ids.length + extras.length, gb: num(soma, 1), u: (G.destino || {}).unidade || '' }))) return;
  if (extras.length) {      // um por vez no servidor: o resto espera na fila daqui
    G.extraFila = (G.extraFila || []).concat(extras.map((x) => x.id));
    G.extraSel.clear();
    if (!((G.requisitos || {}).andamento || {}).id) proximoExtra(); else lerRequisitos();
  }
  if (!ids.length) { aviso('Começando a baixar.'); return; }
  let entrou = 0, recusa = '';
  for (const id of ids) {
    try {
      const r = await fetch('/api/ias/instalar', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }),
      });
      const resp = await r.json().catch(() => ({}));
      if (r.ok) entrou += 1; else if (!recusa) recusa = resp.mensagem || '';
    } catch (e) { recusa = recusa || 'Não consegui falar com o estúdio.'; }
  }
  G.aprovSel.clear();
  if (recusa) aviso(recusa, 'erro', 12000);
  else aviso(T('aprov.comecou', '{n} IA(s) na fila. A primeira já começou a baixar.', { n: entrou }));
  lerIAs();
  lerDestino();
}
document.addEventListener('click', (ev) => {
  const alvo = ev.target.closest ? ev.target : null;
  if (!alvo) return;
  const disco = alvo.closest('[data-disco]');
  if (disco && !disco.disabled) { trocarDisco(disco.dataset.disco); return; }
  if (alvo.closest('[data-instalar-aprovadas]')) { instalarAprovadas(); return; }
  if (alvo.closest('[data-motor-instalar]')) { instalarMotor(); return; }
  if (alvo.closest('[data-motor-parar]')) {
    fetch('/api/motor/parar', { method: 'POST' }).then(() => setTimeout(lerDestino, 800));
    return;
  }
  if (alvo.closest('[data-marcar-todas]')) {
    const ias = G.ias || {}, podem = (G.aprovadasIds || []).filter((i) => ias[i] && !ias[i].instalada && ias[i].da_para_baixar);
    const todas = podem.every((i) => G.aprovSel.has(i));
    podem.forEach((i) => (todas ? G.aprovSel.delete(i) : G.aprovSel.add(i)));
    renderAprovadas();
    return;
  }
  if (alvo.closest('[data-parar-download]')) {
    fetch('/api/ias/parar', { method: 'POST' }).then(() => { aviso('Download parado. O que já baixou fica guardado.'); lerIAs(); });
  }
});
document.addEventListener('change', (ev) => {
  const x = ev.target && ev.target.dataset && ev.target.dataset.extra;
  if (x) {
    if (!G.extraSel) G.extraSel = new Set();
    if (ev.target.checked) G.extraSel.add(x); else G.extraSel.delete(x);
    renderAprovadas();
    return;
  }
  const c = ev.target && ev.target.dataset && ev.target.dataset.aprov;
  if (!c) return;
  if (!G.aprovSel) G.aprovSel = new Set();
  if (ev.target.checked) G.aprovSel.add(c); else G.aprovSel.delete(c);
  renderAprovadas();
});

// ---------------------------------------------------------------- seletor de IA em cards
function badgeCarregada(p) {
  return G.sistema && G.sistema.ultimo_preset === p.id
    ? `<span class="carregada" title="${esc(T('ia.carregadaDica', 'Foi a última IA usada: o modelo deve estar na memória, então a próxima sai mais rápido.'))}">${esc(T('ia.carregada', 'já carregada'))}</span>` : '';
}
function tagsDe(f, max = 4) { return (f.tags || []).slice(0, max).map((t) => `<span class="tag">${esc(rot(t))}</span>`).join(''); }
function htmlIAAtual(p) {
  const f = fichaOuPreset(p), tempo = tempoCurto(f), notas = htmlNotas(f);
  return `<div class="ia-card atual">
    <div class="ia-corpo">
      <span class="ia-cat">${esc(f.categoria || '')}</span>
      <span class="ia-topo"><span class="ia-nome">${esc(rot(f.nome || p.nome))}</span>${badgeCarregada(p)}</span>
      ${f.resumo_curto ? `<span class="ia-resumo">${esc(f.resumo_curto)}</span>` : ''}
      ${notas ? `<span class="ia-meta">${notas}</span>` : ''}
      ${tempo ? `<span class="ia-tempo">${ic('relogio')}<span>${esc(tempo)}</span></span>` : ''}
    </div>
    ${faixaInstalar(p.id)}
    <div class="ia-rodape"><span class="tags">${tagsDe(f)}</span>${botaoRemoverIA(p.id)}
      <button type="button" class="ia-saiba" data-saiba="${esc(p.id)}" aria-label="${esc(T('ia.saibaSobre', 'Saiba mais sobre {q}', { q: nomeCurto(f.nome || p.nome) }))}">${ic('info')}${esc(T('ia.saiba', 'Saiba mais'))}</button></div>
  </div>`;
}
function htmlCardIA(p, f) {
  const sel = p.id === E.sel, tempo = tempoCurto(f), notas = htmlNotas(f), nome = nomeCurto(f.nome || p.nome);
  return `<div class="ia-card${sel ? ' sel' : ''}">
    <button type="button" class="ia-escolher" data-escolher="${esc(p.id)}" aria-pressed="${sel}">
      <span class="ia-topo"><span class="ia-nome">${esc(nome)}</span>${badgeCarregada(p)}${sel ? `<span class="ia-check" title="${esc(T('ia.escolhida', 'Escolhida'))}">${ic('ok')}</span>` : ''}</span>
      ${f.resumo_curto ? `<span class="ia-resumo">${esc(f.resumo_curto)}</span>` : ''}
      ${notas ? `<span class="ia-meta">${notas}</span>` : ''}
      ${tempo ? `<span class="ia-tempo">${ic('relogio')}<span>${esc(tempo)}</span></span>` : ''}
    </button>
    ${faixaInstalar(p.id)}
    <div class="ia-rodape"><span class="tags">${tagsDe(f, 3)}</span>${botaoRemoverIA(p.id)}
      <button type="button" class="ia-saiba" data-saiba="${esc(p.id)}" aria-label="${esc(T('ia.saibaSobre', 'Saiba mais sobre {q}', { q: nome }))}">${ic('info')}${esc(T('ia.saiba', 'Saiba mais'))}</button></div>
  </div>`;
}
// 11/11/2026: trocou de idioma, os cartoes se desenham de novo. Sem isto a casca ficava
// em espanhol e os cartoes so trocavam na proxima vez que a tela se redesenhasse sozinha -
// o que, parado na mesma aba, podia nunca acontecer.
document.addEventListener('idioma-mudou', () => {
  // Cada um destes desenha um pedaco que o JavaScript escreve, e por isso nao e alcancado
  // pelo data-i18n do HTML. Cada um no seu try: um que falhe nao pode derrubar os outros.
  [renderIAs, renderEscolhas, renderHeroi, renderCatalogo, renderChaves, renderAprovadas, renderPreparar].forEach((f) => {
    try { f(true); } catch (e) { /* secao que ainda nao existe nesta tela */ }
  });
  try { if (G.rota && ROTAS[G.rota]) {
    const R = ROTAS[G.rota];
    const a = $('#rotaTitulo'), b = $('#rotaSobre'), c = $('#tituloCriacoes');
    if (a) a.textContent = TX(R.titulo);
    if (b) b.textContent = TX(R.sobre);
    if (c) c.textContent = TX(R.criacoes);
  } } catch (e) { /* fora de uma secao de gerador */ }
});
function renderIAs() {
  const lista = presetsDa(G.rota), p = presetAtual();
  const varias = lista.length > 1, aberto = !!E.trocando && varias;
  $('#seletorIA').hidden = !aberto;
  if (!p) { $('#iaAtual').innerHTML = `<p class="nota">${esc(T('ia.nenhuma', 'Nenhuma IA disponível nesta seção.'))}</p>`; return; }
  const foco = document.activeElement && document.activeElement.id;
  if (aberto) {
    $('#iaAtual').innerHTML = `<div class="ia-trocar"><span class="nota" style="flex:1;align-self:center">${esc(T('ia.quantasNaSecao', '{n} IAs nesta seção. Toque numa para escolher.', { n: lista.length }))}</span>
      <button type="button" class="bt-sec" id="btTrocarIA" aria-expanded="true" aria-controls="seletorIA" style="flex:none">${ic('baixo')}${esc(T('ia.recolher', 'Recolher'))}</button></div>`;
    renderListaIA();
  } else {
    $('#iaAtual').innerHTML = htmlIAAtual(p) + (varias
      ? `<div class="ia-trocar"><button type="button" class="bt-sec" id="btTrocarIA" aria-expanded="false" aria-controls="seletorIA">${ic('reusar')}${esc(T('ia.trocar', 'Trocar IA · {n} opções', { n: lista.length }))}</button></div>` : '');
  }
  if (foco === 'btTrocarIA' && $('#btTrocarIA')) $('#btTrocarIA').focus();
  renderEmTeste();
}
function renderListaIA() {
  const lista = presetsDa(G.rota), busca = $('#buscaIA').value.trim(), termos = norm(busca).split(/\s+/).filter(Boolean);
  const grupos = new Map();
  lista.forEach((p) => {
    const f = fichaOuPreset(p);
    const texto = norm([f.nome, p.nome, f.categoria, f.resumo_curto, f.melhor_para, f.o_que_faz, (f.tags || []).join(' ')].join(' '));
    if (termos.length && !termos.every((t) => texto.includes(t))) return;
    const cat = f.categoria || 'Outras';
    if (!grupos.has(cat)) grupos.set(cat, []);
    grupos.get(cat).push(htmlCardIA(p, f));
  });
  $('#listaIA').innerHTML = grupos.size
    ? [...grupos].map(([cat, itens]) => `<div class="grupo-ia"><h3>${esc(cat)}</h3><div class="itens">${itens.join('')}</div></div>`).join('')
    : `<p class="sem-resultado">Nenhuma IA combina com “${esc(busca)}”.</p>`;
}
function renderEmTeste() {
  const box = $('#emTeste');
  if (G.rota === 'apresentador') { box.hidden = true; return; }
  const aba = ROTAS[G.rota].aba;
  const ativos = G.presets[aba] || [];
  const ag = ((G.presets.aguardando_teste || {})[aba] || []).filter((n) => !ativos.some((p) =>
    norm(p.nome).startsWith(norm(n)) || norm(n).startsWith(norm(nomeCurto(p.nome)))));
  box.hidden = !ag.length;
  $('#listaTeste').innerHTML = ag.map((n) => `<li>${esc(rot(n))} <span class="fraco">— baixada, aguardando teste antes de liberar</span></li>`).join('');
}
function escolherIA(id) {
  E.sel = id;
  E.formato = E.duracao = E.resolucao = null;
  E.trocando = false;
  aplicarPreset();
  const b = $('#btTrocarIA');
  if (b) b.focus();
}

// ---------------------------------------------------------------- formulário (mesmo comportamento da versão anterior)
function aplicarPreset() {
  const p = presetAtual();
  if (!p) return;
  E.sel = p.id;
  const pad = p.padrao || {}, modos = p.modos || ['prompt'];
  if (!modos.includes(E.modo)) E.modo = modos[0];
  E.estilo = p.estilos ? (Object.keys(p.estilos).includes(E.estilo) ? E.estilo : pad.estilo) : null;
  E.formato = p.formatos ? (Object.keys(p.formatos).includes(E.formato) ? E.formato : pad.formato) : null;
  E.duracao = p.duracoes ? (Object.keys(p.duracoes).includes(E.duracao) ? E.duracao : pad.duracao) : null;
  const res = p.resolucoes || p.resolucoes_mp;
  E.resolucao = res ? (Object.keys(res).includes(E.resolucao) ? E.resolucao : pad.resolucao) : null;
  const qs = p.qualidades ? Object.keys(p.qualidades) : [];
  if (!qs.includes(E.qualidade)) E.qualidade = pad.qualidade || qs.find((q) => p.qualidades[q] === pad.steps) || qs[0];
  renderIAs();
  renderForm();
  renderBotaoGerar();
}
function rotuloModo(p, v) {
  if (v === 'referencia') return p.imagem_inicial ? 'Começar de uma imagem' : p.quadros_chave ? 'Primeiro/último quadro'
    : p.referencias ? 'Com imagens de referência' : 'Com imagem de referência';
  return ROT_MODO[v] || rot(v);
}
function notaMotor(m) {
  const s = String(m || '');
  if (s.startsWith('LTX')) return 'LTX-2.3: boca mais expressiva, 704×1280, até 15 s de fala.';
  if (s.startsWith('InfiniteTalk')) return 'InfiniteTalk: sem limite de duração, cerca de 480p, uns 2,5 min por trecho de 3 s.';
  return 'Automático: até 15 s de fala usa o LTX-2.3; mais longo usa o InfiniteTalk. O motor usado aparece no resultado.';
}
function renderForm() {
  const p = presetAtual();
  if (!p) return;
  const f = fichaOuPreset(p);
  const modos = p.modos || ['prompt'];
  $('#secModo').hidden = modos.length < 2;
  chips($('#modos'), modos, E.modo, (v) => { E.modo = v; renderForm(); }, (v) => rotuloModo(p, v));
  const precisaImg = E.modo === 'referencia' || E.modo === 'personagem';
  const multi = !!(p.referencias || p.quadros_chave) && E.modo === 'referencia';
  $('#secImagem').hidden = !precisaImg || multi;
  $('#secRefs').hidden = !multi;
  if (multi) renderRefs();
  const apres = p.tipo === 'apresentador';
  $('#secVoz').hidden = !apres;
  if (apres) {
    if (!p.idiomas.includes(E.idioma)) E.idioma = p.padrao.idioma;
    chips($('#idiomas'), p.idiomas, E.idioma, (v) => { E.idioma = v; renderForm(); }, (v) => v);
    if (!p.motores.includes(E.motor)) E.motor = p.padrao.motor;
    chips($('#motores'), p.motores, E.motor, (v) => { E.motor = v; renderForm(); }, (v) => v);
    $('#motorNota').textContent = notaMotor(E.motor);
    renderVozes();
    $('#limparAudio').hidden = !E.up.audio;
  }
  $('#tituloImagem').textContent = apres ? 'Foto do apresentador (de frente, rosto e ombros)'
    : p.tipo === 'contexto' ? 'Foto da pessoa (opcional — vazio = ele cria a pessoa no Krea 2)'
      : E.modo === 'personagem' ? 'Imagem do personagem'
        : (p.imagem_inicial || /i2v/.test(p.id) ? 'Imagem inicial do vídeo' : 'Imagem de referência');
  $('#secVideo').hidden = E.modo !== 'personagem';
  // grupo com uma opção só não vira botão (não há o que escolher): aparece como texto em "Fixo nesta IA"
  const fixos = [];
  const grupo = (sel, rotulo, obj, mostrar = true) => {
    const ks = obj ? Object.keys(obj) : [];
    $(sel).hidden = !mostrar || ks.length < 2;
    if (mostrar && ks.length === 1) fixos.push(`${rotulo} ${rot(nomeCurto(ks[0]) || ks[0])}`);
    return mostrar && ks.length >= 2;
  };
  if (grupo('#optEstilo', 'estilo', p.estilos)) chips($('#estilos'), Object.keys(p.estilos), E.estilo, (v) => { E.estilo = v; renderForm(); });
  const vi = E.up.video && E.up.video.segundos != null ? E.up.video : null;
  if (grupo('#optFormato', 'formato', p.formatos, !(p.quadros_chave && E.modo === 'referencia')))  // com 1º quadro, segue a imagem
    chips($('#formatos'), Object.keys(p.formatos), E.formato, (v) => { E.formato = v; renderForm(); },
      (v) => (v === IGUAL && vi ? `${v} (${vi.largura > vi.altura ? 'deitado' : vi.largura < vi.altura ? 'em pé' : 'quadrado'})` : rot(v)));
  const res = p.resolucoes || p.resolucoes_mp;
  if (grupo('#optResolucao', 'resolução', res)) chips($('#resolucoes'), Object.keys(res), E.resolucao, (v) => { E.resolucao = v; renderForm(); });
  if (grupo('#optDuracao', 'duração', p.duracoes))
    chips($('#duracoes'), Object.keys(p.duracoes), E.duracao, (v) => { E.duracao = v; renderForm(); },
      (v) => (v === IGUAL && vi ? `${v} (${seg(vi.segundos)})` : rot(v)));
  if (grupo('#optQualidade', 'qualidade', p.qualidades))
    chips($('#qualidades'), Object.keys(p.qualidades), E.qualidade, (v) => { E.qualidade = v; renderForm(); });
  $('#optForca').hidden = !(p.campos || {}).forca;
  $('#ajustesFixos').textContent = fixos.length ? `Fixo nesta IA: ${fixos.join(' · ')}.` : '';
  $('#secAjustes').hidden = !fixos.length
    && ['#optEstilo', '#optFormato', '#optResolucao', '#optDuracao', '#optQualidade', '#optForca'].every((s) => $(s).hidden);
  $('#hPrompt').textContent = apres ? 'Texto que a pessoa vai falar'
    : p.tipo === 'contexto' ? 'Descreva a CENA inteira (em português)'
      : E.modo === 'personagem' ? 'Descrição (opcional)' : 'Descreva o que você quer';
  $('#prompt').placeholder = apres ? (E.up.audio ? 'Com áudio pronto, o texto é ignorado.'
    : 'Escreva aqui o que ele vai FALAR. Ex.: Olá! Hoje vou mostrar como criar vídeos com inteligência artificial…')
    : multi && p.referencias ? 'Ex.: <Picture 1> é o personagem principal, vestindo a roupa de <Picture 2>, dirigindo o carro de <Picture 3> pelo cenário de <Picture 4>. Descreva a ação, a câmera e o som.'
      : p.tipo === 'contexto' ? 'Ex.: Um homem jovem de fone de ouvido, sentado na cama de manhã, olhos fechados, balançando a cabeça devagar; a câmera chega bem devagar, mantendo o rosto no quadro.'
      : E.modo === 'personagem' ? 'Opcional: descreva o personagem e a ação (ex.: andando pela calçada, câmera parada)'
        : 'Descreva o que você quer gerar…';
  const dica = f.dica_prompt;
  $('#dicaPrompt').hidden = !dica;
  if (dica) $('#dicaPrompt').innerHTML = `${ic('dica')}<span>${esc(dica)}</span>`;
  renderEnquadrar();
  renderTexto();
  estimarLogo();
}

function renderRefs() {
  const p = presetAtual(), qc = p.quadros_chave, box = $('#refs');
  const max = qc ? 2 : ((p.referencias && p.referencias.max) || 9);
  if (E.refs.length > max) E.refs = E.refs.slice(0, max);
  box.innerHTML = '';
  E.refs.forEach((r, i) => {
    const rotulo = qc ? qc.rotulos[i] : `Picture ${i + 1}`;
    const d = document.createElement('div');
    d.className = 'ref';
    const bt = document.createElement('button');
    bt.type = 'button'; bt.className = 'ref-bt';
    bt.title = qc ? rotulo : `Clique para inserir <Picture ${i + 1}> no prompt`;
    bt.setAttribute('aria-label', qc ? `${rotulo} (imagem ${i + 1})` : `Inserir <Picture ${i + 1}> no prompt`);
    const img = document.createElement('img');
    img.src = r.url; img.alt = '';
    const b = document.createElement('b');
    b.textContent = rotulo;
    bt.append(img, b);
    if (!qc) bt.onclick = () => inserirNoPrompt(`<Picture ${i + 1}>`);
    const x = document.createElement('button');
    x.type = 'button'; x.className = 'ref-x'; x.innerHTML = ic('fechar');
    x.setAttribute('aria-label', `Remover ${rotulo}`);
    x.onclick = () => { E.refs.splice(i, 1); renderRefs(); estimarLogo(); };
    d.append(bt, x);
    box.appendChild(d);
  });
  $('#refsConta').textContent = `(${E.refs.length} de ${max})`;
  $('#refsDica').textContent = qc
    ? '1ª imagem = onde o vídeo COMEÇA (ex.: último quadro da cena anterior). 2ª imagem (opcional) = onde ele TERMINA.'
    : 'Clique numa imagem para colocar a etiqueta dela no prompt.';
  $('#hRefs').firstChild.textContent = qc ? 'Primeiro e último quadro ' : 'Imagens de referência ';
  $('#upRefs').hidden = E.refs.length >= max;
}
function inserirNoPrompt(txt) {
  const t = $('#prompt'), a = t.selectionStart ?? t.value.length, b = t.selectionEnd ?? a;
  t.value = t.value.slice(0, a) + txt + ' ' + t.value.slice(b);
  t.focus();
  t.selectionStart = t.selectionEnd = a + txt.length + 1;
}

function renderEnquadrar() {
  const on = E.modo === 'personagem';
  $('#secEnquadrar').hidden = !on;
  if (!on) return;
  chips($('#enquadrarChips'), Object.keys(ENQ), Object.keys(ENQ).find((k) => ENQ[k] === E.enquadrar),
    (v) => { E.enquadrar = ENQ[v]; renderEnquadrar(); }, (v) => v);
  const pronto = E.up.imagem && E.up.video;
  $('#enquadre').hidden = !(E.enquadrar && pronto && E.enq.res && E.enq.res.ok);
  if (!E.enquadrar) { $('#enqStatus').textContent = 'Usa a imagem como está. Se o vídeo for de perto e a imagem de corpo inteiro, o personagem pode sair cortado.'; return; }
  if (!pronto) { $('#enqStatus').textContent = 'Envie a imagem e o vídeo: o personagem é recortado para ficar do mesmo tamanho e posição da pessoa do vídeo.'; return; }
  pedirEnquadre();
}
async function pedirEnquadre() {
  const est = E, chave = est.up.imagem.nome + '|' + est.up.video.nome;
  if (est.enq.chave === chave) return mostrarEnquadre();
  est.enq = { chave, res: null };
  $('#enquadre').hidden = true;
  $('#enqStatus').textContent = 'Detectando a pose… (alguns segundos; se a GPU estiver gerando, espera a geração atual)';
  let res;
  try {
    res = await api('/api/enquadrar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imagem: est.up.imagem.nome, video: est.up.video.nome }) });
  } catch (err) { res = { ok: false, motivo: err.message }; }
  if (est.enq.chave !== chave) return;  // trocou de arquivo enquanto detectava
  est.enq.res = res;
  if (est === E && E.modo === 'personagem') mostrarEnquadre();
}
function mostrarEnquadre() {
  const r = E.enq.res;
  if (!r) return;
  $('#enquadre').hidden = !r.ok;
  if (!r.ok) { $('#enqStatus').textContent = '⚠ ' + (r.motivo || 'Não deu para enquadrar') + ' — vai usar a imagem original.'; return; }
  const v = $('#enqVideo'), url = E.up.video.url + '#t=0.3';
  if (v.getAttribute('src') !== url) v.src = url;
  if ($('#enqImagem').getAttribute('src') !== r.url) $('#enqImagem').src = r.url;
  $('#enqStatus').textContent = `Cabeça e ombros alinhados com o vídeo (detecção por ${r.fonte})`
    + (r.preenchido ? ' · bordas completadas repetindo o fundo' : '')
    + (r.tamanho && r.tamanho[1] < 500 ? ' · ⚠ recorte pequeno: a imagem vai perder nitidez; uma imagem do personagem mais de perto fica melhor' : '');
}

// ---------------------------------------------------------------- estimativa
let estT = null, estSeq = 0;
function estimarLogo(ms = 250) { clearTimeout(estT); estT = setTimeout(estimar, ms); }
async function estimar() {
  if (!ehGerador(G.rota) || !E) return;
  const p = presetAtual();
  if (!p) return;
  const seq = ++estSeq, el = $('#estimativa');
  try {
    const q = new URLSearchParams({ preset: p.id, duracao: E.duracao || '', qualidade: E.qualidade || '',
      formato: E.formato || '', resolucao: E.resolucao || '', video: (E.modo === 'personagem' && E.up.video && E.up.video.nome) || '',
      motor: E.motor || '', texto: p.tipo === 'apresentador' ? ($('#prompt').value || '') : '',
      audio: (p.tipo === 'apresentador' && E.up.audio && E.up.audio.nome) || '' });
    const r = await api('/api/estimativa?' + q, { timeout: 15000 });
    if (seq !== estSeq) return;
    if (r.segundos == null) {
      el.innerHTML = r.motivo ? `<span class="aviso-linha" style="color:var(--fraco)">${ic('info')}<span>${esc(rot(r.motivo))}</span></span>` : '';
      return;
    }
    const partes = [r.tamanho && `${r.tamanho[0]}×${r.tamanho[1]}`,
      r.segundos_video && `${seg(r.segundos_video)} de vídeo em ${r.segmentos} trecho${r.segmentos > 1 ? 's' : ''}`,
      r.carregado ? 'modelo já carregado (mais rápido)' : 'inclui carregar o modelo do HD',
      r.historico ? 'baseada nas suas gerações' : 'estimativa inicial (melhora com o uso)'].filter(Boolean);
    el.innerHTML = `Estimativa: <b>~${esc(fmt(r.segundos))}</b><br>${esc(partes.join(' · '))}`
      + (r.aviso ? `<span class="aviso-linha">${ic('alerta')}<span>${esc(rot(r.aviso))}</span></span>` : '');
  } catch (e) { if (seq === estSeq) el.textContent = ''; }
}
let assinaturaSistema = '';
function checarMudancaSistema() {
  const s = G.sistema || {}, a = `${s.ultimo_preset}|${s.fila}`;
  if (a === assinaturaSistema) return;
  const mudouPreset = assinaturaSistema.split('|')[0] !== String(s.ultimo_preset);
  assinaturaSistema = a;
  estimarLogo(50);
  if (mudouPreset && E && presetsDa(G.rota).length) renderIAs();
}

// ---------------------------------------------------------------- uploads (clique, teclado, arrastar e colar)
const TXT_UP = { imagem: 'Clique, arraste ou cole (Ctrl+V) a imagem', video: '1 pessoa, câmera parada, corpo inteiro — clique ou arraste o vídeo',
  voz: 'Clonar uma voz nova: envie 10–20 s só da voz (sem música)', audio: 'Clique ou arraste o áudio que ele vai falar',
  refs: 'Adicionar imagens (rosto, roupa, carro, cenário…)' };
async function enviar(tipo, arquivo) {
  const fd = new FormData();
  fd.append('arquivo', arquivo);
  return api(`/api/upload?tipo=${tipo}`, { method: 'POST', body: fd });
}
function aceita(input, f) {
  const ac = String(input.accept || '').split(',').map((s) => s.trim()).filter(Boolean);
  return !ac.length || ac.some((a) => (a.endsWith('/*') ? String(f.type).startsWith(a.slice(0, -1)) : f.type === a));
}
function ligarUpload(box, fn) {
  const input = box.querySelector('input');
  input.addEventListener('change', (e) => { const fs = [...e.target.files]; e.target.value = ''; if (fs.length) fn(fs); });
  box.addEventListener('dragover', (e) => { e.preventDefault(); box.classList.add('arrastando'); });
  box.addEventListener('dragleave', () => box.classList.remove('arrastando'));
  box.addEventListener('drop', (e) => {
    e.preventDefault();
    box.classList.remove('arrastando');
    const fs = [...((e.dataTransfer && e.dataTransfer.files) || [])].filter((f) => aceita(input, f));
    if (fs.length) fn(fs); else aviso('Esse tipo de arquivo não serve aqui.', 'aviso');
  });
}
function renderUploads() {
  const por = (id, obj, tag, padrao) => {
    const box = $(id), m = box.querySelector(tag), t = box.querySelector('.up-txt');
    if (obj) {
      if (m.getAttribute('src') !== obj.url) m.src = obj.url;
      m.hidden = false;
      t.textContent = obj.rotulo || String(obj.nome || '');
    } else {
      if (m.getAttribute('src')) { m.removeAttribute('src'); if (m.load) m.load(); }
      m.hidden = true;
      t.textContent = padrao;
    }
  };
  por('#upImagem', E.up.imagem, 'img', TXT_UP.imagem);
  por('#upVideo', E.up.video, 'video', TXT_UP.video);
  $('#upVideo video').controls = !!E.up.video;
  por('#upVoz', E.up.voz, 'audio', TXT_UP.voz);
  por('#upAudio', E.up.audio, 'audio', TXT_UP.audio);
  $('#upRefs .up-txt').textContent = TXT_UP.refs;
}
async function enviarImagem(f) {
  const est = E, t = $('#upImagem .up-txt');
  t.textContent = 'Enviando…';
  try {
    const r = await enviar('imagem', f);
    r.rotulo = f.name;
    est.up.imagem = r;
    if (est === E) { renderUploads(); renderEnquadrar(); renderTexto(); estimarLogo(); }
  } catch (err) { if (est === E) t.textContent = 'Erro: ' + err.message; }
}
async function enviarVideo(f) {
  const est = E, t = $('#upVideo .up-txt');
  t.textContent = 'Enviando e convertendo para 16 fps…';
  try {
    const r = await enviar('video', f);
    r.rotulo = f.name + (r.segundos != null ? ` (16 fps · ${seg(r.segundos)} · ${r.largura}×${r.altura})` : ' (16 fps)');
    est.up.video = r;
    if (est === E) { renderUploads(); renderForm(); }
  } catch (err) { if (est === E) t.textContent = 'Erro: ' + err.message; }
}
async function enviarRefs(lista) {
  const est = E, pa = presetAtual(), max = pa.quadros_chave ? 2 : ((pa.referencias || {}).max || 9);
  const fs = lista.slice(0, max - est.refs.length);
  const t = $('#upRefs .up-txt');
  t.textContent = `Enviando ${fs.length} imagem(ns)…`;
  for (const f of fs) {
    try { est.refs.push(await enviar('imagem', f)); if (est === E) renderRefs(); }
    catch (err) { if (est === E) mostrarErro('Erro ao enviar ' + f.name + ': ' + err.message); }
  }
  if (est === E) { t.textContent = TXT_UP.refs; estimarLogo(); }
}
async function enviarAudio(chave, f) {
  const est = E, box = chave === 'voz' ? $('#upVoz') : $('#upAudio'), t = box.querySelector('.up-txt');
  t.textContent = 'Enviando…';
  try {
    const r = await enviar('audio', f);
    r.rotulo = `${f.name} (${seg(r.segundos || 0)})`;
    est.up[chave] = r;
    if (chave === 'voz') est.vozId = null;
    if (est === E) { renderUploads(); renderForm(); }
  } catch (err) { if (est === E) t.textContent = 'Erro: ' + err.message; }
}
function prepararUploads() {
  ligarUpload($('#upImagem'), (fs) => enviarImagem(fs[0]));
  ligarUpload($('#upVideo'), (fs) => enviarVideo(fs[0]));
  ligarUpload($('#upRefs'), (fs) => enviarRefs(fs));
  ligarUpload($('#upVoz'), (fs) => enviarAudio('voz', fs[0]));
  ligarUpload($('#upAudio'), (fs) => enviarAudio('audio', fs[0]));
  $('#limparAudio').onclick = () => { E.up.audio = null; renderUploads(); renderForm(); };
  document.addEventListener('paste', (e) => {
    if (!ehGerador(G.rota) || !E) return;
    const fs = [...((e.clipboardData && e.clipboardData.files) || [])].filter((f) => String(f.type).startsWith('image/'));
    if (!fs.length) return;
    if (!$('#secRefs').hidden) { e.preventDefault(); enviarRefs(fs); }
    else if (!$('#secImagem').hidden) { e.preventDefault(); enviarImagem(fs[0]); }
  });
}

// ------------------------------------------------- chave do ElevenLabs de QUEM USA o estudio
// 09/11/2026: a lista de vozes desta tela mostra as vozes da nuvem com "☁", mas nao havia
// onde dizer que a pessoa TEM conta: sem chave ela so via as vozes locais e nenhuma explicacao.
// Esta caixa pede a chave DELA, que vai para um arquivo na maquina dela (pasta API) - nada de
// ElevenLabs viaja no pacote, e sem chave o estudio inteiro continua funcionando local.
// Tudo com "se existe": se o HTML for de uma versao velha, a funcao sai calada em vez de
// matar o iniciar() (foi o que o "FILA is not defined" fez em 07/11).
function recadoNuvem11(texto, tipo) {
  const m = $('#nuvem11Msg');
  if (!m) return;
  m.textContent = texto || '';
  m.className = 'nuvem-msg' + (tipo ? ' ' + tipo : '');
}
// "tem" = existe chave guardada; "serve" = ela devolveu voz de verdade. O ponto verde so
// acende quando SERVE: guardar uma chave errada e ver a luz verde foi o que me enganou no
// teste de 09/11 - a mensagem dizia que nao veio voz nenhuma e a bolinha dizia que estava tudo bem.
function seloNuvem11(tem, serve) {
  const bom = serve === undefined ? !!tem : !!serve;
  const s = $('#nuvem11Selo');
  if (s) {
    s.classList.toggle('on', bom);
    s.title = bom ? 'Uma chave esta guardada e funcionando.'
      : tem ? 'Chave guardada, mas o ElevenLabs nao devolveu nenhuma voz.'
            : 'Sem chave: so voz local.';
  }
  const i = $('#nuvem11Chave');
  if (i) i.placeholder = tem ? 'uma chave ja esta guardada — cole outra para trocar'
                             : 'cole a chave aqui';
}
function seloDepoisDasVozes() {
  if (G.temChave11 === undefined) return;   // ainda nao sei se ha chave
  seloNuvem11(G.temChave11, (G.vozes11 || []).length > 0);
}
async function recarregarVozes11() {
  await carregarVozes();
  if (G.rota && !$('#secVoz').hidden) renderVozes();
}
function prepararNuvem11() {
  const bloco = $('#nuvem11Bloco');
  if (!bloco) return;
  // O GET diz se EXISTE chave, nunca se ela funciona. Quem responde isso e a lista de
  // vozes: chave guardada + lista vazia = chave que nao serve. Por isso o ponto verde
  // espera a lista (seloDepoisDasVozes, chamado no fim de carregarVozes).
  api('/api/chave-nuvem', { timeout: 8000 })
    .then((d) => { G.temChave11 = !!(d && d.tem); seloDepoisDasVozes(); })
    .catch(() => { /* estudio velho: a caixa so fica quieta */ });
  const salvar = $('#nuvem11Salvar'), tirar = $('#nuvem11Tirar');
  if (salvar) salvar.onclick = async () => {
    const campo = $('#nuvem11Chave');
    const chave = ((campo && campo.value) || '').trim();
    if (!chave) { recadoNuvem11('Cole a chave antes de salvar.', 'ruim'); return; }
    recadoNuvem11('Conferindo a chave com o ElevenLabs…');
    try {
      const d = await api('/api/chave-nuvem', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chave }), timeout: 30000 });
      campo.value = '';
      G.temChave11 = !!d.tem;
      seloNuvem11(d.tem, d.ok);
      recadoNuvem11(d.mensagem, d.ok ? 'bom' : 'ruim');
      if (d.ok) await recarregarVozes11();
    } catch (e) { recadoNuvem11(String((e && e.message) || e), 'ruim'); }
  };
  if (tirar) tirar.onclick = async () => {
    const ok = await confirmar({ titulo: 'Remover a chave do ElevenLabs?',
      texto: 'A chave sai desta maquina e as vozes da nuvem desaparecem da lista. A narracao '
           + 'continua funcionando com as vozes locais, de graca.',
      sim: 'Remover a chave', icone: 'lixo' });
    if (!ok) return;
    try {
      const d = await api('/api/chave-nuvem', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chave: '' }), timeout: 15000 });
      const campo = $('#nuvem11Chave');
      if (campo) campo.value = '';
      G.temChave11 = false;
      seloNuvem11(false);
      recadoNuvem11(d.mensagem, 'bom');
      await recarregarVozes11();
    } catch (e) { recadoNuvem11(String((e && e.message) || e), 'ruim'); }
  };
}

// ---------------------------------------------------------------- vozes do Apresentador
async function carregarVozes() {
  try { G.vozes = await api('/api/vozes', { timeout: 8000 }); } catch (e) { G.vozes = []; }
  if (!Array.isArray(G.vozes)) G.vozes = [];
  // vozes do ElevenLabs (nuvem, paga): só aparecem se a chave estiver salva na pasta API
  try {
    const r = await api('/api/vozes11', { timeout: 15000 });
    G.vozes11 = Array.isArray(r.vozes) ? r.vozes : [];
    G.creditos11 = r.creditos || null;
  } catch (e) { G.vozes11 = []; G.creditos11 = null; }
  try { seloDepoisDasVozes(); } catch (e) { /* a bolinha nao pode derrubar as vozes */ }
}
function renderVozes() {
  // "Voz padrão" + cada voz já clonada; a voz recém-enviada entra como "Nova (ainda não salva)"
  const NOVA = 'Nova (ainda não salva)';
  const v11 = G.vozes11 || [];
  const nome11 = (v) => `☁ ${v.nome}`;  // ☁ = voz do ElevenLabs (nuvem, gasta crédito da conta dele)
  const opcoes = ['Voz padrão', ...G.vozes.map((v) => v.nome), ...v11.map(nome11)];
  if (E.up.voz && !E.vozId) opcoes.push(NOVA);
  const atual = E.voz11 ? nome11(v11.find((x) => x.id === E.voz11) || { nome: '?' })
    : (E.vozId ? (G.vozes.find((v) => v.id === E.vozId) || {}).nome : (E.up.voz ? NOVA : 'Voz padrão'));
  chips($('#vozes'), opcoes, atual, (v) => {
    E.voz11 = null;
    if (v === 'Voz padrão') { E.vozId = null; E.up.voz = null; limparUpVoz(); }
    else if (v.startsWith('☁ ')) { E.voz11 = (v11.find((x) => nome11(x) === v) || {}).id; E.vozId = null; E.up.voz = null; limparUpVoz(); }
    else if (v !== NOVA) { E.vozId = (G.vozes.find((x) => x.nome === v) || {}).id; E.up.voz = null; limparUpVoz(); }
    renderForm();
  }, (v) => v);
  $('#salvarVoz').hidden = !(E.up.voz && !E.vozId);
  const v = G.vozes.find((x) => x.id === E.vozId), st = $('#vozStatus');
  if (E.voz11) {
    const esc11 = (v11.find((x) => x.id === E.voz11) || {}).nome || '';
    const c = G.creditos11;
    const sobra = c ? ` Sobram ${(c.limite - c.usados).toLocaleString('pt-BR')} caracteres neste mês.` : '';
    st.innerHTML = `Voz <b>${esc(esc11)}</b> do <b>ElevenLabs</b> (nuvem): gasta crédito da sua conta, 1 crédito por letra do texto.${esc(sobra)}`;
    $('#salvarVoz').hidden = true;
    return;
  }
  if (v) {
    st.innerHTML = `Usando a voz <b>${esc(v.nome)}</b> (${seg(v.segundos || 0)}). <button type="button" class="bt-fantasma mini" id="apagarVoz">${ic('lixo')}Apagar esta voz</button>`;
    $('#apagarVoz').onclick = async () => {
      const ok = await confirmar({ titulo: 'Apagar esta voz?', texto: `A voz "${v.nome}" sai da lista e o áudio guardado dela é apagado do HD. Não dá para desfazer.`,
        sim: 'Apagar voz', icone: 'lixo' });
      if (!ok) return;
      try {
        G.vozes = (await api(`/api/vozes/remover/${encodeURIComponent(v.id)}`, { method: 'POST' })).vozes || [];
        E.vozId = null;
        renderForm();
        aviso('Voz apagada.');
      } catch (err) { aviso('Não consegui apagar a voz: ' + err.message, 'erro'); }
    };
  } else {
    st.textContent = E.up.voz ? 'Voz nova enviada. Dê um nome e salve para reusar depois sem enviar de novo.' : '';
  }
}
function limparUpVoz() { $('#nomeVoz').value = ''; renderUploads(); }
function prepararVozes() {
  $('#btSalvarVoz').onclick = async () => {
    const nome = $('#nomeVoz').value.trim();
    if (!nome) { $('#vozStatus').textContent = 'Escreva um nome para a voz.'; $('#nomeVoz').focus(); return; }
    try {
      const r = await api('/api/vozes', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, arquivo: E.up.voz.nome }) });
      G.vozes = r.vozes || [];
      E.vozId = (G.vozes[G.vozes.length - 1] || {}).id;
      E.up.voz = null;
      limparUpVoz();
      renderForm();
      aviso(`Voz "${nome}" salva na lista.`);
    } catch (err) { $('#vozStatus').textContent = 'Erro ao salvar: ' + err.message; }
  };
}

// ---------------------------------------------------------------- IA de texto (23/09/2026)
// "✨ Melhorar prompt" (Imagem/Vídeo), "Escrever o texto" (Pessoa falando) e "Descrever esta imagem".
// POST /api/texto: placa livre = roda na placa e descarrega no fim; placa ocupada = Qwen3.5-9B no processador.
const ONDE_TEXTO = { placa: { txt: 'rodou na placa de vídeo', ic: 'placa' }, processador: { txt: 'rodou no processador', ic: 'processador' } };
const TITULO_TEXTO = { melhorar: 'Prompt melhorado', escrever: 'Texto escrito pela IA', descrever: 'Descrição da imagem' };
function htmlOndeTexto(r) {
  const o = ONDE_TEXTO[r.onde] || { txt: r.onde, ic: 'info' };
  const vel = r.tokens_por_segundo ? ` (${num(r.tokens_por_segundo, 0)} tokens/s)` : '';
  return `${ic(o.ic)}<span>${esc(r.modelo)} · ${esc(o.txt)} · ${esc(fmt(r.segundos))}${esc(vel)}</span>`;
}
// status ao lado do botão enquanto espera: fase do servidor (carregando na placa, escrevendo...) + tempo
async function pedirTexto(corpo, aoMudar) {
  const t0 = Date.now();
  let vivo = true;
  const olhar = async () => {
    while (vivo) {
      let fase = null;
      try { const s = await api('/api/texto/estado', { timeout: 3000 }); fase = s.em_uso && s.em_uso.fase; } catch (e) { /* segue */ }
      if (!vivo) break;
      aoMudar(`${fase || 'Pensando'}… ${fmt((Date.now() - t0) / 1000)}`);
      await new Promise((r) => setTimeout(r, 1200));
    }
  };
  olhar();
  try {
    return await api('/api/texto', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo), timeout: 15 * 60 * 1000 });
  } finally { vivo = false; }
}
function textoPedindo() { return !!(E && E.texto && E.texto.ocupado); }
function renderTexto() {
  if (!E || !ehGerador(G.rota)) return;
  const p = presetAtual(), T = E.texto || (E.texto = { caixa: null, status: '', ocupado: false });
  const apres = !!p && p.tipo === 'apresentador';
  const bm = $('#btMelhorar'), be = $('#btEscrever'), bd = $('#btDescrever');
  bm.hidden = apres || !p;
  be.hidden = !apres;
  // "Descrever esta imagem": onde tem UMA imagem enviada (não na foto do apresentador)
  $('#barraDescrever').hidden = apres || $('#secImagem').hidden || !E.up.imagem;
  [bm, be, bd].forEach((b) => { b.disabled = T.ocupado; b.setAttribute('aria-busy', String(T.ocupado)); });
  const st = $('#textoStatus'), sd = $('#descreverStatus');
  const alvo = T.statusDe === 'descrever' ? sd : st, outro = alvo === st ? sd : st;
  outro.textContent = '';
  outro.classList.remove('erro');
  alvo.textContent = T.status || '';
  alvo.classList.toggle('erro', !!T.erro);
  const c = T.caixa, cx = $('#textoCaixa');
  cx.hidden = !c;
  if (!c) return;
  $('#textoTitulo').textContent = TITULO_TEXTO[c.modo] || 'IA de texto';
  const onde = $('#textoOnde');
  onde.className = `texto-ia-onde ${c.r.onde || ''}`;
  onde.innerHTML = htmlOndeTexto(c.r);
  onde.title = c.r.onde === 'processador'
    ? 'A placa de vídeo estava ocupada: a IA rápida rodou no processador para não atrapalhar a geração.'
    : 'Rodou na placa de vídeo e foi descarregada dela logo depois (a placa já está livre de novo).';
  const desc = c.modo === 'descrever';
  $('#textoComparar').firstElementChild.hidden = desc && !c.usado;
  $('#textoAntes').textContent = c.antes || '(caixa vazia)';
  $('#textoDepois').textContent = c.depois;
  $('#textoDepoisRot').textContent = desc ? (c.usado ? 'Descrição (já está na caixa acima)' : 'Descrição')
    : 'Depois (já está na caixa acima — revise antes de gerar)';
  const av = $('#textoAviso');
  av.hidden = !c.r.aviso;
  av.innerHTML = c.r.aviso ? `${ic('alerta')}<span>${esc(c.r.aviso)}</span>` : '';
  $('#btUsarTexto').hidden = !desc || c.usado;
  $('#btJuntarTexto').hidden = !desc || c.usado;
  $('#btDesfazer').hidden = desc && !c.usado;
  pintarIcones(cx);
}
async function acaoTexto(modo) {
  const p = presetAtual();
  if (!p || textoPedindo()) return;
  const est = E, T = est.texto, entrada = $('#prompt').value.trim();
  let corpo;
  if (modo === 'descrever') {
    if (!est.up.imagem) { aviso('Envie a imagem primeiro.', 'aviso'); return; }
    corpo = { tarefa: 'descrever_imagem', entrada: '', contexto: { imagem: est.up.imagem.nome, preset: p.id } };
  } else if (modo === 'escrever') {
    if (!entrada) { T.status = 'Escreva o TEMA na caixa (ex.: 3 dicas para dormir melhor) e clique de novo.'; T.erro = true; T.statusDe = 'escrever'; renderTexto(); $('#prompt').focus(); return; }
    corpo = { tarefa: 'roteiro', entrada, contexto: { preset: 'apresentador', idioma: est.idioma || 'Português', segundos: 15 }, modelo: 'principal' };
  } else {
    if (!entrada) { T.status = 'Escreva o pedido primeiro (pode ser curto, em português).'; T.erro = true; T.statusDe = 'melhorar'; renderTexto(); $('#prompt').focus(); return; }
    const f = fichaOuPreset(p);
    corpo = { tarefa: 'melhorar_prompt', entrada, contexto: { preset: p.id, ia: nomeCurto(f.nome || p.nome), estilo: est.estilo || undefined, modo: est.modo || undefined } };
  }
  T.ocupado = true; T.erro = false; T.statusDe = modo; T.status = 'Começando…';
  renderTexto();
  try {
    const r = await pedirTexto(corpo, (txt) => { T.status = txt; if (est === E) renderTexto(); });
    const antes = est === E ? $('#prompt').value : est.prompt;
    if (modo === 'descrever') {
      T.caixa = { modo, antes, depois: r.texto, r, usado: false };
    } else {
      if (est === E) $('#prompt').value = r.texto; else est.prompt = r.texto;
      T.caixa = { modo, antes, depois: r.texto, r, usado: true };
      if (est === E && presetAtual() && presetAtual().tipo === 'apresentador') estimarLogo(300);
    }
    T.status = '';
    aviso(`${TITULO_TEXTO[modo]}: ${r.modelo} ${(ONDE_TEXTO[r.onde] || {}).txt || ''} em ${fmt(r.segundos)}.`);
  } catch (e) {
    T.status = 'Não deu certo: ' + e.message; T.erro = true;
  } finally {
    T.ocupado = false;
    if (est === E) renderTexto();
  }
}
function usarTexto(juntar) {
  const c = E.texto.caixa;
  if (!c) return;
  const t = $('#prompt'), antes = t.value;
  t.value = juntar && antes.trim() ? `${antes.trim()}\n\n${c.depois}` : c.depois;
  c.antes = antes;
  c.usado = true;
  renderTexto();
  t.focus();
}
function desfazerTexto() {
  const c = E.texto.caixa;
  if (!c) return;
  $('#prompt').value = c.antes || '';
  E.texto.caixa = null;
  E.texto.status = 'Desfeito: voltou o texto de antes.';
  E.texto.erro = false;
  renderTexto();
  $('#prompt').focus();
}
function prepararTexto() {
  $('#btMelhorar').onclick = () => acaoTexto('melhorar');
  $('#btEscrever').onclick = () => acaoTexto('escrever');
  $('#btDescrever').onclick = () => acaoTexto('descrever');
  $('#btUsarTexto').onclick = () => usarTexto(false);
  $('#btJuntarTexto').onclick = () => usarTexto(true);
  $('#btDesfazer').onclick = desfazerTexto;
  $('#btFecharTexto').onclick = () => { E.texto.caixa = null; E.texto.status = ''; renderTexto(); };
}

// ---------------------------------------------------------------- gerar e reusar
function mostrarErro(msg) { const e = $('#erro'); e.textContent = rot(msg); e.hidden = false; }
function esconderErro() { $('#erro').hidden = true; $('#erro').textContent = ''; }
async function gerar() {
  const p = presetAtual(), bt = $('#gerar');
  if (!p || bt.disabled) return;
  esconderErro();
  bt.disabled = true;
  $('#gerarTxt').textContent = 'Enviando…';
  try {
    await api('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      preset: p.id, modo: E.modo, prompt: $('#prompt').value, estilo: E.estilo, formato: E.formato,
      duracao: E.duracao, resolucao: E.resolucao, qualidade: E.qualidade, enquadrar: E.modo === 'personagem' && E.enquadrar, seed: $('#seed').value, forca: +$('#forca').value,
      imagem: E.up.imagem && E.up.imagem.nome,
      imagens: (p.referencias || p.quadros_chave) && E.modo === 'referencia' ? E.refs.map((r) => r.nome) : undefined,
      voz: p.tipo === 'apresentador' && E.up.voz ? E.up.voz.nome : undefined,
      voz_id: p.tipo === 'apresentador' ? E.vozId || undefined : undefined,
      voz11: p.tipo === 'apresentador' ? E.voz11 || undefined : undefined,
      audio: p.tipo === 'apresentador' && E.up.audio ? E.up.audio.nome : undefined,
      idioma: p.tipo === 'apresentador' ? E.idioma : undefined,
      motor: p.tipo === 'apresentador' ? (E.motor || '').split(' ')[0].replace('LTX-2.3', 'LTX') : undefined, video: E.up.video && E.up.video.nome }) });
    aviso(`Pedido enviado para a fila: ${nomeCurto(p.nome)}. Acompanhe o progresso na lista de criações.`);
    atualizar(true);
  } catch (err) { mostrarErro(err.message); }
  bt.disabled = false;
  renderBotaoGerar();
}
function reusar(j) {
  const rota = rotaDoJob(j), p = presetsDa(rota).find((x) => x.id === j.preset);
  if (!p || j.preset_existe === false) { aviso('Essa IA foi removida do estúdio: não dá para reusar este trabalho.', 'aviso'); return; }
  const est = ESTADOS[rota] || (ESTADOS[rota] = estadoNovo(rota));
  est.sel = j.preset; est.modo = j.modo; est.estilo = j.estilo; est.formato = j.formato; est.duracao = j.duracao;
  if (j.imagens) est.refs = j.imagens.map((n) => ({ nome: n, url: `/api/entrada/${encodeURIComponent(n)}` }));
  est.resolucao = j.resolucao || null;
  est.enquadrar = j.enquadrar !== undefined ? !!j.enquadrar : true;
  est.qualidade = j.qualidade;
  est.prompt = j.prompt || '';
  est.seed = j.seed != null ? String(j.seed) : '';
  if (j.forca) est.forca = +j.forca;
  if (j.imagem) est.up.imagem = { nome: j.imagem, url: `/api/entrada/${encodeURIComponent(j.imagem)}`, rotulo: 'Imagem do trabalho reusado' };
  if (j.video) est.up.video = { nome: j.video, url: `/api/entrada/${encodeURIComponent(j.video)}`, rotulo: 'Vídeo do trabalho reusado' };
  if (ehApresentador(p)) {
    est.idioma = j.idioma || null;
    const motorCurto = (m) => String(m || '').split(' ')[0].replace('LTX-2.3', 'LTX');
    est.motor = (p.motores || []).find((m) => motorCurto(m) === motorCurto(j.motor)) || null;
    est.vozId = j.voz_id && G.vozes.some((v) => v.id === j.voz_id) ? j.voz_id : null;
    est.voz11 = j.voz11 && (G.vozes11 || []).some((v) => v.id === j.voz11) ? j.voz11 : null;
    est.up.voz = !est.vozId && j.voz && !j.voz_id ? { nome: j.voz, url: `/api/entrada/${encodeURIComponent(j.voz)}`, rotulo: 'Voz do trabalho reusado' } : null;
    est.up.audio = j.audio ? { nome: j.audio, url: `/api/entrada/${encodeURIComponent(j.audio)}`, rotulo: 'Áudio do trabalho reusado' } : null;
  }
  est.trocando = false;
  if ($('#lupa').open) { lupaOrigem = null; fecharLupa(); }
  aviso('Configurações carregadas no formulário. Ajuste o que quiser e clique em Gerar.');
  if (G.rota !== rota) { location.hash = '#/' + rota; return; }
  E = est;
  restaurarCampos();
  aplicarPreset();
  $('#painelCorpo').scrollTo({ top: 0, behavior: 'smooth' });
  if (window.matchMedia('(max-width: 980px)').matches) $('#painel').scrollIntoView({ behavior: 'smooth' });
}

// ================================================================ GALERIA
let galSeq = 0, galT = null;
function pararGaleria() { galSeq++; clearTimeout(galT); }
async function atualizar(forcar) {
  clearTimeout(galT);
  const gen = ++galSeq, rota = G.rota;
  if (!ehGerador(rota)) return;
  let ativos = false;
  if (!document.hidden || !G.jobsCarregado[rota] || forcar === true) {
    try {
      const pedir = G.pedir[rota] || PEDIR_PADRAO;
      const { dados, headers } = await apiCompleta(`/api/trabalhos?aba=${ROTAS[rota].aba}&limite=${pedir}`, { timeout: 15000 });
      if (gen !== galSeq || rota !== G.rota) return;
      const lista = Array.isArray(dados) ? dados : [];
      // X-Total = quantas existem na aba (servidor novo); sem ele, o servidor antigo corta em 120 sem dizer quantas faltam
      const xt = headers.get('X-Total');
      G.faltam[rota] = xt != null && xt !== '' && isFinite(+xt) ? Math.max(0, +xt - lista.length) : (lista.length === 120 ? -1 : 0);
      G.jobs[rota] = lista.filter((j) => rotaDoJob(j) === rota);
      G.jobsCarregado[rota] = true;
      renderGaleria();
      cabecalhoDaGaleria(G.jobs[rota]);
      ativos = G.jobs[rota].some((j) => j.estado === 'fila' || j.estado === 'rodando');
    } catch (e) { /* servidor reiniciando: tenta de novo */ }
  }
  if (gen !== galSeq) return;
  galT = setTimeout(atualizar, ativos ? 1500 : 5000);
}
const grupoEstado = (j) => (j.estado === 'concluido' ? 'prontos' : (j.estado === 'fila' || j.estado === 'rodando') ? 'andamento' : 'erros');
function passaFiltro(j, F) {
  if (F.ia && j.preset !== F.ia) return false;
  if (F.estado !== 'todos' && grupoEstado(j) !== F.estado) return false;
  if (F.busca) {
    const alvo = norm(`${j.prompt || ''} ${iaDe(j).nome} ${j.id}`);
    if (!norm(F.busca).split(/\s+/).filter(Boolean).every((t) => alvo.includes(t))) return false;
  }
  return true;
}
function botoes(el, itens) {
  const foco = el.contains(document.activeElement) ? document.activeElement.dataset.v : null;
  el.innerHTML = itens.map((x) => `<button type="button" data-v="${esc(x.v)}" aria-pressed="${!!x.on}"${x.cls ? ` class="${x.cls}"` : ''}${x.estilo ? ` style="${x.estilo}"` : ''}>${x.html}</button>`).join('');
  if (foco != null) { const b = [...el.children].find((y) => y.dataset.v === foco); if (b) b.focus(); }
}
function renderFiltros(todos) {
  const F = G.gal[G.rota];
  const cont = { todos: todos.length, prontos: 0, andamento: 0, erros: 0 };
  todos.forEach((j) => { cont[grupoEstado(j)]++; });
  const sigE = JSON.stringify([cont, F.estado]);
  const fe = $('#filtroEstado');
  if (fe._sig !== sigE) {
    fe._sig = sigE;
    botoes(fe, [['todos', 'Todos'], ['prontos', 'Prontos'], ['andamento', 'Na fila / gerando'], ['erros', 'Com erro ou cancelados']]
      .map(([v, r]) => ({ v, html: `${r}<span>${cont[v]}</span>`, on: F.estado === v })));
  }
  const porIA = new Map();
  todos.forEach((j) => {
    if (!porIA.has(j.preset)) porIA.set(j.preset, { n: 0, nome: iaDe(j).curto });
    porIA.get(j.preset).n++;
  });
  if (F.ia && !porIA.has(F.ia)) F.ia = null;
  const fi = $('#filtroIA');
  fi.hidden = porIA.size < 2;
  const itens = [{ v: '', html: `Todas<span>${todos.length}</span>`, on: !F.ia, cls: 'todas' },
    ...[...porIA].sort((a, b) => b[1].n - a[1].n).map(([k, x]) => ({ v: k, html: `${esc(x.nome)} <span>${x.n}</span>`, on: F.ia === k }))];
  const sigI = JSON.stringify(itens);
  if (fi._sig !== sigI) { fi._sig = sigI; botoes(fi, itens); }
}
function renderGaleria() {
  const rota = G.rota, F = G.gal[rota], R = ROTAS[rota], todos = G.jobs[rota] || [];
  renderFiltros(todos);
  const vis = todos.filter((j) => passaFiltro(j, F));
  G.visiveis = vis;
  const mostrar = vis.slice(0, F.mostrar);
  const grade = $('#grade'), ids = new Set(mostrar.map((j) => j.id));
  [...grade.children].forEach((el) => { if (!ids.has(el.dataset.id)) el.remove(); });
  mostrar.forEach((j, i) => { const c = card(j); if (grade.children[i] !== c) grade.insertBefore(c, grade.children[i] || null); });
  const vivos = new Set(todos.map((j) => j.id));
  [...G.cards.keys()].forEach((id) => { if (!vivos.has(id)) G.cards.delete(id); });
  const andando = todos.filter((j) => grupoEstado(j) === 'andamento').length;
  const filtrado = F.ia || F.estado !== 'todos' || F.busca;
  $('#contaCriacoes').textContent = `${todos.length} criaç${todos.length === 1 ? 'ão' : 'ões'}`
    + (filtrado ? ` · ${vis.length} com esses filtros` : '') + (andando ? ` · ${andando} em andamento` : '');
  const vazio = $('#vazio');
  vazio.hidden = vis.length > 0;
  if (!vis.length) {
    vazio.className = 'vazio ' + R.tipo;
    vazio.innerHTML = !G.jobsCarregado[rota] ? '<p>Carregando criações…</p>' : todos.length
      ? `${ic('busca')}<p>Nenhuma criação com esses filtros.</p><p style="margin-top:10px"><button type="button" class="bt-sec" id="limparFiltros">Limpar filtros</button></p>`
      : `${ic(R.icone)}<p>${esc(TX(R.vazio))}</p>`;
  }
  const resta = vis.length - mostrar.length;
  $('#maisBox').hidden = resta <= 0;
  if (resta > 0) $('#carregarMais').textContent = `Carregar mais (${resta} restante${resta > 1 ? 's' : ''})`;
  // criações que o servidor ainda não mandou (as mais antigas): nunca corta em silêncio
  const faltam = G.faltam[rota] || 0, pedir = G.pedir[rota] || PEDIR_PADRAO;
  $('#limiteBox').hidden = !faltam || resta > 0;
  if (faltam === -1) {
    $('#limiteAviso').textContent = 'Esta versão do servidor do estúdio manda só as 120 criações mais recentes desta aba; as mais antigas continuam no HD (pasta output da ComfyUI).';
    $('#carregarAntigas').hidden = true;
  } else if (faltam > 0) {
    const pode = pedir < PEDIR_MAX;
    $('#limiteAviso').textContent = `Faltam carregar ${faltam} criaç${faltam === 1 ? 'ão mais antiga' : 'ões mais antigas'} desta aba.`
      + (pode ? '' : ` O estúdio mostra no máximo ${num(PEDIR_MAX, 0)}; as outras continuam no HD (pasta output da ComfyUI).`);
    $('#carregarAntigas').hidden = !pode;
    $('#carregarAntigas').textContent = `Carregar as mais antigas (${Math.min(faltam, PEDIR_MAX - pedir)})`;
  }
}

const SEM_ARQUIVO = `<div class="espera falhou">${ic('alerta')}<b>Arquivo não encontrado no HD</b><small>Pode ter sido apagado fora do estúdio. Use Remover para tirar da lista.</small></div>`;
const ativoJ = (j) => j.estado === 'fila' || j.estado === 'rodando';
function htmlMidiaCard(j) {
  const selo = `<span class="selo"><span>${esc(seloTexto(j))}</span></span>`;
  if (ativoJ(j)) {
    // % e fase são preenchidos por vivoCard() (só texto: nada é recriado a cada atualização)
    return `<div class="espera gerando"><span class="pct v-pct"></span><small class="fase v-fase-m"></small></div>${selo}`;
  }
  if (j.estado !== 'concluido') {
    return `<div class="espera falhou">${ic(j.estado === 'cancelado' ? 'parar' : 'alerta')}<b>${j.estado === 'cancelado' ? 'Cancelado' : 'Deu erro'}</b></div>${selo}`;
  }
  const saidas = j.saidas || [];
  if (!saidas.length) return `<div class="espera falhou">${ic('alerta')}<b>Terminou sem arquivo</b><small>A ComfyUI não registrou a saída.</small></div>${selo}`;
  if (sumiu(j)) return SEM_ARQUIVO + selo;
  const s = saidas[0], url = urlMidia(j), video = ehVideo(s.arquivo);
  const midia = video ? `<video src="${url}#t=0.1" muted loop playsinline preload="metadata"></video>`
    : `<img src="${url}" alt="${esc(altDe(j))}" loading="lazy" decoding="async">`;
  return `<button type="button" class="midia-bt" data-a="ver" aria-label="Ver ${esc(seloTexto(j))} em tamanho grande">${midia}</button>${selo}`
    + (video ? `<span class="tipo-video">${ic('play')}vídeo</span>` : '')
    + (saidas.length > 1 ? `<span class="n-saidas">${saidas.length} arquivos</span>` : '');
}
function ligarMidia(m, id) {
  const v = m.querySelector('video'), i = m.querySelector('img');
  // a mídia não carregou: se o servidor confirmar 404, o card inteiro vira "arquivo não encontrado" (sem Ver/Baixar)
  const perdido = () => confirmarSumico(id, () => {
    const j = (G.jobs[G.rota] || []).find((x) => x.id === id);
    if (j) card(j);
  });
  if (i) i.addEventListener('error', perdido, { once: true });
  if (v) {
    v.addEventListener('error', perdido, { once: true });
    m.addEventListener('pointerenter', () => { v.play().catch(() => {}); });
    m.addEventListener('pointerleave', () => { v.pause(); });
  }
}
function htmlInfoCard(j) {
  const ft = fichaTec(j);
  const semPrompt = j.modo === 'personagem' ? '(sem prompt — personagem + movimento)' : '(sem prompt)';
  let h = `<p class="prompt${j.prompt ? '' : ' vazio-p'}" title="${esc(j.prompt || '')}">${esc(j.prompt || semPrompt)}</p>`
    + `<p class="ficha" title="${esc(ft)}">${esc(ft)}</p>`;
  if (j.aviso) h += `<p class="aviso-linha" title="${esc(rot(j.aviso))}">${ic('alerta')}<span>${esc(rot(j.aviso))}</span></p>`;
  const reusarBt = podeReusar(j)
    ? `<button type="button" data-a="reusar" title="Carregar estas configurações no formulário">${ic('reusar')}Reusar</button>`
    : `<button type="button" data-a="reusar" aria-disabled="true" title="Essa IA foi removida do estúdio: não dá para reusar">${ic('reusar')}Reusar</button>`;
  const removerBt = (rotulo, dica) => `<button type="button" data-a="remover" class="perigo" title="${dica}">${ic('lixo')}${rotulo}</button>`;
  if (j.estado === 'concluido') {
    const tem = (j.saidas || []).length > 0, foi = tem && sumiu(j);
    h += `<div class="linha">${foi ? '<span class="estado falhou" title="O arquivo do resultado não está mais no HD">Sem arquivo</span>' : '<span class="estado feito">Pronto</span>'}<span>Levou <b>${esc(fmt(decorrido(j)))}</b> · ${esc(quando(j.criado))}</span></div>`;
    h += `<div class="acoes">${tem && !foi ? `<button type="button" data-a="ver">${ic('ver')}Ver</button>
      <a href="${urlMidia(j)}" download="${esc(nomeArquivo(j))}" title="Baixar o arquivo original">${ic('baixar')}Baixar</a>` : ''}${reusarBt}${foi
      ? removerBt('Remover (limpar registro)', 'O arquivo já não está no HD: tira este trabalho da lista (e apaga o que sobrou dele)')
      : removerBt('Remover', 'Apagar do HD')}</div>`;
  } else if (j.estado === 'erro' || j.estado === 'cancelado') {
    const msg = j.estado === 'cancelado' ? 'Cancelado.' : (j.erro || 'Erro sem mensagem.');
    h += `<p class="erro-txt" title="${esc(msg)}">${esc(String(msg).slice(0, 300))}</p>`;
    h += `<div class="linha"><span class="estado falhou">${j.estado === 'erro' ? 'Deu erro' : 'Cancelado'}</span><span>${esc(quando(j.criado))}</span></div>`;
    h += `<div class="acoes">${reusarBt}${removerBt('Remover', 'Apagar do HD')}</div>`;
  } else {
    h += `<div class="linha"><span class="estado andando"><span class="v-est"></span> · <span class="v-pct"></span></span><span class="v-fase"></span></div>
      <div class="barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Progresso"><i></i></div>
      <div class="linha"><span class="v-dec"></span><span class="v-falta"></span></div>
      <div class="acoes"><button type="button" data-a="cancelar" class="perigo">${ic('parar')}Cancelar</button></div>`;
  }
  return h;
}
// parte que muda a cada atualização (%, fase, decorrido, falta): só textContent e largura da barra
function vivoCard(c, j) {
  const g = j.progresso || {}, pct = Math.floor(g.pct || 0);
  const txt = (sel, t) => $$(sel, c).forEach((el) => { if (el.textContent !== t) el.textContent = t; });
  txt('.v-pct', `${pct}%`);
  txt('.v-fase-m', rot(g.fase || (j.estado === 'fila' ? 'Na fila' : 'Gerando')));
  txt('.v-est', j.estado === 'fila' ? 'Na fila' : 'Gerando');
  txt('.v-fase', rot(g.fase || ''));
  txt('.v-dec', `Decorrido ${fmt(g.decorrido)}`);
  txt('.v-falta', (g.restante == null ? 'Falta: calculando…' : 'Falta ~' + fmt(g.restante)) + (g.base && g.restante != null ? ` (${rot(g.base)})` : ''));
  const barra = $('.barra', c);
  if (barra) {
    barra.setAttribute('aria-valuenow', String(pct));
    barra.firstElementChild.style.width = `${Math.min(100, g.pct || 0)}%`;
  }
}
function card(j) {
  let c = G.cards.get(j.id);
  if (!c) {
    c = document.createElement('article');
    c.dataset.id = j.id;
    c.innerHTML = '<div class="midia"></div><div class="info"></div>';
    G.cards.set(j.id, c);
  }
  c.className = 'card ' + tipoDaRota(rotaDoJob(j));
  const ativo = ativoJ(j), m = c.querySelector('.midia'), info = c.querySelector('.info');
  // o HTML só é refeito quando muda a ESTRUTURA (estado, arquivo, aviso…); o progresso não entra aqui
  const sigM = [j.estado, (j.saidas || []).length, seloTexto(j), sumiu(j)].join('|');
  if (m._sig !== sigM) { m._sig = sigM; m.innerHTML = htmlMidiaCard(j); ligarMidia(m, j.id); }
  const sigI = [j.estado, j.aviso, j.erro, j.preset_existe, (j.saidas || []).length, podeReusar(j), sumiu(j), fichaTec(j), j.prompt].join('|');
  if (info._sig !== sigI) {
    // se o foco estava num botão do card, volta para o botão equivalente depois de refazer
    const foco = info.contains(document.activeElement) ? document.activeElement.dataset.a : null;
    info._sig = sigI;
    info.innerHTML = htmlInfoCard(j);
    if (foco) { const b = $(`[data-a="${foco}"]`, info) || $('[data-a]', info); if (b) b.focus({ preventScroll: true }); }
  }
  if (ativo) vivoCard(c, j);
  return c;
}
async function tamanhoSaidas(j) {
  let total = 0;
  for (let i = 0; i < (j.saidas || []).length; i++) {
    try {
      const r = await fetch(urlMidia(j, i), { method: 'HEAD', cache: 'no-store' });
      const n = +r.headers.get('content-length');
      if (r.ok && n) total += n;
    } catch (e) { /* ignora */ }
  }
  return total ? total / 1048576 : null;
}
// ---------------------------------------------------------------- o que o Remover apaga além do resultado
// Mesmas regras do servidor (apagar_trabalho): só arquivos que o PRÓPRIO estúdio criou em ComfyUI\input
// (upload estudio_<hex>, recorte enq_<hex>, fala apres_<id>.wav) e que nenhum outro trabalho usa.
const RE_CRIADO = /^(?:estudio_[0-9a-f]{10}(?:_16fps\.mp4|_voz\.wav|\.[A-Za-z0-9]+)|enq_[0-9a-f]{12}\.(?:png|json))$/;
const raizEntrada = (n) => { const m = /^(estudio_[0-9a-f]{10})/.exec(n); return m ? m[1] : n; };  // o original e o convertido andam juntos
const soNome = (n) => String(n || '').split(/[\\/]/).pop();
function entradasDo(j) {
  const ap = j.preset === 'apresentador' || rotaDoJob(j) === 'apresentador', out = [], vistos = new Set();
  const add = (nome, rotulo) => {
    const n = soNome(nome);
    if (!n || vistos.has(n)) return;
    vistos.add(n);
    out.push({ nome: n, rotulo });
  };
  add(j.imagem, ap ? 'a foto do apresentador que você enviou' : j.modo === 'personagem' ? 'a imagem do personagem que você enviou' : 'a foto que você enviou');
  add(j.video, 'o vídeo de movimento que você enviou');
  add(j.audio, 'o áudio pronto que você enviou');
  add(j.voz, 'o áudio que você enviou para clonar a voz');
  add(j.imagem_enquadrada, 'o recorte do personagem (feito pelo estúdio)');
  (j.imagens || []).forEach((n, i) => add(n, `a imagem de referência ${i + 1} que você enviou`));
  if (ap && j.id) add(`apres_${j.id}.wav`, 'a fala gerada pela IA de voz (Chatterbox) e os trechos dela');
  return out;
}
const criadoPeloEstudio = (n, j) => RE_CRIADO.test(n) || n === `apres_${j.id}.wav`;
async function headEntrada(nome) {
  try {
    const r = await fetch(`/api/entrada/${encodeURIComponent(nome)}`, { method: 'HEAD', cache: 'no-store' });
    if (!r.ok) return null;
    const lm = Date.parse(r.headers.get('last-modified') || '');
    return { bytes: +r.headers.get('content-length') || 0, mtime: isFinite(lm) ? lm / 1000 : null };
  } catch (e) { return null; }
}
// formulários (de qualquer seção) que estão usando um desses arquivos
function formulariosUsando(nomes) {
  const achados = [];
  Object.values(ESTADOS).forEach((est) => {
    const usa = [...Object.values(est.up || {}), ...(est.refs || [])].some((x) => x && nomes.has(soNome(x.nome)));
    if (usa) achados.push(est.rota);
  });
  return achados;
}
async function planoRemover(j) {
  const n = (j.saidas || []).length;
  const mbSaidas = n && !sumiu(j) ? await tamanhoSaidas(j) : null;
  // quem mais usa cada arquivo: lista NOVA de todas as abas (não a guardada da seção)
  let outros = [];
  try {
    const todos = await api('/api/trabalhos?limite=5000', { timeout: 15000 });
    outros = (Array.isArray(todos) ? todos : []).filter((x) => x.id !== j.id);
  } catch (e) { outros = Object.values(G.jobs).flat().filter((x) => x.id !== j.id); }
  const usadas = new Set();
  outros.forEach((x) => entradasDo(x).forEach((e) => usadas.add(raizEntrada(e.nome))));
  (G.vozes || []).forEach((v) => { if (v.arquivo) usadas.add(raizEntrada(soNome(v.arquivo))); });
  const apaga = [], fica = [];
  for (const e of entradasDo(j)) {
    if (!criadoPeloEstudio(e.nome, j)) continue;  // arquivo seu posto na pasta input: o estúdio nunca apaga
    const info = await headEntrada(e.nome);
    if (!info) continue;  // já não está no HD
    if (usadas.has(raizEntrada(e.nome))) { fica.push({ ...e, motivo: 'outra criação também usa' }); continue; }
    if (RE_CRIADO.test(e.nome) && info.mtime && j.criado && info.mtime > +j.criado + 2) {
      fica.push({ ...e, motivo: 'foi enviado de novo depois deste trabalho' });
      continue;
    }
    apaga.push({ ...e, mb: info.bytes / 1048576 });
  }
  return { n, mbSaidas, apaga, fica };
}
const maiuscula = (s) => s.charAt(0).toUpperCase() + s.slice(1);
async function remover(j, bt) {
  if (bt) { bt.disabled = true; bt.setAttribute('aria-busy', 'true'); }
  let plano;
  try { plano = await planoRemover(j); }
  finally { if (bt && document.contains(bt)) { bt.disabled = false; bt.removeAttribute('aria-busy'); } }
  const { n, mbSaidas, apaga, fica } = plano;
  const resultado = !n ? 'o registro deste trabalho'
    : sumiu(j) ? 'o registro deste trabalho (o arquivo do resultado já não está no HD)'
      : `o resultado: ${n} arquivo${n > 1 ? 's' : ''}${mbSaidas != null ? ` (${num(mbSaidas, 1)} MB)` : ''}`;
  const lista = [];
  if (apaga.length) {
    lista.push({ txt: `Também apaga ${apaga.length === 1 ? 'este arquivo, porque nenhuma outra criação usa' : 'estes arquivos, porque nenhuma outra criação usa'}:`, cls: 'titulo' });
    apaga.forEach((e) => lista.push({ txt: `${maiuscula(e.rotulo)} (${e.nome} · ${num(e.mb, 1)} MB)` }));
  }
  fica.forEach((e) => lista.push({ txt: `Fica no HD: ${e.rotulo} (${e.nome}), porque ${e.motivo}.`, cls: 'fica' }));
  const nomesApaga = new Set(apaga.map((e) => e.nome));
  const formularios = formulariosUsando(nomesApaga);
  formularios.forEach((r) => lista.push({ txt: `O formulário de ${TITULOS[r]} está usando um desses arquivos: ele sai do formulário e você vai precisar enviar de novo.`, cls: 'alerta' }));
  const total = (mbSaidas || 0) + apaga.reduce((s, e) => s + e.mb, 0);
  const ok = await confirmar({
    titulo: 'Apagar do HD?',
    texto: `${seloTexto(j)} — apaga ${resultado}.`,
    lista,
    rodape: `${total > 0 ? `Total: cerca de ${num(total, 1)} MB. ` : ''}Não dá para desfazer.`,
    sim: 'Apagar do HD', nao: 'Manter', icone: 'lixo' });
  if (!ok) return;
  const rota = G.rota, card0 = G.cards.get(j.id), prox = card0 && (card0.nextElementSibling || card0.previousElementSibling);
  try {
    const r = await api(`/api/remover/${encodeURIComponent(j.id)}`, { method: 'POST', timeout: 30000 });
    const liberado = r.mb != null ? +r.mb : total || null;
    const nA = +r.apagados || 0;
    aviso(`Removido do HD: ${nA} arquivo${nA === 1 ? '' : 's'}${liberado != null ? `, ${num(liberado, 1)} MB liberados` : ''}.`);
    if (r.aviso) aviso(r.aviso, 'aviso', 9000);
    if ((r.falhas || []).length) aviso(`Não consegui apagar ${r.falhas.length} arquivo(s): ${r.falhas.slice(0, 3).join(', ')}. Feche o que estiver usando e tente de novo.`, 'erro', 9000);
    if (G.jobs[rota]) G.jobs[rota] = G.jobs[rota].filter((x) => x.id !== j.id);
    if ($('#lupa').open) { lupaOrigem = null; fecharLupa(); }
    if (G.rota === rota) renderGaleria();
    // o foco vai para o card vizinho (o botão que foi clicado sumiu junto com o card)
    const alvo = prox && document.contains(prox) ? $('[data-a]', prox) : null;
    if (alvo) alvo.focus({ preventScroll: true }); else if (ehGerador(G.rota)) $('#tituloCriacoes').focus({ preventScroll: true });
    await limparFormularios(nomesApaga);
  } catch (e) { aviso('Não consegui remover: ' + e.message, 'erro'); }
  atualizar(true);
}
// depois de apagar: tira dos formulários o que apontava para arquivo que não existe mais (confere no servidor)
async function limparFormularios(nomes) {
  if (!nomes.size) return;
  const sumidos = new Set();
  for (const n of nomes) if (!(await headEntrada(n))) sumidos.add(n);
  if (!sumidos.size) return;
  const afetadas = [];
  Object.values(ESTADOS).forEach((est) => {
    let mudou = false;
    ['imagem', 'video', 'voz', 'audio'].forEach((k) => {
      if (est.up[k] && sumidos.has(soNome(est.up[k].nome))) { est.up[k] = null; mudou = true; }
    });
    const refs = (est.refs || []).filter((x) => !sumidos.has(soNome(x.nome)));
    if (refs.length !== (est.refs || []).length) { est.refs = refs; mudou = true; }
    if (mudou) { est.enq = { chave: null, res: null }; afetadas.push(est.rota); }
  });
  if (!afetadas.length) return;
  if (E && afetadas.includes(E.rota) && G.rota === E.rota) { renderUploads(); renderForm(); }
  aviso(`${afetadas.map((r) => `O formulário de ${TITULOS[r]}`).join(' e ')} usava um arquivo desse trabalho, que foi apagado: envie de novo.`, 'aviso', 9000);
}
async function cancelar(j) {
  const g = j.progresso || {};
  const ok = await confirmar({
    titulo: 'Cancelar esta geração?',
    texto: j.estado === 'rodando' ? `Já foram ${fmt(g.decorrido)} de geração em ${seloTexto(j)}, e esse trabalho se perde.`
      : `${seloTexto(j)} ainda está na fila; nada foi gerado ainda.`,
    sim: 'Cancelar geração', nao: 'Continuar gerando', icone: 'parar' });
  if (!ok) return;
  try {
    const r = await api(`/api/cancelar/${encodeURIComponent(j.id)}`, { method: 'POST', timeout: 20000 });
    if (r && r.aviso) aviso(rot(r.aviso), 'aviso', 9000);  // ex.: "A ComfyUI não respondeu; o trabalho foi marcado como cancelado aqui."
    else aviso('Geração cancelada.');
  } catch (e) { aviso('Não consegui cancelar: ' + e.message, 'erro'); }
  await atualizar(true);
  // o botão Cancelar sumiu com a troca de estado: o foco vai para o próprio card (Reusar/Remover)
  const a = document.activeElement;
  if (!a || a === document.body || !document.contains(a)) {
    const c = G.cards.get(j.id), b = c && document.contains(c) ? $('[data-a]', c) : null;
    if (b) b.focus({ preventScroll: true });
  }
}

// ================================================================ VISUALIZADOR
let lupaOrigem = null;
function abrirLupa(lista, idx) {
  if (!lista.length || idx < 0) return;
  G.lupa = { lista, idx, saida: 0 };
  mostrarLupa();
  const d = $('#lupa');
  if (!d.open) { lupaOrigem = document.activeElement; d.showModal(); d.scrollTop = 0; $('#lupaFechar').focus({ preventScroll: true }); }
}
function fecharLupa() {
  const d = $('#lupa');
  if (d.open) d.close();
  $('#lupaMidia').innerHTML = '';  // para o vídeo/áudio
  const o = lupaOrigem;
  lupaOrigem = null;
  if (o && document.contains(o) && o.focus) o.focus({ preventScroll: true });
}
function rotuloBaixar(w, h) {
  $('#lupaBaixarTxt').textContent = `Baixar no tamanho original${w && h ? ` (${w}×${h})` : ''}`;
}
function mostrarLupa() {
  const L = G.lupa, j = L.lista[L.idx];
  if (!j) return;
  const ia = iaDe(j), rota = rotaDoJob(j), saidas = j.saidas || [];
  const i = Math.min(L.saida || 0, Math.max(0, saidas.length - 1)), s = saidas[i];
  $('#lupa').className = 'lupa ' + tipoDaRota(rota);
  $('#lupaSelo').innerHTML = `<span>${esc(seloTexto(j))}</span>`;
  $('#lupaPos').textContent = L.lista.length > 1 ? `${L.idx + 1} de ${L.lista.length}` : '';
  $('#lupaTitulo').textContent = ia.nome;
  $('#lupaSub').textContent = [ia.motor && `Motor: ${ia.motor}`, ia.voz && `Voz: ${ia.voz}`].filter(Boolean).join(' · ');
  const ap = rota === 'apresentador';
  const dados = [['Levou', fmt(decorrido(j))], ['Passos', j.steps], ['Tamanho', j.tamanho ? `${j.tamanho[0]}×${j.tamanho[1]}` : null],
    ['Fala', ap && j.segundos_audio ? seg(j.segundos_audio) : null], ['Idioma', ap ? j.idioma : null],
    ['Resumo', ia.resumo], ['Criado', dataHora(j.criado)], ['Semente', j.seed]];
  $('#lupaDados').innerHTML = dados.filter(([, v]) => v != null && v !== '' && v !== '—')
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  $('#lupaAviso').hidden = !j.aviso;
  if (j.aviso) $('#lupaAviso').innerHTML = `${ic('alerta')}<span>${esc(rot(j.aviso))}</span>`;
  $('#lupaPrompt').textContent = j.prompt || '(sem prompt)';
  $('#lupaFicha').textContent = fichaTec(j);
  const sb = $('#lupaSaidas');
  sb.hidden = saidas.length < 2;
  sb.innerHTML = saidas.length < 2 ? '' : saidas.map((x, k) => `<button type="button" class="bt-sec" data-saida="${k}" aria-pressed="${k === i}">${k === 0 ? 'Arquivo final' : `Arquivo ${k + 1}`}</button>`).join('');
  const box = $('#lupaMidia'), url = urlMidia(j, i);
  if (!s) box.innerHTML = `<div class="espera falhou">${ic('alerta')}<b>Sem arquivo</b></div>`;
  else if (ehVideo(s.arquivo)) box.innerHTML = `<video src="${url}" controls autoplay playsinline></video>`;
  else if (ehAudio(s.arquivo)) box.innerHTML = `<audio src="${url}" controls autoplay></audio>`;
  else box.innerHTML = `<img src="${url}" alt="${esc(altDe(j))}">`;
  const m = box.firstElementChild;
  if (m && m.tagName !== 'DIV') {
    m.addEventListener('error', () => {
      // sem arquivo: nada de "Baixar" apontando para um 404
      box.innerHTML = `<div class="espera falhou">${ic('alerta')}<b>Arquivo não encontrado no HD</b></div>`;
      $('#lupaBaixar').hidden = true;
      $('#lupaAbrir').hidden = true;
      if (i === 0) confirmarSumico(j.id, () => { const c = G.cards.get(j.id); if (c && document.contains(c)) card(j); });
    }, { once: true });
    m.addEventListener(m.tagName === 'IMG' ? 'load' : 'loadedmetadata', () => {
      const w = m.naturalWidth || m.videoWidth, h = m.naturalHeight || m.videoHeight;
      if (w && h) rotuloBaixar(w, h);
    }, { once: true });
  }
  const bx = $('#lupaBaixar');
  bx.hidden = !s;
  bx.href = url;
  bx.setAttribute('download', nomeArquivo(j, i));
  rotuloBaixar(i === 0 && j.tamanho ? j.tamanho[0] : null, i === 0 && j.tamanho ? j.tamanho[1] : null);
  $('#lupaAbrir').href = url;
  $('#lupaAbrir').hidden = !s;
  const pode = podeReusar(j), rb = $('#lupaReusar');
  rb.setAttribute('aria-disabled', String(!pode));
  rb.title = pode ? 'Carregar estas configurações no formulário' : 'Essa IA foi removida do estúdio: não dá para reusar';
  $('#lupaAnt').disabled = L.idx <= 0;
  $('#lupaProx').disabled = L.idx >= L.lista.length - 1;
}
function navLupa(d) {
  const L = G.lupa, n = L.idx + d;
  if (n < 0 || n >= L.lista.length) return;
  L.idx = n; L.saida = 0;
  mostrarLupa();
}
function verNaGaleria(j) {
  const lista = (G.visiveis || []).filter(prontoComArquivo);
  abrirLupa(lista, lista.findIndex((x) => x.id === j.id));
}

// ================================================================ MÚSICA
function musicaLigada() {
  if (G.rota === 'inicio' && G.inicio) { const sv = (G.inicio.sistema || {}).servicos || {}; return sv.painel_musica == null ? null : !!sv.painel_musica; }
  return G.sistema ? !!G.sistema.musica : null;
}
// O painel de música NÃO guarda rascunho: recarregar o iframe apaga a letra/estilo que o dono está digitando.
// Por isso: (1) só conclui "desligado" depois de 3 checagens seguidas sem resposta (~15 s); numa falha isolada
// (PC paginando, modelo carregando) o painel continua na tela com uma faixa discreta; (2) depois que o iframe
// carregou uma vez, o src NUNCA é trocado: escondido ou não, a página dele continua viva e volta a funcionar
// sozinha quando o painel responder de novo.
const MUS_FALHAS_DESLIGADO = 3;
// O cartão do meio da aba Música. Devolve true quando FALTA alguma coisa para a música existir nesta máquina
// (aí o painel não é mostrado); com tudo no lugar, deixa o cartão no texto de "painel desligado" e devolve false.
function cartaoMusica(em, on) {
  const tit = $('#musicaOffTitulo'), txt = $('#musicaOffTexto'), bt = $('#ligarMusica'), ir = $('#musicaIrInicio'), nota = $('#musicaOffNota');
  const falta = em ? em.falta : null;
  const lista = ((em && em.ias) || []).map((i) => `${i.nome}${i.gb_falta ? ` (${num(i.gb_falta, 1)} GB)` : ''}`).join(TX(' ou '));
  let titulo = T('tela.o-painel-de-musica-esta', 'O painel de música está desligado');
  let texto = T('tela.ele-gera-musicas-com-letra', 'Ele gera músicas com letra cantada e trilhas instrumentais (YuE2 e Stable Audio 3), na mesma ComfyUI da imagem e do vídeo. Ligar leva uns 30 segundos.');
  let rotulo = '';
  if (falta === 'motor') {
    titulo = TX('Falta instalar o motor');
    texto = TX('A música usa o mesmo motor da imagem e do vídeo (a ComfyUI), e ele ainda não está instalado neste computador. Instale o motor pelo Início e volte aqui.');
    rotulo = TX('Ir para o Início e instalar o motor');
  } else if (falta === 'modelo') {
    titulo = TX('Falta baixar uma IA de música');
    texto = TX('Nenhuma IA de música foi baixada ainda. Baixe pelo Início, na lista de IAs aprovadas pelo projeto:') + ' ' + lista + '.';
    rotulo = TX('Ir para o Início e baixar');
  } else if (falta === 'painel') {
    titulo = TX('O painel de música não veio nesta instalação');
    texto = TX('Falta a pasta painel_musica do pacote. Baixe o pacote de novo (ou atualize) para ter a aba Música.');
  }
  tit.textContent = titulo; txt.textContent = texto;
  bt.hidden = !!falta;
  ir.hidden = !rotulo; if (rotulo) ir.querySelector('span:last-child').textContent = rotulo;
  // avisos que não impedem de abrir: o nó da música não foi copiado, ou a ComfyUI ligada ainda não o carregou
  let aviso2 = '';
  if (em && em.no_ok === false) aviso2 = TX('Atenção: não consegui copiar o complemento da música para a ComfyUI. O YuE2 pode falhar.') + (em.no_erro ? ' (' + em.no_erro + ')' : '');
  else if (em && em.reiniciar_comfy) aviso2 = TX('A ComfyUI ligada ainda não carregou o complemento da música. Desligue e ligue "Imagem e vídeo (ComfyUI)" no Início antes de gerar com o YuE2.');
  nota.textContent = aviso2; nota.hidden = !aviso2;
  G.mus.aviso = !falta && on === true ? aviso2 : '';  // com o painel na tela, o aviso vai na faixa de cima
  return !!falta;
}
async function atualizarMusica(forcar) {
  let on = forcar ? null : musicaLigada();
  if (on == null) {
    // estúdio sem resposta = não dá para saber da música: não conta como falha do painel
    try { G.sistema = await api('/api/sistema', { timeout: 9000 }); on = !!G.sistema.musica; } catch (e) { on = null; }
  }
  if (G.rota !== 'musica') return;
  const M = G.mus, fr = $('#musicaFrame'), faixa = $('#musicaFaixa');
  if (on === true) M.falhas = 0;
  else if (on === false) M.falhas++;
  const temSrc = !!fr.getAttribute('src');
  // Falta o motor ou não há nenhuma IA de música baixada: a aba EXPLICA o que falta e leva ao lugar de resolver.
  // (Antes de 14/11/2026 a aba simplesmente não existia no pacote.) Com o que falta resolvido, segue o fluxo normal.
  const falta = cartaoMusica(musicaEstado(), on);
  if (on === true && !temSrc && !falta) fr.src = musicaUrl();  // 1ª carga
  const desligado = on === false && (!M.carregou || M.falhas >= MUS_FALHAS_DESLIGADO);
  if (desligado && !M.carregou && temSrc) fr.removeAttribute('src');  // nunca carregou: não há nada a perder
  $('#musicaOff').hidden = !(desligado || falta);
  fr.hidden = desligado || falta || !fr.getAttribute('src');
  let msg = '';
  if (!desligado && on === false) msg = 'O painel de música não respondeu agora há pouco. Continua na tela; tentando de novo…';
  else if (on === null && M.carregou) msg = 'Sem resposta do estúdio agora; o painel de música continua na tela.';
  else if (on === null && !fr.getAttribute('src')) msg = 'Verificando o painel de música…';
  else if (M.aviso) msg = M.aviso;
  faixa.textContent = msg;
  faixa.hidden = !msg;
}

// ================================================================ eventos
function prepararEventos() {
  $('#gerar').onclick = gerar;
  $('#forca').oninput = (e) => { $('#forcaVal').textContent = num(+e.target.value, 2); };
  $('#prompt').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); gerar(); } });
  $('#prompt').addEventListener('input', () => { if (E && presetAtual() && presetAtual().tipo === 'apresentador') estimarLogo(700); });
  $('#ligarMusica').onclick = (e) => ligarMusica(e.currentTarget);
  // "Falta o motor" / "falta baixar uma IA": leva ao Início, na lista de onde se instala
  $('#musicaIrInicio').onclick = () => {
    location.hash = '#/';
    setTimeout(() => { const el = $('#aprovTitulo'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 400);
  };
  $('#dicaOutra').onclick = proximaDica;
  if ($('#novVerTodas')) $('#novVerTodas').onclick = () => { G.novTodas = !G.novTodas; renderNovidades(); };
  // Início: "Ligar" dos serviços (linhas da máquina, "Ligar tudo" e o aviso de cada cartão)
  $('#vInicio').addEventListener('click', (e) => {
    const rep = e.target.closest('#btReparar');
    if (rep && !rep.disabled) { e.preventDefault(); repararEstudio(rep); return; }
    const d = e.target.closest('[data-desligar]');
    if (d && !d.disabled) { e.preventDefault(); desligarServico(d.dataset.desligar, d); return; }
    const b = e.target.closest('[data-ligar]');
    if (!b || b.disabled) return;
    e.preventDefault();
    ligarServico(b.dataset.ligar, b);
  });
  setInterval(tiquetaque, 1000);
  resultadoDoReparo();
  setInterval(() => { if (G.rota === 'inicio' && !document.hidden) proximaDica(); }, 15000);
  $('#maqMini').addEventListener('click', (e) => {
    // gerando: leva para a aba onde o trabalho esta (antes ia sempre para o Inicio)
    if (G.rotaGerando && G.rotaGerando !== G.rota) { e.preventDefault(); location.hash = '#/' + G.rotaGerando; return; }
    if (G.rota === 'inicio') { e.preventDefault(); $('#maquina').scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
  // copia o bloco que ensina a IA de codigo a falar com o estudio (bloco do Inicio, 02/11/2026)
  const btAtalho = $('#atalhoCopiar');
  if (btAtalho) {
    btAtalho.addEventListener('click', async () => {
      const txt = ($('#atalhoTexto') || {}).textContent || '';
      try {
        await navigator.clipboard.writeText(txt);
        aviso('Bloco copiado. Cole na conversa com a IA de código.', 'ok');
      } catch (e) {
        // sem permissão de área de transferência: seleciona para a pessoa copiar na mão
        const r = document.createRange();
        r.selectNodeContents($('#atalhoTexto'));
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        aviso('Não consegui copiar sozinho — o bloco está selecionado, use Ctrl+C.', 'aviso');
      }
    });
  }
  // "Pular para o conteúdo": vai para o título da tela aberta SEM mexer no endereço (#conteudo não é uma rota)
  $('#pular').addEventListener('click', (e) => { e.preventDefault(); focarTitulo(true); });
  // o painel de música carregou de verdade uma vez: a partir daqui o iframe nunca é recarregado sozinho
  $('#musicaFrame').addEventListener('load', (e) => { if (e.currentTarget.getAttribute('src')) G.mus.carregou = true; });
  // o cabeçalho muda de altura com a largura da tela (no celular ele quebra em 2 linhas): a Música acompanha
  if (window.ResizeObserver) new ResizeObserver(() => { if (G.rota === 'musica') medirTopo(); }).observe($('.topo'));
  else window.addEventListener('resize', () => { if (G.rota === 'musica') medirTopo(); });
  $('#carregarAntigas').onclick = () => {
    const r = G.rota;
    G.pedir[r] = Math.min(PEDIR_MAX, (G.pedir[r] || PEDIR_PADRAO) + PEDIR_PADRAO);
    G.gal[r].mostrar += POR_PAGINA;  // já mostra a 1ª leva das mais antigas
    $('#carregarAntigas').disabled = true;
    atualizar(true).finally(() => { $('#carregarAntigas').disabled = false; });
  };

  // seletor de IA
  $('#secIA').addEventListener('click', (e) => {
    const esc_ = e.target.closest('[data-escolher]'), saiba = e.target.closest('[data-saiba]'), troca = e.target.closest('#btTrocarIA');
    const inst = e.target.closest('[data-instalar]'), rem = e.target.closest('[data-remover]');
    if (inst) { instalarIA(inst.dataset.instalar); return; }
    if (rem) { removerIA(rem.dataset.remover); return; }
    if (esc_) escolherIA(esc_.dataset.escolher);
    else if (saiba) abrirFicha(fichaOuPreset(acharPreset(saiba.dataset.saiba)));
    else if (troca) {
      E.trocando = !E.trocando;
      renderIAs();
      const b = $('#btTrocarIA');
      if (b) b.focus();
      if (E.trocando) $('#buscaIA').focus();
    }
  });
  let buscaT;
  $('#buscaIA').addEventListener('input', () => { clearTimeout(buscaT); buscaT = setTimeout(renderListaIA, 120); });

  // galeria
  $('#grade').addEventListener('click', (e) => {
    const alvo = e.target.closest('[data-a]');
    if (!alvo) return;
    const c = alvo.closest('.card'), j = c && (G.jobs[G.rota] || []).find((x) => x.id === c.dataset.id);
    if (!j) return;
    const a = alvo.dataset.a;
    if (a === 'ver') verNaGaleria(j);
    else if (a === 'reusar') reusar(j);
    else if (a === 'remover') remover(j, alvo);
    else if (a === 'cancelar') cancelar(j);
  });
  $('#filtroEstado').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-v]');
    if (!b) return;
    const F = G.gal[G.rota];
    F.estado = b.dataset.v; F.mostrar = POR_PAGINA;
    renderGaleria();
  });
  $('#filtroIA').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-v]');
    if (!b) return;
    const F = G.gal[G.rota];
    F.ia = b.dataset.v || null; F.mostrar = POR_PAGINA;
    renderGaleria();
  });
  let buscaCriT;
  $('#buscaCri').addEventListener('input', (e) => {
    clearTimeout(buscaCriT);
    buscaCriT = setTimeout(() => { const F = G.gal[G.rota]; F.busca = e.target.value.trim(); F.mostrar = POR_PAGINA; renderGaleria(); }, 150);
  });
  $('#vazio').addEventListener('click', (e) => {
    if (!e.target.closest('#limparFiltros')) return;
    G.gal[G.rota] = filtroNovo();
    $('#buscaCri').value = '';
    renderGaleria();
  });
  $('#carregarMais').onclick = () => { G.gal[G.rota].mostrar += POR_PAGINA; renderGaleria(); };

  // início
  $('#recentes').addEventListener('click', (e) => {
    const t = e.target.closest('[data-tocar]');
    if (t) { e.preventDefault(); tocar(+t.dataset.tocar); return; }
    const l = e.target.closest('[data-lupa]');
    if (l) abrirLupa(G.listaRecentes, +l.dataset.lupa);
  });
  $('#catalogo').addEventListener('click', (e) => {
    const b = e.target.closest('[data-ficha]');
    if (b) abrirFicha(G.fichas[b.dataset.ficha] || fichaOuPreset(acharPreset(b.dataset.ficha)));
  });

  // janelas
  const dlgF = $('#dlgFicha');
  dlgF.addEventListener('click', (e) => {
    if (e.target === dlgF || e.target.closest('[data-fechar]')) { fecharFicha(); return; }
    const u = e.target.closest('[data-usar]');
    if (u) usarIA(u.dataset.usar, u.dataset.rota);
  });
  dlgF.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); fecharFicha(); } });
  const lupa = $('#lupa');
  $('#lupaFechar').onclick = fecharLupa;
  $('#lupaAnt').onclick = () => navLupa(-1);
  $('#lupaProx').onclick = () => navLupa(1);
  lupa.addEventListener('click', (e) => {
    if (e.target === lupa || e.target === $('#lupaMidia')) { fecharLupa(); return; }
    const s = e.target.closest('[data-saida]');
    if (s) { G.lupa.saida = +s.dataset.saida; mostrarLupa(); }
  });
  lupa.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { e.preventDefault(); fecharLupa(); return; }
    if (e.target.matches('input, textarea, video, audio')) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); navLupa(-1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); navLupa(1); }
  });
  lupa.addEventListener('close', () => { if (!lupa.open) $('#lupaMidia').innerHTML = ''; });
  $('#lupaCopiar').onclick = async () => {
    const j = G.lupa.lista[G.lupa.idx];
    try { await navigator.clipboard.writeText((j && j.prompt) || ''); aviso('Prompt copiado.'); }
    catch (e) { aviso('Não consegui copiar (o navegador bloqueou). Selecione o texto e use Ctrl+C.', 'aviso'); }
  };
  $('#lupaReusar').onclick = () => { const j = G.lupa.lista[G.lupa.idx]; if (j) reusar(j); };

  window.addEventListener('hashchange', irPara);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    pulso();
    if (ehGerador(G.rota)) atualizar();
  });
}

// ================================================================ início do app
async function carregarPresets() {
  for (;;) {
    try { return await api('/api/presets', { timeout: 15000 }); }
    catch (e) {
      $('#maqTxt').textContent = 'Estúdio sem resposta — tentando de novo…';
      $('#maqPonto').className = 'ponto off';
      await new Promise((r) => setTimeout(r, 4000));
    }
  }
}
// Aba sem nenhuma IA instalada nao pode ficar no menu: quem clica cai numa tela que acusa
// erro e parece defeito do programa. Acontece no pacote do GitHub, que leva a tela do
// Plano-sequencia mas nao leva a IA dele (02/11/2026).
function esconderAbasSemIA() {
  [['plano', () => presetsDa('plano').length], ['apresentador', () => presetsDa('apresentador').length]]
    .forEach(([rota, tem]) => {
      const link = $(`#nav a[data-rota="${rota}"]`);
      if (!link) return;
      const vazia = !tem();
      link.hidden = vazia;
      if (vazia && G.rota === rota) location.hash = '#/';
    });
}
(async function iniciar() {
  pintarIcones();
  $('#marcaIc').innerHTML = ic('marca');
  montarMaquina();
  prepararEventos();
  prepararUploads();
  prepararVozes();
  try { prepararNuvem11(); } catch (e) { /* a caixa da nuvem nao pode derrubar a tela */ }
  prepararTexto();
  // o Início aparece NA HORA (cartões, máquina, últimas criações), mesmo com o servidor lento ou sem resposta:
  // a lista de IAs chega depois e completa os cartões (as outras seções esperam por ela)
  if (rotaDoHash() === 'inicio') irPara();
  const p = await carregarPresets();
  p.imagem = p.imagem || [];
  p.video = p.video || [];
  G.presets = p;
  if (p.recomendada) Object.assign(RECOMENDADA, p.recomendada);
  aplicarTemMusica();
  esconderAbasSemIA();
  await Promise.all([carregarFichas(), carregarVozes(), carregarNovidades()]);
  lerIAs();   // quais IAs estao no disco e quanto falta baixar (nao segura a tela)
  lerDestino();   // em que disco elas ficam, e quanto ha livre em cada um
  lerRequisitos();   // o que esta maquina ainda precisa para funcionar inteira
  // (o cabeçalho continua "verificando…" até o 1º pulso completo: sem a fila do estúdio ele poderia dizer "Livre" à toa)
  try { G.sistema = await api('/api/sistema', { timeout: 9000 }); } catch (e) { /* o pulso tenta de novo */ }
  if (G.rota === 'inicio' && rotaDoHash() === 'inicio' && !G.irDepois) {
    renderHeroi();
    renderEscolhas(true);
    renderCatalogo();
    if (G.dicaIdx == null) proximaDica();
  } else {
    G.irDepois = false;
    irPara();
  }
})();
