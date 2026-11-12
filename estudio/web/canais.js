/* Canais — vários canais isolados, do briefing ao vídeo, agendamento e análise.

   Tudo desta tela vive em /api/canais/*. Nenhuma rota daqui grava no histórico do
   estúdio: as produções ficam dentro da pasta do canal e os trabalhos de imagem que a
   esteira dispara vão marcados como ocultos. É a camada de automação separada da tela
   antiga de Canal, que continua funcionando igual.

   Sem biblioteca e sem internet. As cores dos gráficos são as validadas para o fundo
   do painel (#161a23): azul para views, laranja para receita, água para o melhor horário. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...(r || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ic = (n) => (window.ic ? window.ic(n) : '');
  const nf = new Intl.NumberFormat('pt-BR');
  const nf1 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const money = (v) => 'R$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pct = (v) => nf1.format(Number(v || 0) * 100) + '%';
  const hora = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '';
  const dataHora = (ts) => ts ? new Date(ts * 1000).toLocaleString('pt-BR',
    { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
  const dtInput = (ts) => {
    const d = ts ? new Date(ts * 1000) : new Date(Date.now() + 3600e3);
    const z = (n) => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()) + 'T' + z(d.getHours()) + ':' + z(d.getMinutes());
  };
  const linhas = (s) => String(s || '').split(/\n+/).map((x) => x.trim()).filter(Boolean);
  const tags = (s) => String(s || '').split(/[\s,]+/).map((x) => x.trim()).filter(Boolean)
    .map((x) => (x.startsWith('#') ? x : '#' + x));
  const METAS = { preparando: 'Preparando', voz: 'Gerando voz', imagens: 'Gerando imagens', montagem: 'Montando',
    aguardando_aprovacao: 'Aguardando aprovação', aprovado: 'Aprovado', rejeitado: 'Rejeitado',
    concluido: 'Pronto', erro: 'Erro', cancelado: 'Cancelado' };
  const Cores = { youtube: '#3987e5', tiktok: '#d95926', instagram: '#199e70', facebook: '#6250d6' };
  const Rotulo = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram', facebook: 'Facebook' };
  const ABAS = [['visao', 'Visão geral'], ['ajustes', 'Ajustes'], ['agenda', 'Agenda'], ['analise', 'Análise'], ['produzir', 'Produzir']];
  const HORAS = ['06:00', '08:00', '09:00', '11:00', '12:00', '15:00', '18:00', '19:00', '20:00', '21:00'];
  const CATEGORIAS_YT = [
    ['1', 'Filmes e animação'], ['2', 'Automóveis'], ['10', 'Música'], ['15', 'Animais'],
    ['17', 'Esportes'], ['19', 'Viagens'], ['20', 'Games'], ['22', 'Pessoas e blogs'],
    ['23', 'Comédia'], ['24', 'Entretenimento'], ['25', 'Notícias'], ['26', 'Como fazer e estilo'],
    ['27', 'Educação'], ['28', 'Ciência e tecnologia'], ['29', 'Causas sociais'],
  ];

  function modelosImagem() {
    const lista = ((S.presets && S.presets.imagem) || []).filter((p) => p && p.id);
    if (!lista.length) {
      return [{ id: 'z_image_turbo', nome: 'Z-Image Turbo' }, { id: 'krea2', nome: 'Krea 2 Turbo' },
        { id: 'qwen_image_2512', nome: 'Qwen-Image 2512' }, { id: 'flux2_dev', nome: 'FLUX.2 dev' },
        { id: 'ideogram4', nome: 'Ideogram 4' }];
    }
    return lista.filter((p) => !['krea2_img2img', 'h3_imagem'].includes(p.id));
  }

  function opcoesSelect(valores, atual) {
    const lista = valores.map(String);
    if (atual != null && atual !== '' && !lista.includes(String(atual))) lista.unshift(String(atual));
    return lista.map((v) => `<option value="${esc(v)}" ${String(v) === String(atual) ? 'selected' : ''}>${esc(v)}</option>`).join('');
  }

  function estilosDisponiveis() {
    return (S.estilos && S.estilos.length) ? S.estilos : [
      { id: 'auto', nome: 'Automático' }, { id: 'papel', nome: 'Papel' }, { id: 'lapis', nome: 'Lápis' },
      { id: 'pixel', nome: 'Pixel' }, { id: 'pincel', nome: 'Pincel' }, { id: 'palavra', nome: 'Palavra animada' },
      { id: '3d', nome: '3D' }, { id: 'e_se', nome: 'E se...' }, { id: 'novelinha', nome: 'Novelinha' },
    ];
  }

  function botaoIA(campo, rotulo = 'Melhorar') {
    return `<button type="button" class="cx-ia" data-acao="ia-campo" data-campo="${esc(campo)}"
      title="Usar a IA local para melhorar este campo">${ic('brilho')}${esc(rotulo)}</button>`;
  }

  const S = {
    iniciado: false, canais: [], atual: null, dados: null, aba: 'visao',
    plano: null, briefing: '', producao: null, poll: null, analise: null,
    analiseDias: 30, analiseCarregada: false, vozes: null, presets: null, charts: {}, erros: 0,
    personagensNovos: [], agendarAgora: false, abaFixa: false, estilos: [],
  };

  async function pedir(url, corpo, metodo) {
    const op = corpo === undefined && !metodo ? { method: 'GET' }
      : { method: metodo || 'POST', headers: { 'Content-Type': 'application/json' },
          body: corpo === undefined ? undefined : JSON.stringify(corpo) };
    const r = await fetch(url, op);
    const txt = await r.text();
    if (!r.ok) throw new Error((txt || ('Erro ' + r.status)).slice(0, 500));
    try { return JSON.parse(txt); } catch (e) { return {}; }
  }

  function mostrar(msg, tipo) {
    const el = $('#canaisErro');
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || '';
    el.className = 'aviso-linha' + (tipo ? ' ' + tipo : '');
    clearTimeout(S._aviso);
    if (msg) S._aviso = setTimeout(() => { el.hidden = true; }, 6000);
  }

  // ================================================================ carregar
  async function abrir() {
    montar();
    const sub = (location.hash.replace(/^#\/?/, '').split('/')[1] || '').trim();
    if (ABAS.some(([k]) => k === sub)) { S.aba = sub; S.abaFixa = true; }
    if (!S.presets) carregarPresets();
    if (!S.canais.length) await carregarCanais();
    else if (S.atual) { await carregarCanal(false); render(); }
    else render();
    if (!S.abaFixa && S.dados) {
      S.aba = (S.dados.contexto && S.dados.contexto.tema) ? 'visao' : 'ajustes';
      S.abaFixa = true;
      render();
    }
    if (S.aba === 'analise') { S.analiseCarregada = false; await carregarAnalise(true); }
  }

  async function carregarPresets() {
    if (S.presets) return;
    try {
      S.presets = await pedir('/api/presets');
      if (S.aba === 'ajustes') render();
    } catch (e) { S.presets = { imagem: [] }; }
  }

  async function carregarCanais() {
    try {
      const d = await pedir('/api/canais');
      S.canais = d.canais || [];
      S.estilos = d.estilos || S.estilos;
      S.plataformas = d.plataformas || {};
      if (!S.atual || !S.canais.some((c) => c.id === S.atual)) {
        let guardado = null;
        try { guardado = localStorage.getItem('forja_canal_atual'); } catch (e) { /* sem armazenamento */ }
        S.atual = (S.canais.find((c) => c.id === guardado) || S.canais[0] || {}).id || null;
      }
      if (S.atual) await carregarCanal(false);
      render();
    } catch (e) {
      mostrar('Não consegui carregar os canais: ' + e.message, 'erro');
      render();
    }
  }

  async function carregarCanal(mostrarErro = true) {
    if (!S.atual) { S.dados = null; return; }
    try {
      S.dados = await pedir('/api/canais/' + encodeURIComponent(S.atual));
      S.analiseCarregada = false;
      carregarAnalise(false);
      carregarVozes();
      if (mostrarErro) mostrar('');
    } catch (e) {
      if (mostrarErro) mostrar('Não consegui abrir o canal: ' + e.message, 'erro');
      S.dados = null;
    }
  }

  async function carregarAnalise(renderizar = true) {
    if (!S.atual || S.analiseCarregada) return;
    S.analiseCarregada = true;
    try {
      S.analise = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/analytics?dias=' + S.analiseDias);
      if (renderizar || S.aba === 'analise' || S.aba === 'visao') render();
    } catch (e) {
      S.analise = null;
      if (renderizar && S.aba === 'analise') mostrar('Não consegui ler a análise: ' + e.message, 'erro');
    }
  }

  async function carregarVozes() {
    if (S.vozes) return;
    try {
      const d = await pedir('/api/voz/estado');
      S.vozes = d.vozes || [];
      if (S.aba === 'ajustes') render();
    } catch (e) { S.vozes = []; }
  }

  async function selecionar(id) {
    if (id === S.atual) return;
    S.atual = id;
    try { localStorage.setItem('forja_canal_atual', id); } catch (e) { /* sem armazenamento */ }
    S.plano = null; S.producao = null; S.analise = null; S.inspiracao = null;
    pararPoll();
    await carregarCanal();
    render();
  }

  // ================================================================ render
  function render() {
    if (!S.iniciado) montar();
    renderSeletor();
    renderAbas();
    renderCorpo();
    posRender();
  }

  function renderSeletor() {
    const el = $('#canaisSeletor');
    if (!el) return;
    if (!S.canais.length) { el.innerHTML = ''; return; }
    el.innerHTML = S.canais.map((c) => {
      const n = ((c.producoes || []).length) || c._producoes || 0;
      return `<button type="button" data-canal="${esc(c.id)}" aria-selected="${c.id === S.atual}"
        style="--i:${esc(c.cor || '#5B8DEF')}"><span class="cx-ponto"></span>
        <span>${esc(c.nome)}</span><span class="cx-n">${n}</span></button>`;
    }).join('') + '<button type="button" class="cx-add" data-acao="novo-canal">' +
      ic('mais') + 'Novo</button>';
  }

  function renderAbas() {
    const el = $('#canaisAbas');
    if (!el) return;
    if (!S.dados) { el.innerHTML = ''; return; }
    el.innerHTML = ABAS.map(([k, t]) =>
      `<button type="button" role="tab" data-aba="${k}" aria-selected="${S.aba === k}">${esc(t)}</button>`).join('');
  }

  function renderCorpo() {
    const el = $('#canaisCorpo');
    if (!el) return;
    if (!S.canais.length) {
      el.innerHTML = `<div class="cx-vazio"><b>Nenhum canal ainda</b>
        Crie o primeiro canal. Cada um guarda o próprio tema, personagens, voz, formatos e agenda.
        <div class="cx-acoes" style="justify-content:center"><button type="button" class="gerar" data-acao="novo-canal">
        ${ic('mais')}Criar o primeiro canal</button></div></div>`;
      return;
    }
    if (!S.dados) { el.innerHTML = '<p class="fraco">Carregando o canal…</p>'; return; }
    if (S.aba === 'visao') el.innerHTML = telaVisao();
    else if (S.aba === 'produzir') el.innerHTML = telaProduzir();
    else if (S.aba === 'agenda') el.innerHTML = telaAgenda();
    else if (S.aba === 'analise') el.innerHTML = telaAnalise();
    else el.innerHTML = telaAjustes();
  }

  function seloEstado(e) {
    const mapa = { concluido: 'ok', aprovado: 'ok', aguardando_aprovacao: 'agenda', rejeitado: 'erro',
      erro: 'erro', cancelado: 'pendente', publicado: 'ok',
      agendado: 'agenda', parcial: 'agenda', executando: 'fazendo', aguardando_credenciais: 'pendente' };
    return `<span class="cx-selo ${mapa[e] || 'pendente'}">${esc(METAS[e] || e || '—')}</span>`;
  }

  function listaProducoes(comBotoes = true) {
    const prods = (S.dados.producoes || []);
    if (!prods.length) return '<div class="cx-vazio"><b>Nenhum vídeo produzido neste canal</b>Use a aba Produzir para gerar o primeiro roteiro e montar o vídeo.</div>';
    return '<div class="cx-lista">' + prods.slice(0, 12).map((p) => {
      const podeAgendar = p.estado === 'aprovado' &&
        p.arquivos && Object.keys(p.arquivos.videos || {}).length;
      return `<div class="cx-prod ${esc(p.estado || '')}">
        <div><b>${esc(p.titulo || p.id)}</b>
          <div class="cx-prod-sub">${dataHora(p.criado)} · ${esc(METAS[p.estado] || p.estado || '')}
            ${p.parte ? ' · Parte ' + p.parte : ''}
            ${p.progresso != null && p.estado !== 'concluido' ? ' · ' + p.progresso + '%' : ''}
            ${p.erro ? ' · ' + esc(p.erro.slice(0, 140)) : ''}</div></div>
        <div class="cx-prod-bts">${seloEstado(p.estado)}
          <button type="button" class="bt-sec mini" data-acao="ver-producao" data-id="${esc(p.id)}">Abrir</button>
          ${comBotoes && podeAgendar ? `<button type="button" class="bt-sec mini" data-acao="abrir-agendar" data-id="${esc(p.id)}">${ic('relogio')}Agendar</button>` : ''}
        </div></div>`;
    }).join('') + '</div>';
  }

  // ------------------------------------------------------------------ visão geral
  function telaVisao() {
    const d = S.dados, ctx = d.contexto || {}, prods = d.producoes || [];
    const ag = (d.agenda || []).filter((a) => ['agendado', 'parcial', 'executando'].includes(a.estado))
      .sort((a, b) => (a.quando || 0) - (b.quando || 0));
    const proximo = ag[0];
    const cred = d.credenciais || {};
    const conectadas = Object.values(cred).filter((x) => x && x.configurado).length;
    const t = (S.analise && S.analise.total) || null;
    const ativos = (d.formatos || []).filter((f) => f.ativo !== false);
    return `
      <div class="cx-kpis">
        <div class="cx-kpi"><div class="k-rotulo">Produções</div><div class="k-valor">${prods.length}</div>
          <div class="k-nota">${prods.filter((p) => p.estado === 'concluido').length} prontas</div></div>
        <div class="cx-kpi"><div class="k-rotulo">Na agenda</div><div class="k-valor">${ag.length}</div>
          <div class="k-nota">${proximo ? 'próxima ' + dataHora(proximo.quando) : 'nada marcado'}</div></div>
        <div class="cx-kpi"><div class="k-rotulo">Visualizações</div><div class="k-valor">${t ? nf.format(t.views || 0) : '—'}</div>
          <div class="k-nota">${t ? 'últimos ' + S.analiseDias + ' dias' : 'abra a aba Análise'}</div></div>
        <div class="cx-kpi destaque"><div class="k-rotulo">Receita</div><div class="k-valor">${t ? money(t.receita) : '—'}</div>
          <div class="k-nota">${t ? 'engajamento ' + pct(t.engagement) : 'importe os números das plataformas'}</div></div>
      </div>
      <div class="cx-grid2">
        <div class="cx-card">
          <h2>O mundo deste canal</h2>
          <p class="fraco">${esc(ctx.tema || 'Sem tema definido ainda.')}</p>
          <div class="cx-row" style="margin-top:8px">
            <span class="cx-selo">${esc((ctx.personagens || []).length)} personagens</span>
            <span class="cx-selo">${ativos.length} formatos</span>
            <span class="cx-selo ${conectadas ? 'ok' : 'pendente'}">${conectadas} de 3 contas conectadas</span>
          </div>
          <p class="nota" style="margin-top:10px">${esc(ctx.publico || 'Público não definido')} · ${esc(ctx.tom || 'tom livre')}</p>
          <div class="cx-acoes" style="justify-content:flex-start">
            <button type="button" class="bt-sec" data-acao="ir-ajustes">${ic('ajustes')}Editar contexto</button>
            <button type="button" class="gerar" data-acao="ir-produzir">${ic('play')}Produzir vídeo</button>
          </div>
        </div>
        <div class="cx-card">
          <h2>Próximos commits na agenda</h2>
          ${proximo ? `<div class="cx-prod"><div><b>${esc(proximo.titulo || proximo.producao_id)}</b>
            <div class="cx-prod-sub">${dataHora(proximo.quando)} · ${(proximo.plataformas || []).map((p) => Rotulo[p] || p).join(' · ')}</div></div>
            ${seloEstado(proximo.estado)}</div>
            <div class="cx-acoes" style="justify-content:flex-start;margin-top:8px">
              <button type="button" class="bt-sec mini" data-acao="abrir-agenda">Ver a agenda</button></div>`
            : '<p class="fraco">Nada programado. Um vídeo pronto também pode ser agendado pelo botão Agendar.</p>'}
          <h3 style="margin-top:16px">Formatos ativos</h3>
          <div class="cx-row">${ativos.map((f) => `<span class="cx-selo">${esc(f.nome)} · ${f.largura}x${f.altura}</span>`).join('') || '<span class="fraco">Nenhum formato ativo.</span>'}</div>
        </div>
      </div>
      <div class="cx-card">
        <div class="cx-row" style="margin-bottom:10px"><h2 style="margin:0">Últimos vídeos</h2>
          <button type="button" class="bt-sec mini cx-right" data-acao="ir-produzir">Produzir outro</button></div>
        ${listaProducoes()}
      </div>`;
  }

  // ------------------------------------------------------------------ produzir
  function telaProduzir() {
    const d = S.dados;
    const ativos = (d.formatos || []).filter((f) => f.ativo !== false);
    const disponiveis = d.personagens_disponiveis || [];
    const insp = S.inspiracao || {};
    return `
      <div class="cx-card">
        <h2>Do briefing ao vídeo</h2>
        <p class="fraco">Escreva o que você quer postar. A IA local monta roteiro, falas, cenas e personagens com base no contexto deste canal. O número de cenas é calculado pela duração e pelo roteiro.</p>
        <div class="cx-form">
          <label><span>Briefing</span><textarea id="cxBriefing" rows="5" placeholder="Ex.: conta a história de Davi e Golias em 45 segundos, com gancho nos 3 primeiros segundos, sem citar violência explícita.">${esc(S.briefing || '')}</textarea></label>
          <div class="cx-briefing-grade">
            <div class="cx-campo"><label for="cxDuracao">Duração mínima (s)</label>
              <select id="cxDuracao">${opcoesSelect([15, 20, 30, 45, 60, 75, 90, 120, 180], Number((d.producao || {}).duracao_alvo) || 45)}</select>
              <span class="cx-dica">O vídeo pode ficar mais longo, nunca menor.</span></div>
            <div class="cx-campo"><label for="cxEstilo">Estilo visual</label>
              <select id="cxEstilo">${estilosDisponiveis().map((e) =>
                `<option value="${esc(e.id)}" ${((d.producao || {}).estilo || 'auto') === e.id ? 'selected' : ''}>${esc(e.nome)}</option>`).join('')}</select></div>
            <div class="cx-campo"><label for="cxParte">Série</label>
              <select id="cxParte"><option value="0">Vídeo único</option><option value="1">Parte 1 de uma série</option></select>
              <span class="cx-dica">Depois de aprovado, use Próxima parte.</span></div>
            <div class="cx-campo"><span class="cx-rotulo"><label>Formatos a montar</label></span>
              <div class="cx-row" style="gap:12px">${ativos.map((f) =>
                `<label class="cx-check"><input type="checkbox" data-formato="${esc(f.id)}" checked>${esc(f.nome)}</label>`).join('') || '<span class="fraco">Ative um formato em Ajustes.</span>'}</div>
              <span class="cx-dica">Imagens automáticas: uma por proporção ativa. 9:16 e 16:9 não são o mesmo arquivo.</span></div>
          </div>
          <div class="cx-campo"><div class="cx-rotulo"><label>Personagens</label>
            <span class="cx-dica">Sem marcar = a IA escolhe e repete a aparência</span></div>
            <div class="cx-personagens-uso">${disponiveis.map((p) =>
              `<label class="cx-check cx-pill cx-pill-pers" title="${esc(p.descricao || p.origem || '')}">
                ${avatarHtml(p.nome)}<input type="checkbox" data-personagem="${esc(p.nome)}" ${(S.personagensNovos || []).includes(p.nome) ? 'checked' : ''}>${esc(p.nome)}</label>`).join('')
              || '<span class="fraco">Nenhum personagem ainda. A IA cria no roteiro e os próximos vídeos podem reaproveitar.</span>'}</div>
            <div class="cx-acoes" style="justify-content:flex-start">
              <button type="button" class="bt-sec mini" data-acao="gerar-personagens">${ic('brilho')}Gerar personagens com IA</button>
              <button type="button" class="bt-sec mini" data-acao="gerar-retratos">${ic('imagem')}Gerar retratos</button>
              <span class="cx-dica">Cria novos a partir do que já existe no canal.</span>
            </div>
          </div>
          <div class="cx-campo"><div class="cx-rotulo"><label for="cxInspiracaoUrl">Vídeo de inspiração</label>
            <button type="button" class="cx-ia" data-acao="ler-inspiracao">${ic('brilho')}Ler referência</button></div>
            <input id="cxInspiracaoUrl" type="url" value="${esc(insp.url || '')}" placeholder="Cole a URL do YouTube ou TikTok">
            <p class="nota" id="cxInspiracaoStatus">${insp.titulo
              ? 'Referência: ' + esc(insp.titulo) + (insp.autor ? ' de ' + esc(insp.autor) : '')
              : 'Opcional. O roteiro se inspira no ritmo e no clima, sem copiar o vídeo.'}</p>
          </div>
          <div class="cx-acoes">
            <button type="button" class="bt-sec" data-acao="gerar-plano">${ic('brilho')}Só o roteiro</button>
            <button type="button" class="gerar" data-acao="produzir-direto">${ic('play')}Gerar vídeo completo</button>
          </div>
          <p class="nota">Gerar vídeo completo faz roteiro, voz, imagens e montagem sem revisão. Só o roteiro deixa você revisar as cenas antes.</p>
        </div>
      </div>
      <div id="cxProgresso">${S.producao ? cartaoProgresso(S.producao) : ''}</div>
      ${S.plano ? editorPlano() : ''}
      <div class="cx-card"><div class="cx-row" style="margin-bottom:10px"><h2 style="margin:0">Últimos vídeos</h2></div>${listaProducoes()}</div>`;
  }

  function editorPlano() {
    const p = S.plano || {};
    const cenas = p.cenas || [];
    const pers = p.personagens || [];
    return `<div class="cx-card">
      <div class="cx-row"><h2 style="margin:0">Roteiro</h2>
        <span class="cx-selo">${p.motor === 'fallback' ? 'montado do briefing' : 'IA local'}</span>
        <span class="cx-selo">${nf1.format(p.duracao_estimada || 0)} s estimados</span>
        ${p.duracao_minima && Number(p.duracao_estimada || 0) < Number(p.duracao_minima)
          ? `<span class="cx-selo">segura até ${p.duracao_minima} s se faltar</span>` : ''}
        <button type="button" class="bt-sec mini cx-right" data-acao="gerar-plano">${ic('brilho')}Gerar de novo</button></div>
      <p class="nota" style="margin:6px 0 12px">${esc(p.observacoes || 'Confira as falas e a descrição visual de cada cena antes de produzir.')}</p>
      <div class="cx-grid2">
        <label class="voz-campo"><span>Título</span><input id="cxTitulo" type="text" maxlength="120" value="${esc(p.titulo || '')}"></label>
        <label class="voz-campo"><span>Gancho (primeiros 3 segundos)</span><input id="cxGancho" type="text" maxlength="300" value="${esc(p.gancho || '')}"></label>
      </div>
      <div class="cx-grid2" style="margin-top:12px">
        <label class="voz-campo"><span>Legenda do post</span><textarea id="cxLegenda" rows="3">${esc(p.legenda || '')}</textarea></label>
        <label class="voz-campo"><span>Hashtags</span><input id="cxHashtags" type="text" value="${esc((p.hashtags || []).join(' '))}">
          <span class="nota">Chamada final: <input id="cxCta" type="text" value="${esc(p.cta || '')}" style="margin-top:5px"></span></label>
      </div>
      <h3 style="margin:16px 0 8px">Personagens</h3>
      <div class="cx-pers" id="cxPersonagens">${pers.map(linhaPersonagem).join('')}</div>
      <div class="cx-acoes"><button type="button" class="bt-sec mini" data-acao="add-persona">${ic('mais')}Personagem</button></div>
      <h3 style="margin:18px 0 8px">Cenas</h3>
      <div class="cx-cena-cab"><span>#</span><span>Fala (o que é dito)</span><span class="cx-prompt-cab">Imagem (descrição visual)</span><span>Personagem</span></div>
      <div class="cx-cenas" id="cxCenas">${cenas.map(linhaCena).join('')}</div>
      <div class="cx-acoes">
        <button type="button" class="bt-sec mini" data-acao="add-cena">${ic('mais')}Cena</button>
        <button type="button" class="gerar" data-acao="produzir">${ic('play')}Produzir tudo</button>
      </div>
    </div>`;
  }

  function linhaCena(c, i) {
    return `<div class="cx-cena" data-cena="${i}">
      <span class="n">${i + 1}</span>
      <textarea class="cx-fala" rows="2" placeholder="Fala curta, 1 a 2 frases">${esc(c.fala || '')}</textarea>
      <textarea class="cx-prompt" rows="2" placeholder="Descrição visual em inglês">${esc(c.imagem || '')}</textarea>
      <div><input class="cx-personagem" type="text" placeholder="Opcional" value="${esc(c.personagem || '')}">
        <button type="button" class="ic-bt cx-tirar" data-acao="del-cena" aria-label="Tirar cena">${ic('lixo')}</button></div>
    </div>`;
  }

  function avatarUrl(nome) {
    const arq = ((S.dados && S.dados.retratos) || {})[nome];
    return arq ? '/api/canais/' + encodeURIComponent(S.atual) + '/personagens/retrato/' + encodeURIComponent(arq) : '';
  }

  function avatarHtml(nome) {
    const u = avatarUrl(nome);
    if (u) return `<img class="cx-avatar" src="${u}" alt="">`;
    const ini = String(nome || '?').trim().slice(0, 2).toUpperCase();
    return `<span class="cx-avatar cx-avatar-vazio">${esc(ini)}</span>`;
  }

  function linhaPersonagem(p, i) {
    const papel = p.papel || 'principal';
    return `<div class="cx-persona" data-persona="${i}">
      <span class="cx-pers-avatar" title="${esc(p.nome || 'sem nome')}">${avatarHtml(p.nome)}</span>
      <input class="cx-pers-nome" type="text" placeholder="Nome" value="${esc(p.nome || '')}">
      <select class="cx-pers-papel" aria-label="Papel do personagem">
        ${[['principal', 'Principal'], ['coadjuvante', 'Coadjuvante'], ['figurante', 'Figurante']].map(([v, r]) =>
          `<option value="${v}" ${papel === v ? 'selected' : ''}>${r}</option>`).join('')}
      </select>
      <textarea class="cx-pers-desc" rows="2" placeholder="Quem é, o que quer, como fala">${esc(p.descricao || '')}</textarea>
      <textarea class="cx-pers-visual" rows="2" placeholder="Aparência visual (para a imagem)">${esc(p.visual || '')}</textarea>
      <button type="button" class="ic-bt" data-acao="del-persona" aria-label="Tirar personagem">${ic('lixo')}</button>
    </div>`;
  }

  function cartaoProgresso(p) {
    const et = p.etapas || {};
    const est = p.estado || '';
    const final = ['concluido', 'aprovado', 'aguardando_aprovacao', 'rejeitado', 'erro', 'cancelado'].includes(est);
    const videos = (p.arquivos && p.arquivos.videos) || {};
    const plano = p.plano || {};
    const urlVideo = (fid) => `/api/canais/${encodeURIComponent(S.atual)}/producoes/${encodeURIComponent(p.id)}/video/${encodeURIComponent(fid)}`;
    const revisao = est === 'aguardando_aprovacao' || est === 'concluido';
    const podePublicar = est === 'aprovado';
    return `<div class="cx-card">
      <div class="cx-row"><h2 style="margin:0">${esc(p.titulo || 'Produção')}</h2>${seloEstado(est)}
        <span class="fraco">${p.progresso || 0}%</span>
        ${!final ? `<button type="button" class="bt-sec mini cx-right" data-acao="cancelar-producao" data-id="${esc(p.id)}">${ic('parar')}Cancelar</button>` : ''}</div>
      <div class="cx-progresso"><i style="width:${Number(p.progresso) || 0}%"></i></div>
      <div class="cx-etapas">${['voz', 'imagens', 'montagem'].map((k) => {
        const e = et[k] || {};
        const cls = e.estado === 'ok' ? 'ok' : e.estado === 'rodando' ? 'fazendo' : e.estado === 'erro' ? 'erro' : '';
        const nome = k === 'voz' ? 'voz' : k === 'imagens' ? 'imagens' : 'montagem';
        return `<span class="${cls}"><i></i>${nome}${e.total ? ' · ' + (e.feito || 0) + '/' + e.total : ''}</span>`;
      }).join('')}</div>
      ${est === 'erro' && p.erro ? `<div class="cx-aviso erro" style="margin-top:10px">${esc(p.erro)}</div>` : ''}
      ${revisao ? `<div class="cx-aprovacao">
        <p class="nota">Assista antes de publicar. Ao aprovar, imagens e áudios intermediários são apagados; ficam só os vídeos, a legenda e os personagens.</p>
        <div class="cx-videos">${Object.entries(videos).map(([fid]) =>
          `<div class="cx-video"><span class="cx-video-rot">${esc(fid)}</span>
            <video controls preload="metadata" src="${urlVideo(fid)}"></video></div>`).join('')}</div>
        ${(plano.legenda || (plano.hashtags || []).length) ? `<div class="cx-legenda-aprovar">
          <b>Legenda</b><p>${esc(plano.legenda || '')}</p>
          <p class="fraco">${esc((plano.hashtags || []).join(' '))}</p></div>` : ''}
        <div class="cx-acoes">
          <button type="button" class="bt-sec" data-acao="rejeitar-producao" data-id="${esc(p.id)}">Rejeitar</button>
          <button type="button" class="gerar" data-acao="aprovar-producao" data-id="${esc(p.id)}">${ic('ok')}Aprovar e limpar arquivos</button>
        </div></div>` : ''}
      ${podePublicar ? `<div class="cx-acoes" style="justify-content:flex-start;margin-top:10px">
        <button type="button" class="bt-sec" data-acao="abrir-agendar" data-id="${esc(p.id)}">${ic('relogio')}Agendar</button>
        <button type="button" class="gerar" data-acao="abrir-agendar" data-id="${esc(p.id)}" data-agora="1">${ic('play')}Publicar agora</button>
        <button type="button" class="bt-sec" data-acao="proxima-parte" data-id="${esc(p.id)}">${ic('mais')}Próxima parte</button>
        ${p.limpeza && p.limpeza.bytes ? `<span class="cx-selo ok">${nf1.format((p.limpeza.bytes || 0) / 1048576)} MB liberados</span>` : ''}
      </div>` : ''}
      ${Object.keys(videos).length ? `<div class="cx-row" style="margin-top:10px">${Object.entries(videos).map(([fid]) =>
        `<a class="bt-sec mini" href="${urlVideo(fid)}" target="_blank" rel="noopener">${ic('baixar')}${esc(fid)}</a>`).join('')}</div>` : ''}
      ${p.log && p.log.length ? `<pre class="cx-log">${esc(p.log.slice(-12).join('\n'))}</pre>` : ''}
    </div>`;
  }

  // ------------------------------------------------------------------ agenda
  function telaAgenda() {
    const cred = S.dados.credenciais || {};
    const falta = Object.entries(cred).filter(([, v]) => !v.configurado).map(([, v]) => v.rotulo);
    const agenda = (S.dados.agenda || []).slice().sort((a, b) => (a.quando || 0) - (b.quando || 0));
    return `
      ${falta.length ? `<div class="cx-aviso">Sem conta conectada: ${esc(falta.join(', '))}. Você pode agendar de qualquer forma; a publicação espera a conta ser conectada em Ajustes.</div>` : ''}
      <div class="cx-card"><div class="cx-row" style="margin-bottom:10px">
        <h2 style="margin:0">Agenda de publicação</h2>
        <button type="button" class="gerar cx-right" data-acao="abrir-agendar">${ic('relogio')}Agendar publicação</button></div>
        <p class="fraco">O estúdio publica sozinho no horário marcado, mesmo com esta tela fechada. O computador precisa estar ligado e o estúdio aberto.</p>
        ${agenda.length ? '<div class="cx-lista" style="margin-top:12px">' + agenda.map((a) => {
          const res = a.resultados || {};
          const ids = Object.entries(res).filter(([, r]) => r.ok && (r.url || r.id));
          return `<div class="cx-prod ${a.estado === 'publicado' ? 'concluido' : a.estado === 'erro' ? 'erro' : ''}">
            <div><b>${esc(a.titulo || a.producao_id)}</b>
              <div class="cx-prod-sub">${dataHora(a.quando)} · ${(a.plataformas || []).map((p) => Rotulo[p] || p).join(' · ')} · ${esc(a.formato_id || '')}</div>
              ${a.erro ? `<div class="cx-prod-sub" style="color:var(--cx-crit)">${esc(a.erro)}</div>` : ''}
              ${ids.length ? `<div class="cx-prod-sub">${ids.map(([p, r]) => r.url
                ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(Rotulo[p] || p)}</a>`
                : esc(Rotulo[p] || p)).join(' · ')}</div>` : ''}</div>
            <div class="cx-prod-bts">${seloEstado(a.estado)}
              ${['agendado', 'parcial', 'erro', 'aguardando_credenciais'].includes(a.estado) ? `<button type="button" class="bt-sec mini" data-acao="publicar-agora" data-id="${esc(a.id)}">${ic('play')}Agora</button>` : ''}
              ${!['publicado', 'cancelado', 'executando'].includes(a.estado) ? `<button type="button" class="bt-sec mini" data-acao="cancelar-agenda" data-id="${esc(a.id)}">Cancelar</button>` : ''}
            </div></div>`;
        }).join('') + '</div>' : '<div class="cx-vazio" style="margin-top:12px"><b>Nada agendado</b>Produza um vídeo e clique em Agendar para escolher o formato, as plataformas e a hora.</div>'}
      </div>`;
  }

  // ------------------------------------------------------------------ análise
  function statusColeta(a) {
    const coleta = (a && a.coleta) || {};
    return Object.keys(Rotulo).map((p) => {
      const cfg = (S.dados.credenciais || {})[p] || {};
      const c = coleta[p] || {};
      let cls = 'pendente', txt = 'ainda não coletado';
      if (!cfg.configurado) { txt = 'conta não conectada'; }
      else if (c.erro) { cls = 'erro'; txt = c.erro; }
      else if (c.quando) { cls = 'ok'; txt = 'atualizado ' + dataHora(c.quando) + (c.novos ? ' · ' + c.novos + ' itens' : ''); }
      return `<div class="cx-coleta-plat ${cls}"><i style="--i:${Cores[p]}"></i>
        <b>${esc(Rotulo[p])}</b><span>${esc(txt)}</span></div>`;
    }).join('');
  }

  function cartaoColeta(a) {
    return `<div class="cx-card cx-coleta-card">
      <div class="cx-card-cab"><div><h2>Análise automática</h2>
        <p class="fraco">O estúdio lê views, receita, seguidores e engajamento direto das contas conectadas. Atualiza sozinho a cada 30 minutos.</p></div>
        <button type="button" class="gerar" data-acao="atualizar-analise">${ic('reusar')}Atualizar agora</button></div>
      <div class="cx-coleta-grid">${statusColeta(a)}</div>
    </div>`;
  }

  function telaAnalise() {
    const a = S.analise;
    const periodo = [[7, '7 dias'], [30, '30 dias'], [90, '90 dias']];
    let html = cartaoColeta(a) + `<div class="cx-row" style="margin-bottom:12px">
      <span class="fraco">Período</span>
      ${periodo.map(([d, r]) => `<button type="button" class="bt-sec mini" data-dias="${d}" ${S.analiseDias === d ? 'aria-pressed="true" style="border-color:var(--acento);color:var(--acento)"' : ''}>${r}</button>`).join('')}
      </div>`;
    if (!a) return html + '<p class="fraco">Lendo os números do canal…</p>';
    const t = a.total || {};
    if (!a.tem_dados) {
      return html + `<div class="cx-vazio"><b>Nenhum número ainda</b>
        Conecte YouTube, TikTok, Instagram e Facebook em Ajustes. Depois clique em Atualizar agora ou espere a coleta automática.
        <div class="cx-acoes" style="justify-content:center"><button type="button" class="gerar" data-acao="atualizar-analise">${ic('reusar')}Atualizar agora</button></div></div>
        <details class="cx-fallback"><summary>Importar CSV/JSON manualmente</summary>${cartaoImportar()}</details>`;
    }
    html += `<div class="cx-kpis">
      <div class="cx-kpi"><div class="k-rotulo">Visualizações</div><div class="k-valor">${nf.format(t.views || 0)}</div>
        <div class="k-nota">${t.videos || 0} vídeos no período</div></div>
      <div class="cx-kpi destaque"><div class="k-rotulo">Receita</div><div class="k-valor">${money(t.receita)}</div>
        <div class="k-nota">${a.meta_receita ? pct(a.progresso_meta) + ' da meta' : 'defina uma meta em Ajustes'}</div>
        ${a.meta_receita ? `<div class="k-barra"><i style="width:${Math.min(100, (a.progresso_meta || 0) * 100)}%"></i></div>` : ''}</div>
      <div class="cx-kpi"><div class="k-rotulo">Seguidores</div><div class="k-valor">${nf.format(t.seguidores || 0)}</div>
        <div class="k-nota">ganhos no período</div></div>
      <div class="cx-kpi"><div class="k-rotulo">Engajamento</div><div class="k-valor">${pct(t.engagement)}</div>
        <div class="k-nota">curtidas + comentários + shares / views</div></div>
    </div>`;
    html += `<div class="cx-grid2">
      <div class="cx-card"><div class="cx-chart-tit"><h3>Visualizações por dia</h3><span>${S.analiseDias} dias</span></div>
        ${graficoLinha('views', a.serie, 'views', '#3987e5', 'views')}</div>
      <div class="cx-card"><div class="cx-chart-tit"><h3>Receita por dia</h3><span>R$</span></div>
        ${graficoLinha('receita', a.serie, 'receita', '#d95926', 'receita')}</div>
    </div>`;
    html += `<div class="cx-card"><div class="cx-chart-tit"><h3>Melhores horários</h3><span>média de views por horário publicado</span></div>
      ${graficoHoras(a.horas, a.melhores_horarios)}</div>`;
    html += `<div class="cx-grid2">
      <div class="cx-card"><h3>Por plataforma</h3>${tabelaPlataformas(a.por_plataforma)}</div>
      <div class="cx-card"><h3>Receita por mês</h3>${graficoMeses(a.serie_meses)}</div>
    </div>`;
    html += `<div class="cx-card"><h3>Vídeos que puxaram o canal</h3>${tabelaTop(a.top)}</div>`;
    html += `<details class="cx-fallback"><summary>Importar CSV/JSON manualmente</summary>${cartaoImportar()}</details>`;
    return html;
  }

  function cartaoImportar() {
    return `<div class="cx-card cx-importar"><h3>Importar números manualmente</h3>
      <p class="fraco">Se alguma plataforma não liberar a análise automática, cole o CSV/JSON dela aqui. As colunas podem estar em português ou inglês: data, plataforma, views, likes, comentários, shares, receita, seguidores.</p>
      <textarea id="cxImportar" placeholder="data,plataforma,titulo,views,likes,comments,shares,receita,seguidores&#10;2026-11-10,youtube,Davi e Golias,12000,450,32,18,12.40,9"></textarea>
      <div class="cx-acoes"><button type="button" class="bt-sec" data-acao="importar">${ic('baixar')}Importar</button></div></div>`;
  }

  function tabelaPlataformas(p) {
    const itens = Object.entries(p || {}).sort((a, b) => (b[1].views || 0) - (a[1].views || 0));
    if (!itens.length) return '<p class="fraco">Sem dados por plataforma.</p>';
    const max = Math.max(1, ...itens.map(([, x]) => x.views || 0));
    return `<table class="cx-tabela"><thead><tr><th>Plataforma</th><th class="num">Views</th><th class="num">Receita</th><th class="num">Engaj.</th><th>Participação</th></tr></thead><tbody>
      ${itens.map(([k, x]) => `<tr><td><span class="plat" style="--p:${Cores[k] || '#3987e5'}"><i></i>${esc(Rotulo[k] || k)}</span></td>
        <td class="num">${nf.format(x.views || 0)}</td><td class="num">${money(x.receita)}</td>
        <td class="num">${pct(x.engagement)}</td><td><div class="trilho"><i style="width:${Math.round(100 * (x.views || 0) / max)}%"></i></div></td></tr>`).join('')}
    </tbody></table>`;
  }

  function tabelaTop(itens) {
    if (!itens || !itens.length) return '<p class="fraco">Sem vídeos no período.</p>';
    return `<table class="cx-tabela"><thead><tr><th>Vídeo</th><th>Plataforma</th><th class="num">Views</th><th class="num">Receita</th><th class="num">Data</th></tr></thead><tbody>
      ${itens.map((v) => `<tr><td>${v.url ? `<a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.titulo)}</a>` : esc(v.titulo)}</td>
        <td>${esc(Rotulo[v.plataforma] || v.plataforma)}</td><td class="num">${nf.format(v.views || 0)}</td>
        <td class="num">${money(v.receita)}</td><td class="num">${v.data ? new Date(v.data * 1000).toLocaleDateString('pt-BR') : '—'}</td></tr>`).join('')}
    </tbody></table>`;
  }

  // ------------------------------------------------------------------ gráficos
  function graficoLinha(id, serie, campo, cor, rotulo) {
    serie = serie || [];
    const W = 720, H = 210, P = { l: 46, r: 12, t: 12, b: 26 };
    const vals = serie.map((x) => Number(x[campo]) || 0);
    const max = Math.max(1, ...vals);
    const x = (i) => P.l + (W - P.l - P.r) * (serie.length <= 1 ? 0.5 : i / (serie.length - 1));
    const y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
    const pts = vals.map((v, i) => [x(i), y(v)]);
    const linha = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    const area = `M${x(0).toFixed(1)} ${y(0).toFixed(1)} ` + pts.map((p) => `L${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') +
      ` L${x(serie.length - 1).toFixed(1)} ${y(0).toFixed(1)} Z`;
    const passo = Math.max(1, Math.ceil(serie.length / 7));
    let marcas = '';
    for (let i = 0; i <= 4; i++) {
      const v = max * i / 4, yy = y(v);
      marcas += `<line class="grade" x1="${P.l}" y1="${yy.toFixed(1)}" x2="${W - P.r}" y2="${yy.toFixed(1)}"></line>
        <text class="eixo" x="${P.l - 7}" y="${(yy + 3).toFixed(1)}" text-anchor="end">${campo === 'receita' ? nf1.format(v) : nf.format(Math.round(v))}</text>`;
    }
    const rotulos = serie.map((s, i) => (i % passo === 0 || i === serie.length - 1)
      ? `<text class="eixo" x="${x(i).toFixed(1)}" y="${H - 7}" text-anchor="middle">${esc(s.rotulo || '')}</text>` : '').join('');
    const pontos = pts.map((p, i) => `<circle class="ponto" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5" data-i="${i}"></circle>`).join('');
    S.charts[id] = { serie, campo, rotulo, x, y, W, H, P, valores: vals };
    return `<div class="cx-chart" data-chart="${id}">
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(rotulo)} por dia">
        ${marcas}<path class="area" d="${area}" fill="${cor}" fill-opacity=".15"></path>
        <path class="serie" d="${linha}" style="stroke:${cor}"></path>${pontos}${rotulos}
      </svg><div class="cx-tip"></div></div>`;
  }

  function graficoHoras(horas, melhores) {
    horas = horas || [];
    const max = Math.max(1, ...horas.map((h) => h.media || 0));
    const top = new Set((melhores || []).map((h) => parseInt(h, 10)));
    return `<div class="cx-barras" id="cxBarrasHoras">${horas.map((h) => {
      const alt = Math.round(100 * (h.media || 0) / max);
      return `<div class="b ${top.has(h.hora) ? 'melhor' : ''}" data-hora="${h.hora}" data-views="${h.media || 0}" data-videos="${h.videos || 0}"
        title="${String(h.hora).padStart(2, '0')}:00 · média ${nf.format(h.media || 0)} views em ${h.videos || 0} vídeo(s)">
        ${top.has(h.hora) && h.media ? `<em>${String(h.hora).padStart(2, '0')}h</em>` : ''}
        <i style="height:${Math.max(2, alt)}%"></i><span>${String(h.hora).padStart(2, '0')}</span></div>`;
    }).join('')}</div><div class="cx-tip" id="cxTipHoras"></div>
    <div class="cx-legenda"><span><i style="background:#199e70"></i>3 melhores horários</span>
      <span><i style="background:#3987e5"></i>demais horários</span>
      <span>${melhores && melhores.length ? 'sugestão: ' + melhores.join(', ') : 'importe mais dados para a sugestão'}</span></div>`;
  }

  function graficoMeses(serie) {
    serie = serie || [];
    if (!serie.length) return '<p class="fraco">Sem receita mensal ainda.</p>';
    const max = Math.max(1, ...serie.map((s) => s.receita || 0));
    return `<div class="cx-barras" style="height:130px">${serie.map((s) => `<div class="b" title="${esc(s.rotulo)}: ${money(s.receita)}">
      <em>${s.receita ? nf1.format(s.receita) : ''}</em><i style="height:${Math.max(2, Math.round(100 * (s.receita || 0) / max))}%;background:#d95926"></i>
      <span>${esc(s.rotulo)}</span></div>`).join('')}</div>`;
  }

  // ------------------------------------------------------------------ ajustes
  function campoIA(campo, rotulo, controle, dica) {
    return `<div class="cx-campo"><div class="cx-rotulo"><label>${esc(rotulo)}</label>${botaoIA(campo)}</div>${controle}${dica ? `<span class="cx-dica">${esc(dica)}</span>` : ''}</div>`;
  }

  function chipHora(h) {
    return `<span class="cx-hora" data-hora="${esc(h)}">${esc(h)}<button type="button" data-acao="del-hora" data-hora="${esc(h)}" aria-label="Tirar ${esc(h)}">×</button></span>`;
  }

  function telaAjustes() {
    const d = S.dados, ctx = d.contexto || {}, pr = d.producao || {}, pub = d.publicacao || {};
    const formatos = d.formatos || [];
    const vozes = S.vozes || [];
    const modelos = modelosImagem();
    const presetAtual = pr.preset_imagem || 'z_image_turbo';
    const horas = (pub.horarios && pub.horarios.length) ? pub.horarios : ['06:00'];
    const opPreset = modelos.map((m) => `<option value="${esc(m.id)}" ${m.id === presetAtual ? 'selected' : ''}>${esc(m.nome || m.id)}</option>`).join('')
      + (modelos.some((m) => m.id === presetAtual) ? '' : `<option value="${esc(presetAtual)}" selected>${esc(presetAtual)}</option>`);
    const opQualidade = ['Normal', 'Alta', 'Máxima'].map((q) =>
      `<option ${pr.qualidade === q ? 'selected' : ''}>${q}</option>`).join('');
    const opIdioma = [['pt', 'Português'], ['en', 'Inglês'], ['es', 'Espanhol']].map(([v, r]) =>
      `<option value="${v}" ${ctx.idioma === v ? 'selected' : ''}>${r}</option>`).join('');
    const opVoz = `<option value="">Voz padrão do VoiceStudio</option>` + vozes.map((v) =>
      `<option value="${esc(v.id)}" ${((d.voz || {}).voz_id === v.id) ? 'selected' : ''}>${esc(v.nome || v.id)}</option>`).join('');
    return `
      <form class="cx-form" id="cxAjustes" onsubmit="return false">
        <div class="cx-card">
          <div class="cx-card-cab">
            <div><h2>Identidade do canal</h2>
              <p class="fraco">É o que a IA usa para escrever todo roteiro e toda imagem deste canal.</p></div>
            <button type="button" class="bt-sec" data-acao="ia-contexto">${ic('brilho')}Gerar contexto com IA</button>
          </div>
          <p class="nota cx-ia-status" id="cxIaStatus" hidden aria-live="polite"></p>
          <div class="cx-grid3">
            <div class="cx-campo"><label for="ajNome">Nome</label>
              <input id="ajNome" type="text" maxlength="80" value="${esc(d.nome || '')}" placeholder="Ex.: Histórias da Bíblia"></div>
            <div class="cx-campo"><label for="ajCor">Cor do canal</label>
              <input id="ajCor" type="color" value="${esc(d.cor || '#5B8DEF')}" class="cx-cor"></div>
            <div class="cx-campo"><label for="ajIdioma">Idioma</label>
              <select id="ajIdioma">${opIdioma}</select></div>
          </div>
          ${campoIA('tema', 'Tema (o que este canal conta)',
            `<textarea id="ajTema" rows="3" placeholder="Ex.: histórias bíblicas em 45 segundos, narradas como conversa, para quem nunca leu a Bíblia.">${esc(ctx.tema || '')}</textarea>`,
            'Se o nome não deixar claro, descreva aqui. A IA usa este texto em tudo.')}
          <div class="cx-grid2">
            ${campoIA('publico', 'Público',
              `<input id="ajPublico" type="text" value="${esc(ctx.publico || '')}" placeholder="Ex.: jovens de 18 a 30 anos que gostam de histórias curtas.">`)}
            ${campoIA('tom', 'Tom',
              `<input id="ajTom" type="text" value="${esc(ctx.tom || '')}" placeholder="Ex.: conversa direta, curiosa, sem sermão.">`)}
          </div>
          ${campoIA('identidade_visual', 'Identidade visual (entra nos prompts de imagem)',
            `<input id="ajVisual" type="text" value="${esc(ctx.identidade_visual || '')}" placeholder="Ex.: luz dourada, deserto, pintura realista, sem texto na imagem.">`)}
          <div class="cx-grid2">
            ${campoIA('regras', 'Regras (uma por linha)',
              `<textarea id="ajRegras" rows="3" placeholder="Ex.: gancho nos 3 primeiros segundos&#10;Ex.: uma ideia por vídeo&#10;Ex.: nunca dividir em parte 1 e parte 2">${esc((ctx.regras || []).join('\n'))}</textarea>`)}
            ${campoIA('nao_fazer', 'Não fazer (uma por linha)',
              `<textarea id="ajNao" rows="3" placeholder="Ex.: violência explícita&#10;Ex.: prometer milagre&#10;Ex.: falar mal de outra religião">${esc((ctx.nao_fazer || []).join('\n'))}</textarea>`)}
          </div>
          <div class="cx-grid2">
            ${campoIA('referencias', 'Referências (uma por linha)',
              `<textarea id="ajRef" rows="2" placeholder="Ex.: ritmo de TikTok de história&#10;Ex.: estética de documentário">${esc((ctx.referencias || []).join('\n'))}</textarea>`)}
            ${campoIA('chamada_final', 'Chamada final',
              `<input id="ajCta" type="text" value="${esc(ctx.chamada_final || '')}" placeholder="Ex.: comenta qual é a sua maior coragem hoje.">`)}
          </div>
          ${campoIA('hashtags', 'Hashtags padrão',
            `<input id="ajHashtags" type="text" value="${esc((ctx.hashtags || []).join(' '))}" placeholder="#historias #fe #coragem #shorts">`)}
        </div>

        <div class="cx-card">
          <div class="cx-card-cab"><div><h2>Personagens do canal</h2>
            <p class="fraco">Eles entram em todo roteiro deste canal, com a mesma aparência.</p></div>
            <button type="button" class="bt-sec mini" data-acao="add-persona-ajustes">${ic('mais')}Personagem</button></div>
          <div class="cx-pers" id="cxPersonagensAjustes">${(ctx.personagens || []).map(linhaPersonagem).join('')}</div>
        </div>

        <div class="cx-card">
          <div class="cx-card-cab"><div><h2>Produção e formatos</h2>
            <p class="fraco">Estes valores viram o padrão de todo vídeo deste canal.</p></div></div>
          <div class="cx-grid3">
            <div class="cx-campo"><label for="ajDuracao">Duração mínima (s)</label>
              <select id="ajDuracao">${opcoesSelect([15, 20, 30, 45, 60, 75, 90, 120, 180], Number(pr.duracao_alvo) || 45)}</select>
              <span class="cx-dica">O vídeo pode passar; nunca fica menor.</span></div>
            <div class="cx-campo"><label for="ajQualidade">Qualidade</label>
              <select id="ajQualidade">${opQualidade}</select></div>
            <div class="cx-campo"><label for="ajImagensPorFormato">Imagens por formato</label>
              <select id="ajImagensPorFormato">${[
                ['auto', 'Automático (uma por proporção)'],
                ['unico', 'Uma só (reaproveita com desfoque)'],
                ['9:16', 'Só 9:16'],
                ['16:9', 'Só 16:9'],
                ['1:1', 'Só 1:1'],
              ].map(([v, r]) => `<option value="${v}" ${((pr.imagens_por_formato || 'auto') === v) ? 'selected' : ''}>${r}</option>`).join('')}</select>
              <span class="cx-dica">Automático gera uma imagem para cada proporção ativa.</span></div>
          </div>
          <div class="cx-grid3">
            <div class="cx-campo"><label for="ajPreset">Modelo de imagem</label>
              <select id="ajPreset">${opPreset}</select></div>
            <div class="cx-campo"><label for="ajVoz">Voz</label>
              <select id="ajVoz">${opVoz}</select></div>
            <div class="cx-campo"><label for="ajEstilo">Estilo visual</label>
              <select id="ajEstilo">${estilosDisponiveis().map((e) =>
                `<option value="${esc(e.id)}" ${((pr.estilo || 'auto') === e.id) ? 'selected' : ''}>${esc(e.nome)}</option>`).join('')}</select></div>
          </div>
          <div class="cx-check-linha">
            <label class="cx-check"><input type="checkbox" id="ajLegendas" ${pr.legendas !== false ? 'checked' : ''}>Legendas nos formatos verticais</label>
            <label class="cx-check"><input type="checkbox" id="ajFalar" ${pr.falar_cenas !== false ? 'checked' : ''}>Gerar narração por cena</label>
          </div>
          <div class="cx-secao-cab"><h3>Formatos a montar</h3>
            <p class="nota">Padrão: 1080x1920 no vertical e 1920x1080 no horizontal, suficiente para celular e YouTube sem 4K. Formatos da mesma proporção e legenda reaproveitam o mesmo arquivo.</p></div>
          <div class="cx-formato-cab"><span>Ativo</span><span>Formato</span><span>Tamanho (px)</span><span>Plataforma</span><span>Legendas</span><span></span></div>
          <div class="cx-formatos" id="cxFormatos">${formatos.map(linhaFormato).join('')}</div>
          <div class="cx-acoes"><button type="button" class="bt-sec mini" data-acao="add-formato">${ic('mais')}Formato</button></div>
        </div>

        <div class="cx-card">
          <div class="cx-card-cab"><div><h2>Publicação</h2>
            <p class="fraco">O estúdio publica sozinho no horário, mesmo com esta tela fechada. O computador precisa estar ligado.</p></div></div>
          <div class="cx-check-linha" style="margin-bottom:12px">
            <label class="cx-check"><input type="checkbox" id="ajAuto" ${pub.automatico ? 'checked' : ''}>Agendar sozinho depois de aprovar</label>
          </div>
          <div class="cx-grid2">
            <div class="cx-campo"><div class="cx-rotulo"><label>Horários</label><span class="cx-dica">Escolha os horários</span></div>
              <div class="cx-horarios" id="cxHorarios">${horas.map(chipHora).join('')}
                <span class="cx-hora-add"><select id="ajHoraNova">${HORAS.filter((h) => !horas.includes(h)).map((h) => `<option>${h}</option>`).join('')}</select>
                  <button type="button" class="bt-sec mini" data-acao="add-hora" ${HORAS.some((h) => !horas.includes(h)) ? '' : 'disabled'}>${ic('mais')}Adicionar</button></span></div>
              <input type="hidden" id="ajHorarios" value="${esc(horas.join(', '))}">
            </div>
            <div class="cx-campo"><label for="ajVisibilidade">Visibilidade</label>
              <select id="ajVisibilidade">${['public', 'unlisted', 'private'].map((v) =>
                `<option value="${v}" ${pub.visibilidade === v ? 'selected' : ''}>${v === 'public' ? 'Público' : v === 'unlisted' ? 'Não listado' : 'Privado'}</option>`).join('')}</select></div>
          </div>
          <div class="cx-campo"><div class="cx-rotulo"><label>Plataformas</label><span class="cx-dica">Só as marcadas entram na agenda automática</span></div>
            <div class="cx-plataformas">${Object.entries(d.credenciais || {}).map(([k, v]) =>
              `<label class="cx-check cx-pill"><input type="checkbox" data-pubplat="${k}" ${(pub.plataformas || []).includes(k) ? 'checked' : ''}>
                <span class="cx-ponto" style="--i:${Cores[k] || '#3987e5'}"></span>${esc(v.rotulo || Rotulo[k] || k)}</label>`).join('')}</div>
          </div>
          <div class="cx-grid2">
            <div class="cx-campo"><label for="ajMeta">Meta de receita mensal (R$)</label>
              <input id="ajMeta" type="number" min="0" step="0.01" value="${Number((d.analytics || {}).meta_receita) || 0}" placeholder="Ex.: 1000"></div>
            <div class="cx-campo"><label for="ajTagsAgenda">Hashtags da agenda</label>
              <input id="ajTagsAgenda" type="text" value="${esc(((d.publicacao || {}).hashtags || []).join(' '))}" placeholder="#historias #shorts"></div>
          </div>
        </div>

        <div class="cx-card">
          <div class="cx-card-cab"><div><h2>Análise</h2>
            <p class="fraco">A coleta usa as mesmas contas conectadas para publicar. Sem a permissão de análise, a plataforma mostra o motivo e você ainda pode importar CSV.</p></div></div>
          <label class="cx-check"><input type="checkbox" id="ajAnaliseAuto" ${((d.analytics || {}).automatico !== false) ? 'checked' : ''}>Atualizar automaticamente a cada 30 minutos</label>
        </div>

        <div class="cx-card">
          <div class="cx-card-cab"><div><h2>Contas das plataformas</h2>
            <p class="fraco">As chaves ficam só nesta máquina, em <code>canais/segredos.json</code> com permissão 600. A tela nunca mostra um token de volta.</p></div></div>
          <div class="cx-cred">${credenciaisHTML(d.credenciais || {})}</div>
        </div>

        <div class="cx-acoes cx-acoes-fim"><button type="button" class="gerar" data-acao="salvar-ajustes">${ic('ok')}Salvar canal</button></div>
      </form>`;
  }

  function linhaFormato(f) {
    return `<div class="cx-formato" data-fmt-row data-fid="${esc(f.id || '')}">
      <label class="cx-check cx-centro" title="Ativo"><input type="checkbox" data-fmt-ativo ${f.ativo !== false ? 'checked' : ''}></label>
      <input data-fmt-nome type="text" value="${esc(f.nome || 'Formato')}" aria-label="Nome do formato" placeholder="Ex.: YouTube Shorts">
      <div class="cx-dim"><input data-fmt-largura type="number" min="240" step="2" value="${Number(f.largura) || 1080}" aria-label="Largura">
        <span>×</span><input data-fmt-altura type="number" min="240" step="2" value="${Number(f.altura) || 1920}" aria-label="Altura"></div>
      <select data-fmt-plataforma aria-label="Plataforma">${Object.entries(Rotulo).map(([k, v]) =>
        `<option value="${k}" ${f.plataforma === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
      <label class="cx-check cx-centro" title="Legendas"><input type="checkbox" data-fmt-legendas ${f.legendas !== false ? 'checked' : ''}></label>
      <button type="button" class="ic-bt" data-acao="del-formato" aria-label="Tirar formato">${ic('lixo')}</button>
    </div>`;
  }

  function campoCred(p, def, c) {
    const detalhe = c.detalhe || {};
    const sensivel = /token|secret|key/i.test(def.k);
    if (def.tipo === 'check') {
      return `<label class="cx-check"><input type="checkbox" data-cred-campo="${def.k}" ${String(detalhe[def.k]).toLowerCase() === 'true' ? 'checked' : ''}>${esc(def.rot)}</label>`;
    }
    if (def.tipo === 'select') {
      return `<div class="cx-campo"><label>${esc(def.rot)}</label><select data-cred-campo="${def.k}">${def.opcoes.map(([v, r]) =>
        `<option value="${esc(v)}" ${String(detalhe[def.k] || def.atual || '') === String(v) ? 'selected' : ''}>${esc(r)}</option>`).join('')}</select></div>`;
    }
    const valor = sensivel ? '' : (detalhe[def.k] || '');
    const ph = sensivel && c.configurado && detalhe[def.k] ? 'já configurado' : (def.ph || '');
    return `<div class="cx-campo"><label>${esc(def.rot)}</label>
      <input data-cred-campo="${def.k}" type="${def.tipo || 'text'}" value="${esc(valor)}" placeholder="${esc(ph)}" autocomplete="off"></div>`;
  }

  function credenciaisHTML(cred) {
    const ajuda = {
      youtube: 'Google Cloud > APIs e serviços > Credenciais > OAuth do tipo "App para computador". Habilite a YouTube Data API v3 e autorize com youtube.upload e youtube.readonly.',
      tiktok: 'developers.tiktok.com > app com Content Posting API. Autorize a conta e cole o access token. Sem auditoria do app, use "Só eu".',
      instagram: 'Conta profissional ligada a uma Página do Facebook. Token com instagram_content_publish e ig_user_id. O vídeo precisa estar numa URL pública.',
      facebook: 'Página do Facebook com token de Página. Permissões pages_manage_posts e pages_read_engagement. O vídeo sobe direto, sem URL pública.',
    };
    const campos = {
      youtube: [
        { k: 'client_id', rot: 'Client ID', tipo: 'text', ph: 'Ex.: 1234567890-abc.apps.googleusercontent.com' },
        { k: 'client_secret', rot: 'Client secret', tipo: 'password', ph: 'Ex.: GOCSPX-...' },
        { k: 'refresh_token', rot: 'Refresh token', tipo: 'password', ph: 'Ex.: 1//0g...' },
        { k: 'categoria', rot: 'Categoria do vídeo', tipo: 'select', opcoes: CATEGORIAS_YT, atual: '22' },
      ],
      tiktok: [
        { k: 'access_token', rot: 'Access token', tipo: 'password', ph: 'Ex.: act.example...' },
        { k: 'privacy_level', rot: 'Privacidade', tipo: 'select', opcoes: [['PUBLIC_TO_EVERYONE', 'Público'], ['SELF_ONLY', 'Só eu']], atual: 'SELF_ONLY' },
        { k: 'disable_comment', rot: 'Desativar comentários', tipo: 'check' },
        { k: 'disable_duet', rot: 'Desativar duetos', tipo: 'check' },
        { k: 'disable_stitch', rot: 'Desativar remixes', tipo: 'check' },
      ],
      instagram: [
        { k: 'access_token', rot: 'Access token', tipo: 'password', ph: 'Ex.: IGQVJ...' },
        { k: 'ig_user_id', rot: 'IG user id', tipo: 'text', ph: 'Ex.: 17841400000000000' },
        { k: 'video_base_url', rot: 'URL pública da pasta do vídeo', tipo: 'url', ph: 'Ex.: https://meusite.com/videos' },
      ],
      facebook: [
        { k: 'page_id', rot: 'ID da Página', tipo: 'text', ph: 'Ex.: 123456789012345' },
        { k: 'access_token', rot: 'Access token da Página', tipo: 'password', ph: 'Ex.: EAAB...' },
      ],
    };
    return Object.entries(campos).map(([p, lista]) => {
      const c = cred[p] || {};
      return `<div class="cx-card cx-cred-card">
        <div class="cx-cred-cab"><h3>${esc(Rotulo[p] || p)}</h3>
          <span class="cx-selo ${c.configurado ? 'ok' : 'pendente'}">${c.configurado ? 'conectado' : 'não conectado'}</span></div>
        <p class="nota">${esc(ajuda[p])}</p>
        <div class="cx-form" data-cred="${p}">${lista.map((def) => campoCred(p, def, c)).join('')}</div>
        <div class="cx-acoes"><button type="button" class="bt-sec" data-acao="salvar-cred" data-plat="${p}">Salvar ${esc(Rotulo[p] || p)}</button></div>
      </div>`;
    }).join('');
  }

  // ================================================================ plano: ler e produzir
  function lerPlano() {
    const p = JSON.parse(JSON.stringify(S.plano || {}));
    p.titulo = ($('#cxTitulo') || {}).value || p.titulo || 'Vídeo';
    p.gancho = ($('#cxGancho') || {}).value || p.gancho || '';
    p.legenda = ($('#cxLegenda') || {}).value || '';
    p.cta = ($('#cxCta') || {}).value || '';
    p.hashtags = tags(($('#cxHashtags') || {}).value || '');
    p.personagens = $$('#cxPersonagens .cx-persona').map((el) => ({
      nome: ($('.cx-pers-nome', el) || {}).value || '',
      papel: ($('.cx-pers-papel', el) || {}).value || 'principal',
      descricao: ($('.cx-pers-desc', el) || {}).value || '',
      visual: ($('.cx-pers-visual', el) || {}).value || '',
    }));
    p.cenas = $$('#cxCenas .cx-cena').map((el, i) => ({
      n: i + 1,
      fala: ($('.cx-fala', el) || {}).value || '',
      imagem: ($('.cx-prompt', el) || {}).value || '',
      personagem: ($('.cx-personagem', el) || {}).value || '',
    }));
    return p;
  }

  function personagensEscolhidos() {
    return $$('[data-personagem]:checked').map((x) => x.dataset.personagem);
  }

  function inspiracaoAtual() {
    const url = (($('#cxInspiracaoUrl') || {}).value || '').trim();
    if (S.inspiracao && S.inspiracao.url === url) return S.inspiracao;
    return null;
  }

  async function lerInspiracao() {
    const url = (($('#cxInspiracaoUrl') || {}).value || '').trim();
    const status = $('#cxInspiracaoStatus');
    if (!url) { if (status) status.textContent = 'Cole a URL primeiro.'; return; }
    const bt = $('[data-acao="ler-inspiracao"]');
    if (bt) bt.disabled = true;
    if (status) status.textContent = 'Lendo a referência…';
    try {
      const r = await pedir('/api/inspiracao', { url });
      S.inspiracao = r;
      if (status) status.textContent = 'Referência: ' + (r.titulo || url) + (r.autor ? ' de ' + r.autor : '');
    } catch (e) {
      S.inspiracao = null;
      if (status) { status.textContent = e.message; status.className = 'nota erro'; }
    } finally { if (bt) bt.disabled = false; }
  }

  async function garantirInspiracao() {
    const url = (($('#cxInspiracaoUrl') || {}).value || '').trim();
    if (url && (!S.inspiracao || S.inspiracao.url !== url)) await lerInspiracao();
    return inspiracaoAtual();
  }

  async function gerarPlano() {
    const briefing = (($('#cxBriefing') || {}).value || '').trim();
    if (!briefing) { mostrar('Escreva o briefing antes de gerar o roteiro.', 'erro'); return; }
    S.briefing = briefing;
    const bt = $('[data-acao="gerar-plano"]');
    if (bt) { bt.disabled = true; bt.textContent = 'Lendo o briefing…'; }
    try {
      const inspiracao = await garantirInspiracao();
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/plano', {
        briefing,
        duracao: Number(($('#cxDuracao') || {}).value) || undefined,
        estilo: ($('#cxEstilo') || {}).value || undefined,
        parte: Number(($('#cxParte') || {}).value) || 0,
        personagens: personagensEscolhidos(),
        inspiracao,
      });
      S.plano = r.plano;
      mostrar('Roteiro pronto. Revise as cenas e mande produzir.', 'ok');
      render();
    } catch (e) {
      mostrar('Não consegui montar o roteiro: ' + e.message, 'erro');
    } finally {
      if (bt) { bt.disabled = false; if (bt.isConnected) bt.innerHTML = ic('brilho') + 'Só o roteiro'; }
    }
  }

  async function produzir() {
    if (!S.plano) { mostrar('Gere o roteiro primeiro.', 'erro'); return; }
    const plano = lerPlano();
    plano.cenas = plano.cenas.filter((c) => String(c.fala || '').trim());
    if (!plano.cenas.length) { mostrar('Nenhuma cena com fala para produzir.', 'erro'); return; }
    const formatos = $$('[data-formato]:checked').map((x) => x.dataset.formato);
    const bt = $('[data-acao="produzir"]');
    if (bt) { bt.disabled = true; bt.textContent = 'Começando…'; }
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/produzir',
        { plano, briefing: S.briefing, formatos, inspiracao: inspiracaoAtual(),
          estilo: ($('#cxEstilo') || {}).value || undefined,
          parte: Number(($('#cxParte') || {}).value) || 0 });
      S.producao = { ...r.producao, plano: r.plano || S.plano };
      mostrar('Produção começou. A voz vem primeiro; depois as imagens e a montagem.', 'ok');
      render();
      pollProducao(r.producao.id);
    } catch (e) {
      mostrar('A produção não começou: ' + e.message, 'erro');
    } finally {
      if (bt) { bt.disabled = false; if (bt.isConnected) bt.innerHTML = ic('play') + 'Produzir tudo'; }
    }
  }

  async function produzirDireto() {
    const briefing = (($('#cxBriefing') || {}).value || '').trim();
    if (!briefing) { mostrar('Escreva o briefing antes de gerar o vídeo completo.', 'erro'); return; }
    const formatos = $$('[data-formato]:checked').map((x) => x.dataset.formato);
    const bt = $('[data-acao="produzir-direto"]');
    if (bt) { bt.disabled = true; bt.textContent = 'Começando a produção…'; }
    try {
      const inspiracao = await garantirInspiracao();
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/produzir', {
        briefing,
        duracao: Number(($('#cxDuracao') || {}).value) || undefined,
        estilo: ($('#cxEstilo') || {}).value || undefined,
        parte: Number(($('#cxParte') || {}).value) || 0,
        formatos,
        personagens: personagensEscolhidos(),
        inspiracao,
      });
      S.briefing = briefing;
      S.plano = r.plano;
      S.producao = { ...r.producao, plano: r.plano };
      mostrar('Produção completa começou: roteiro, voz, imagens e montagem.', 'ok');
      render();
      pollProducao(r.producao.id);
    } catch (e) {
      mostrar('A produção não começou: ' + e.message, 'erro');
    } finally {
      if (bt) { bt.disabled = false; if (bt.isConnected) bt.innerHTML = ic('play') + 'Gerar vídeo completo'; }
    }
  }

  function pollProducao(pid) {
    pararPoll();
    S.poll = setInterval(async () => {
      try {
        const d = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' + encodeURIComponent(pid));
        S.producao = d;
        const cx = $('#cxProgresso');
        if (cx) cx.innerHTML = cartaoProgresso(d);
        if (['concluido', 'aprovado', 'aguardando_aprovacao', 'rejeitado', 'erro', 'cancelado'].includes(d.estado)) {
          pararPoll();
          S.analiseCarregada = false;
          await carregarCanal(false);
          carregarAnalise(false);
          render();
          if (d.estado === 'aguardando_aprovacao') mostrar('Vídeo montado. Assista e aprove antes de publicar.', 'ok');
          else if (d.estado === 'aprovado') mostrar('Vídeo aprovado.', 'ok');
          else if (d.estado === 'concluido') mostrar('Vídeo pronto. Agende ou publique agora.', 'ok');
        }
      } catch (e) {
        S.erros = (S.erros || 0) + 1;
        if (S.erros > 4) { pararPoll(); mostrar('Perdi o contato com a produção: ' + e.message, 'erro'); }
      }
    }, 3000);
  }

  function pararPoll() { if (S.poll) { clearInterval(S.poll); S.poll = null; } }

  // ================================================================ agenda
  function preencherAgendar(pid, agora = false) {
    S.agendarAgora = !!agora;
    const prods = (S.dados.producoes || []).filter((p) => ['aprovado', 'concluido'].includes(p.estado) &&
      Object.keys((p.arquivos || {}).videos || {}).length);
    const selP = $('#agendarProducao'), selF = $('#agendarFormato'), plats = $('#agendarPlataformas');
    if (!prods.length) {
      $('#agendarSub').textContent = 'Nenhum vídeo aprovado com arquivo final. Aprove o vídeo antes de publicar.';
      selP.innerHTML = ''; selF.innerHTML = ''; plats.innerHTML = '';
      $('#agendarCriar').disabled = true;
      $('#agendarCriar').innerHTML = ic('relogio') + 'Agendar';
      return;
    }
    $('#agendarCriar').disabled = false;
    $('#agendarCriar').innerHTML = agora ? ic('play') + 'Publicar agora' : ic('relogio') + 'Agendar';
    selP.innerHTML = prods.map((p) => `<option value="${esc(p.id)}" ${p.id === pid ? 'selected' : ''}>${esc(p.titulo || p.id)}</option>`).join('');
    $('#agendarSub').textContent = agora
      ? 'Confira o formato e as plataformas. Ao confirmar, o vídeo vai para publicação imediatamente.'
      : 'Escolha o formato, as plataformas e a hora. O vídeo final de cada formato é publicado como está.';
    preencherFormatosAgendar();
    $('#agendarQuando').value = agora ? dtInput(Math.floor(Date.now() / 1000)) : dtInput();
    const p = prods.find((x) => x.id === (pid || selP.value)) || prods[0];
    $('#agendarTituloIn').value = p.titulo || '';
    const plano = p.plano || p;
    $('#agendarDescricao').value = plano.legenda || '';
    $('#agendarHashtags').value = (plano.hashtags || []).join(' ');
    $('#dlgAgendar').showModal();
  }

  function preencherFormatosAgendar() {
    const pid = $('#agendarProducao').value;
    const p = (S.dados.producoes || []).find((x) => x.id === pid);
    const videos = (p && p.arquivos && p.arquivos.videos) || {};
    const formats = (S.dados.formatos || []).filter((f) => videos[f.id]);
    const selF = $('#agendarFormato');
    selF.innerHTML = formats.map((f) => `<option value="${esc(f.id)}">${esc(f.nome)} · ${f.largura}x${f.altura}</option>`).join('');
    const plats = $('#agendarPlataformas');
    const escolhido = (formats[0] || {}).plataforma;
    plats.innerHTML = Object.keys(Rotulo).map((k) =>
      `<label class="cx-check"><input type="checkbox" data-agplat="${k}" ${k === escolhido ? 'checked' : ''}>${Rotulo[k]}</label>`).join('');
    atualizarAvisoAgendar();
  }

  function atualizarAvisoAgendar() {
    const pid = $('#agendarProducao').value;
    const fid = $('#agendarFormato').value;
    const p = (S.dados.producoes || []).find((x) => x.id === pid);
    const video = p && p.arquivos && p.arquivos.videos && p.arquivos.videos[fid];
    const cred = S.dados.credenciais || {};
    const marcadas = $$('[data-agplat]:checked').map((x) => x.dataset.agplat);
    const sem = marcadas.filter((k) => !(cred[k] && cred[k].configurado)).map((k) => Rotulo[k]);
    $('#agendarAviso').textContent = (video ? 'Arquivo: ' + video.split('/').pop() : 'Escolha um formato com vídeo pronto.') +
      (sem.length ? ' · sem conta conectada: ' + sem.join(', ') + ' (o agendamento fica esperando a conta).' : '');
  }

  async function agendar() {
    const plataformas = $$('[data-agplat]:checked').map((x) => x.dataset.agplat);
    if (!plataformas.length) { mostrar('Escolha pelo menos uma plataforma.', 'erro'); return; }
    const quando = $('#agendarQuando').value;
    if (!quando) { mostrar('Escolha a data e a hora.', 'erro'); return; }
    const bt = $('#agendarCriar');
    bt.disabled = true;
    try {
      const item = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/agenda', {
        producao_id: $('#agendarProducao').value,
        formato_id: $('#agendarFormato').value,
        plataformas: plataformas,
        quando: quando,
        titulo: $('#agendarTituloIn').value,
        descricao: $('#agendarDescricao').value,
        hashtags: tags($('#agendarHashtags').value),
      });
      if (S.agendarAgora && item && item.id) {
        await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/agenda/' + encodeURIComponent(item.id),
          { publicar_agora: true });
      }
      const eraAgora = S.agendarAgora;
      S.agendarAgora = false;
      $('#dlgAgendar').close();
      await carregarCanal(false);
      S.aba = 'agenda';
      render();
      mostrar(eraAgora ? 'Publicando agora. Acompanhe o estado na agenda.' : 'Publicação agendada.', 'ok');
    } catch (e) {
      mostrar('Não consegui agendar: ' + e.message, 'erro');
    } finally { bt.disabled = false; }
  }

  async function proximaParte(pid) {
    if (!confirm('Gerar a próxima parte com o mesmo elenco e estilo? Ela entra na fila agora.')) return;
    const bt = $('[data-acao="proxima-parte"][data-id="' + pid + '"]');
    if (bt) bt.disabled = true;
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' +
        encodeURIComponent(pid) + '/proxima-parte', {});
      S.producao = { ...r.producao, plano: r.plano };
      S.plano = r.plano;
      S.briefing = r.plano && r.plano.titulo ? ('Continuação de ' + r.plano.titulo) : '';
      render();
      pollProducao(r.producao.id);
      mostrar('Próxima parte começou a ser produzida.', 'ok');
    } catch (e) {
      mostrar('Não consegui gerar a próxima parte: ' + e.message, 'erro');
    } finally { if (bt) bt.disabled = false; }
  }

  async function aprovarProducao(pid) {
    if (!confirm('Aprovar este vídeo? As imagens, vozes por cena e temporários serão apagados. Ficam só os vídeos, a legenda e os personagens.')) return;
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' + encodeURIComponent(pid) + '/aprovar',
        { aprovado: true, limpar: true });
      S.producao = (S.producao && S.producao.id === pid) ? { ...S.producao, ...r } : r;
      S.analiseCarregada = false;
      await carregarCanal(false);
      carregarAnalise(false);
      render();
      mostrar('Vídeo aprovado.' + (r.bytes_liberados ? ' ' + nf1.format(r.bytes_liberados / 1048576) + ' MB liberados.' : ''), 'ok');
    } catch (e) {
      mostrar('Não consegui aprovar: ' + e.message, 'erro');
    }
  }

  async function rejeitarProducao(pid) {
    if (!confirm('Rejeitar este vídeo? Ele não será publicado e você pode gerar outro.')) return;
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' + encodeURIComponent(pid) + '/aprovar',
        { aprovado: false });
      S.producao = r;
      await carregarCanal(false);
      render();
      mostrar('Vídeo rejeitado. Nada foi publicado.', 'ok');
    } catch (e) {
      mostrar('Não consegui rejeitar: ' + e.message, 'erro');
    }
  }

  async function gerarRetratos() {
    const disponiveis = (S.dados && S.dados.personagens_disponiveis) || [];
    const retratos = (S.dados && S.dados.retratos) || {};
    const faltam = disponiveis.filter((p) => !retratos[p.nome]);
    if (!faltam.length) { mostrar('Todos os personagens já têm retrato.', 'ok'); return; }
    const bt = $('[data-acao="gerar-retratos"]');
    if (bt) bt.disabled = true;
    mostrar('Gerando ' + faltam.length + ' retrato(s) com a imagem local…', 'ok');
    const erros = [];
    for (const p of faltam) {
      try {
        await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/personagens/retrato', {
          nome: p.nome, visual: p.visual, descricao: p.descricao,
          estilo: ((S.dados.producao || {}).estilo) || 'auto',
        });
      } catch (e) { erros.push(p.nome + ': ' + e.message); }
    }
    await carregarCanal(false);
    render();
    mostrar(erros.length ? 'Retratos gerados com avisos. ' + erros.join(' · ') : 'Retratos gerados.', erros.length ? 'erro' : 'ok');
  }

  async function gerarPersonagens() {
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/personagens/gerar', {});
      S.personagensNovos = (r.novos || []).map((p) => p.nome);
      await carregarCanal(false);
      render();
      mostrar((r.novos || []).length + ' personagem(ns) criado(s) e salvo(s) no canal.', 'ok');
    } catch (e) {
      mostrar('Não consegui criar personagens: ' + e.message, 'erro');
    }
  }

  async function atualizarAnalise() {
    const bt = $('[data-acao="atualizar-analise"]');
    if (bt) bt.disabled = true;
    mostrar('Coletando números no YouTube, TikTok, Instagram e Facebook… pode levar alguns segundos.', 'ok');
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/analytics/coletar',
        { dias: S.analiseDias });
      S.analise = r.dashboard || S.analise;
      S.analiseCarregada = true;
      render();
      const res = ((r.resultado || {}).resultados) || {};
      const erros = Object.entries(res).filter(([, v]) => !v.ok && v.erro)
        .map(([p, v]) => (Rotulo[p] || p) + ': ' + v.erro);
      mostrar(erros.length ? 'Números atualizados com avisos. ' + erros.join(' · ') : 'Números atualizados.', erros.length ? 'erro' : 'ok');
    } catch (e) {
      mostrar('Não consegui coletar: ' + e.message, 'erro');
    } finally { if (bt) bt.disabled = false; }
  }

  // ================================================================ contexto com IA
  const CAMPOS_IA = {
    tema: '#ajTema', publico: '#ajPublico', tom: '#ajTom', identidade_visual: '#ajVisual',
    regras: '#ajRegras', nao_fazer: '#ajNao', referencias: '#ajRef',
    chamada_final: '#ajCta', hashtags: '#ajHashtags',
  };

  function statusIA(msg, erro) {
    const el = $('#cxIaStatus');
    if (!el) return;
    el.hidden = !msg;
    el.textContent = msg || '';
    el.className = 'nota cx-ia-status' + (erro ? ' erro' : '');
  }

  async function melhorarCampo(botao) {
    const campo = botao.dataset.campo;
    const alvo = $(CAMPOS_IA[campo]);
    if (!alvo) return;
    botao.disabled = true;
    statusIA('Lendo o campo com a IA local…');
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/contexto/ia',
        { campo, texto: alvo.value || '' });
      alvo.value = r.texto || '';
      statusIA('Pronto. Revise o texto e clique em Salvar canal.');
    } catch (e) {
      statusIA('A IA não conseguiu melhorar: ' + e.message, true);
    } finally { botao.disabled = false; }
  }

  async function gerarContexto() {
    const nome = (($('#ajNome') || {}).value || '').trim();
    const tema = (($('#ajTema') || {}).value || '').trim();
    if (!nome) { mostrar('Dê um nome ao canal antes de gerar o contexto.', 'erro'); return; }
    const base = nome.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z]/g, '');
    const generico = ['', 'canal', 'meucanal', 'novocanal', 'teste', 'canal1', 'canal2', 'canal3'].includes(base);
    if (generico && tema.length < 12) {
      mostrar('O nome não diz do que o canal trata. Escreva uma descrição no campo Tema antes de gerar.', 'erro');
      const t = $('#ajTema'); if (t) t.focus();
      return;
    }
    const bt = $('[data-acao="ia-contexto"]');
    if (bt) bt.disabled = true;
    statusIA('Gerando o contexto do canal com a IA local… pode levar até um minuto.');
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/contexto/ia',
        { gerar: true, nome, tema });
      const c = r.contexto || {};
      Object.entries(CAMPOS_IA).forEach(([k, sel]) => {
        const el = $(sel);
        if (!el || c[k] == null) return;
        el.value = Array.isArray(c[k]) ? (k === 'hashtags' ? c[k].join(' ') : c[k].join('\n')) : c[k];
      });
      if (Array.isArray(c.personagens)) {
        const cx = $('#cxPersonagensAjustes');
        if (cx) cx.innerHTML = c.personagens.map(linhaPersonagem).join('');
        posRender();
      }
      statusIA('Contexto gerado. Revise os campos e clique em Salvar canal.');
    } catch (e) {
      statusIA('A IA não conseguiu gerar: ' + e.message, true);
    } finally { if (bt) bt.disabled = false; }
  }

  async function sugerirDescricao() {
    const nome = (($('#canalNovoNome') || {}).value || '').trim();
    const texto = (($('#canalNovoTema') || {}).value || '').trim();
    const status = $('#canalNovoStatus');
    if (!nome) {
      if (status) { status.hidden = false; status.textContent = 'Dê um nome ao canal primeiro.'; status.className = 'nota erro'; }
      return;
    }
    const bt = $('[data-acao="sugerir-descricao"]');
    if (bt) bt.disabled = true;
    if (status) { status.hidden = false; status.className = 'nota'; status.textContent = 'Escrevendo a descrição com a IA local…'; }
    try {
      const r = await pedir('/api/canais/sugerir', { nome, texto });
      $('#canalNovoTema').value = r.texto || '';
      if (status) { status.textContent = 'Descrição gerada. Ajuste se quiser.'; }
    } catch (e) {
      if (status) { status.textContent = e.message; status.className = 'nota erro'; }
    } finally { if (bt) bt.disabled = false; }
  }

  function atualizarHoras() {
    const hidden = $('#ajHorarios');
    if (!hidden) return;
    hidden.value = $$('#cxHorarios .cx-hora').map((x) => x.dataset.hora).join(', ');
    const sel = $('#ajHoraNova');
    if (!sel) return;
    const usadas = $$('#cxHorarios .cx-hora').map((x) => x.dataset.hora);
    const atual = sel.value;
    const opcoes = HORAS.filter((h) => !usadas.includes(h));
    sel.innerHTML = opcoes.map((h) => `<option>${h}</option>`).join('');
    if (opcoes.includes(atual)) sel.value = atual;
    const add = sel.closest('.cx-hora-add') && sel.closest('.cx-hora-add').querySelector('button');
    if (add) add.disabled = !opcoes.length;
  }

  // ================================================================ salvar ajustes
  function valoresConfig() {
    const d = S.dados;
    const formatos = $$('#cxFormatos [data-fmt-row]').map((row, i) => {
      const base = (d.formatos || []).find((x) => x.id === row.dataset.fid) || {};
      const largura = Number(($('[data-fmt-largura]', row) || {}).value) || 1080;
      const altura = Number(($('[data-fmt-altura]', row) || {}).value) || 1920;
      return {
        ...base,
        id: row.dataset.fid || ('formato-' + Date.now() + '-' + i),
        nome: ($('[data-fmt-nome]', row) || {}).value || 'Formato',
        plataforma: ($('[data-fmt-plataforma]', row) || {}).value || 'youtube',
        largura, altura,
        proporcao: largura === altura ? '1:1' : largura > altura ? '16:9' : '9:16',
        legendas: !!($('[data-fmt-legendas]', row) || {}).checked,
        ativo: !!($('[data-fmt-ativo]', row) || {}).checked,
      };
    });
    return {
      nome: ($('#ajNome') || {}).value || d.nome,
      cor: ($('#ajCor') || {}).value || d.cor,
      voz: { ...(d.voz || {}), voz_id: ($('#ajVoz') || {}).value || '', idioma: ($('#ajIdioma') || {}).value || 'pt' },
      producao: { ...(d.producao || {}),
        duracao_alvo: Number(($('#ajDuracao') || {}).value) || 45,
        qualidade: ($('#ajQualidade') || {}).value || 'Normal',
        preset_imagem: ($('#ajPreset') || {}).value || 'z_image_turbo',
        estilo: ($('#ajEstilo') || {}).value || 'auto',
        imagens_por_formato: ($('#ajImagensPorFormato') || {}).value || 'auto',
        legendas: !!($('#ajLegendas') || {}).checked,
        falar_cenas: !!($('#ajFalar') || {}).checked },
      formatos,
      publicacao: { ...(d.publicacao || {}),
        automatico: !!($('#ajAuto') || {}).checked,
        aprovacao_obrigatoria: true,
        horarios: String(($('#ajHorarios') || {}).value || '').split(',').map((x) => x.trim()).filter(Boolean),
        plataformas: $$('[data-pubplat]:checked').map((x) => x.dataset.pubplat),
        visibilidade: ($('#ajVisibilidade') || {}).value || 'public',
        hashtags: tags(($('#ajTagsAgenda') || {}).value || '') },
      analytics: { ...(d.analytics || {}), meta_receita: Number(($('#ajMeta') || {}).value) || 0,
        automatico: !!($('#ajAnaliseAuto') || {}).checked },
    };
  }

  function valoresContexto() {
    return {
      tema: ($('#ajTema') || {}).value || '',
      publico: ($('#ajPublico') || {}).value || '',
      tom: ($('#ajTom') || {}).value || '',
      idioma: ($('#ajIdioma') || {}).value || 'pt',
      identidade_visual: ($('#ajVisual') || {}).value || '',
      regras: linhas(($('#ajRegras') || {}).value || ''),
      nao_fazer: linhas(($('#ajNao') || {}).value || ''),
      referencias: linhas(($('#ajRef') || {}).value || ''),
      chamada_final: ($('#ajCta') || {}).value || '',
      hashtags: tags(($('#ajHashtags') || {}).value || ''),
      personagens: $$('#cxPersonagensAjustes .cx-persona').map((el) => ({
        nome: ($('.cx-pers-nome', el) || {}).value || '',
        papel: ($('.cx-pers-papel', el) || {}).value || 'principal',
        descricao: ($('.cx-pers-desc', el) || {}).value || '',
        visual: ($('.cx-pers-visual', el) || {}).value || '',
      })).filter((x) => x.nome),
    };
  }

  async function salvarAjustes() {
    const bt = $('[data-acao="salvar-ajustes"]');
    if (bt) bt.disabled = true;
    try {
      await pedir('/api/canais/' + encodeURIComponent(S.atual),
        { config: valoresConfig(), contexto: valoresContexto() });
      await carregarCanais();
      S.aba = 'ajustes';
      render();
      mostrar('Canal salvo.', 'ok');
    } catch (e) {
      mostrar('Não consegui salvar: ' + e.message, 'erro');
    } finally { if (bt) bt.disabled = false; }
  }

  async function salvarCred(plat) {
    const form = $(`[data-cred="${plat}"]`);
    if (!form) return;
    const campos = {};
    $$('[data-cred-campo]', form).forEach((el) => {
      if (el.type === 'checkbox') {
        campos[el.dataset.credCampo] = el.checked ? 'true' : 'false';
        return;
      }
      const v = String(el.value || '').trim();
      if (v) campos[el.dataset.credCampo] = v;
    });
    if (!Object.keys(campos).length) { mostrar('Preencha pelo menos um campo.', 'erro'); return; }
    try {
      await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/credenciais',
        { plataforma: plat, campos });
      await carregarCanal(false);
      S.aba = 'ajustes';
      render();
      mostrar('Conta de ' + (Rotulo[plat] || plat) + ' atualizada.', 'ok');
    } catch (e) {
      mostrar('Não consegui salvar a conta: ' + e.message, 'erro');
    }
  }

  // ================================================================ ações
  function montar() {
    if (S.iniciado) return;
    S.iniciado = true;
    $('#canaisAtualizar') && $('#canaisAtualizar').addEventListener('click', async () => {
      S.analiseCarregada = false;
      await carregarCanais();
    });
    $('#canaisNovo') && $('#canaisNovo').addEventListener('click', abrirNovoCanal);
    $('#canalNovoCancelar') && $('#canalNovoCancelar').addEventListener('click', () => $('#dlgCanalNovo').close());
    $('#canalNovoCriar') && $('#canalNovoCriar').addEventListener('click', criarCanal);
    $('#agendarCancelar') && $('#agendarCancelar').addEventListener('click', () => {
      S.agendarAgora = false;
      $('#agendarCriar').innerHTML = ic('relogio') + 'Agendar';
      $('#dlgAgendar').close();
    });
    $('#agendarCriar') && $('#agendarCriar').addEventListener('click', agendar);
    $('#agendarProducao') && $('#agendarProducao').addEventListener('change', () => {
      preencherFormatosAgendar();
      const p = (S.dados.producoes || []).find((x) => x.id === $('#agendarProducao').value);
      if (p) $('#agendarTituloIn').value = p.titulo || '';
    });
    $('#agendarFormato') && $('#agendarFormato').addEventListener('change', () => {
      const f = (S.dados.formatos || []).find((x) => x.id === $('#agendarFormato').value);
      if (f) $$('[data-agplat]').forEach((x) => { x.checked = x.dataset.agplat === f.plataforma; });
      atualizarAvisoAgendar();
    });
    $('#agendarPlataformas') && $('#agendarPlataformas').addEventListener('change', atualizarAvisoAgendar);

    document.addEventListener('click', aoClicar);
    document.addEventListener('pointermove', tooltipGrafico);
    document.addEventListener('pointerleave', () => {
      $$('.cx-tip').forEach((t) => t.classList.remove('on'));
    }, true);
  }

  async function aoClicar(ev) {
    const b = ev.target.closest('[data-canal], [data-aba], [data-acao], [data-dias]');
    if (!b) return;
    if (b.dataset.canal) { ev.preventDefault(); await selecionar(b.dataset.canal); return; }
    if (b.dataset.aba) { ev.preventDefault(); S.aba = b.dataset.aba; render(); if (S.aba === 'analise') carregarAnalise(true); return; }
    if (b.dataset.dias) { ev.preventDefault(); S.analiseDias = Number(b.dataset.dias) || 30; S.analiseCarregada = false; S.analise = null; render(); carregarAnalise(true); return; }
    const acao = b.dataset.acao;
    if (!acao) return;
    ev.preventDefault();
    if (acao === 'novo-canal') { abrirNovoCanal(); return; }
    if (acao === 'ir-produzir') { S.aba = 'produzir'; render(); return; }
    if (acao === 'ir-ajustes') { S.aba = 'ajustes'; render(); return; }
    if (acao === 'abrir-agenda') { S.aba = 'agenda'; render(); return; }
    if (acao === 'gerar-plano') { await gerarPlano(); return; }
    if (acao === 'produzir') { await produzir(); return; }
    if (acao === 'produzir-direto') { await produzirDireto(); return; }
    if (acao === 'gerar-personagens') { await gerarPersonagens(); return; }
    if (acao === 'gerar-retratos') { await gerarRetratos(); return; }
    if (acao === 'atualizar-analise') { await atualizarAnalise(); return; }
    if (acao === 'ia-campo') { await melhorarCampo(b); return; }
    if (acao === 'ia-contexto') { await gerarContexto(); return; }
    if (acao === 'sugerir-descricao') { await sugerirDescricao(); return; }
    if (acao === 'ler-inspiracao') { await lerInspiracao(); return; }
    if (acao === 'add-hora') {
      const h = ($('#ajHoraNova') || {}).value || '06:00';
      const atual = $$('#cxHorarios .cx-hora').map((x) => x.dataset.hora);
      if (!atual.includes(h)) {
        const add = $('#cxHorarios .cx-hora-add');
        if (add) add.insertAdjacentHTML('beforebegin', chipHora(h));
      }
      atualizarHoras();
      return;
    }
    if (acao === 'del-hora') {
      const chip = b.closest('.cx-hora');
      if (chip) chip.remove();
      atualizarHoras();
      return;
    }
    if (acao === 'add-cena') {
      const p = lerPlano();
      p.cenas.push({ n: p.cenas.length + 1, fala: '', imagem: '', personagem: '' });
      S.plano = p; render(); return;
    }
    if (acao === 'del-cena') {
      const p = lerPlano();
      const i = Number(b.closest('.cx-cena').dataset.cena);
      p.cenas.splice(i, 1);
      S.plano = p; render(); return;
    }
    if (acao === 'add-persona') {
      const p = lerPlano(); p.personagens.push({ nome: '', descricao: '', visual: '' });
      S.plano = p; render(); return;
    }
    if (acao === 'del-persona') {
      if (b.closest('#cxPersonagensAjustes')) {
        b.closest('.cx-persona').remove();
        return;
      }
      const p = lerPlano(); const i = Number(b.closest('.cx-persona').dataset.persona);
      p.personagens.splice(i, 1); S.plano = p; render(); return;
    }
    if (acao === 'add-formato') {
      const cx = $('#cxFormatos');
      if (cx) { cx.insertAdjacentHTML('beforeend', linhaFormato({ nome: 'Novo formato', plataforma: 'youtube', largura: 1080, altura: 1920, legendas: true, ativo: true })); posRender(); }
      return;
    }
    if (acao === 'del-formato') {
      const row = b.closest('.cx-formato');
      if (row) row.remove();
      return;
    }
    if (acao === 'add-persona-ajustes') {
      const cx = $('#cxPersonagensAjustes');
      if (!cx) return;
      const i = cx.children.length;
      const div = document.createElement('div');
      div.innerHTML = linhaPersonagem({}, i);
      cx.appendChild(div.firstElementChild);
      posRender(); return;
    }
    if (acao === 'ver-producao') {
      try {
        S.producao = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' + encodeURIComponent(b.dataset.id));
        S.aba = 'produzir'; render(); pollProducao(S.producao.id);
      } catch (e) { mostrar(e.message, 'erro'); }
      return;
    }
    if (acao === 'cancelar-producao') {
      if (!confirm('Cancelar esta produção? O vídeo que está sendo feito agora é interrompido.')) return;
      await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/producoes/' + encodeURIComponent(b.dataset.id), { cancelar: true });
      mostrar('Cancelamento pedido.', 'ok'); return;
    }
    if (acao === 'abrir-agendar') { preencherAgendar(b.dataset.id, b.dataset.agora === '1'); return; }
    if (acao === 'aprovar-producao') { await aprovarProducao(b.dataset.id); return; }
    if (acao === 'rejeitar-producao') { await rejeitarProducao(b.dataset.id); return; }
    if (acao === 'proxima-parte') { await proximaParte(b.dataset.id); return; }
    if (acao === 'publicar-agora') {
      try { await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/agenda/' + encodeURIComponent(b.dataset.id), { publicar_agora: true });
        mostrar('Publicando agora. A agenda mostra o resultado.', 'ok'); await carregarCanal(false); render();
      } catch (e) { mostrar(e.message, 'erro'); }
      return;
    }
    if (acao === 'cancelar-agenda') {
      try { await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/agenda/' + encodeURIComponent(b.dataset.id), { cancelar: true });
        await carregarCanal(false); render();
      } catch (e) { mostrar(e.message, 'erro'); }
      return;
    }
    if (acao === 'salvar-ajustes') { await salvarAjustes(); return; }
    if (acao === 'salvar-cred') { await salvarCred(b.dataset.plat); return; }
    if (acao === 'importar') { await importarMetricas(); return; }
  }

  function abrirNovoCanal() {
    $('#canalNovoNome').value = '';
    $('#canalNovoTema').value = '';
    const st = $('#canalNovoStatus');
    if (st) { st.hidden = true; st.textContent = ''; st.className = 'nota'; }
    $('#dlgCanalNovo').showModal();
    setTimeout(() => $('#canalNovoNome').focus(), 50);
  }

  async function criarCanal() {
    const nome = ($('#canalNovoNome').value || '').trim();
    if (!nome) { mostrar('Dê um nome ao canal.', 'erro'); return; }
    const bt = $('#canalNovoCriar');
    bt.disabled = true;
    try {
      const c = await pedir('/api/canais', { nome, contexto: { tema: ($('#canalNovoTema').value || '').trim() } });
      $('#dlgCanalNovo').close();
      await carregarCanais();
      S.atual = c.id;
      try { localStorage.setItem('forja_canal_atual', c.id); } catch (e) { /* sem armazenamento */ }
      await carregarCanal(false);
      S.aba = 'ajustes';
      render();
      mostrar('Canal criado. Complete o contexto e as contas.', 'ok');
    } catch (e) {
      mostrar('Não consegui criar: ' + e.message, 'erro');
    } finally { bt.disabled = false; }
  }

  async function importarMetricas() {
    const texto = ($('#cxImportar') || {}).value || '';
    if (!texto.trim()) { mostrar('Cole o CSV ou o JSON antes de importar.', 'erro'); return; }
    try {
      const r = await pedir('/api/canais/' + encodeURIComponent(S.atual) + '/analytics',
        { texto, formato: 'auto' });
      S.analiseCarregada = false;
      S.analise = null;
      await carregarAnalise(false);
      render();
      mostrar(r.importados + ' linha(s) lida(s), ' + r.novos + ' nova(s).', 'ok');
    } catch (e) {
      mostrar('A importação falhou: ' + e.message, 'erro');
    }
  }

  // ================================================================ tooltips
  function tooltipGrafico(ev) {
    const cx = ev.target.closest('.cx-chart');
    if (!cx) {
      $$('.cx-tip').forEach((t) => t.classList.remove('on'));
      return;
    }
    const info = S.charts[cx.dataset.chart];
    const tip = $('.cx-tip', cx);
    if (!info || !tip) return;
    const rect = cx.getBoundingClientRect();
    const px = (ev.clientX - rect.left) / rect.width * info.W;
    let melhor = 0, dist = Infinity;
    info.serie.forEach((s, i) => {
      const d = Math.abs(info.x(i) - px);
      if (d < dist) { dist = d; melhor = i; }
    });
    const s = info.serie[melhor];
    if (!s) return;
    tip.textContent = (s.dia || '') + ' · ' + (info.campo === 'receita' ? money(s[info.campo]) : nf.format(s[info.campo] || 0));
    tip.style.left = ((info.x(melhor) / info.W) * rect.width) + 'px';
    tip.style.top = ((info.y(Number(s[info.campo]) || 0) / info.H) * rect.height) + 'px';
    tip.classList.add('on');
  }

  // ================================================================ ícones
  function posRender() {
    $$('#vCanais [data-ic]').forEach((el) => { if (!el.firstElementChild) el.innerHTML = ic(el.dataset.ic); });
    if ($('#ajHoraNova')) atualizarHoras();
    // tooltip das barras de horário
    const barras = $('#cxBarrasHoras');
    if (barras) {
      const tip = $('#cxTipHoras');
      barras.addEventListener('pointerover', (ev) => {
        const b = ev.target.closest('.b');
        if (!b || !tip) return;
        tip.textContent = String(b.dataset.hora).padStart(2, '0') + ':00 · média ' +
          nf.format(Number(b.dataset.views) || 0) + ' views em ' + (b.dataset.videos || 0) + ' vídeo(s)';
        const r = barras.getBoundingClientRect();
        tip.style.left = (ev.clientX - r.left) + 'px';
        tip.style.top = (ev.clientY - r.top - 8) + 'px';
        tip.classList.add('on');
      });
      barras.addEventListener('pointerleave', () => tip && tip.classList.remove('on'));
    }
  }

  window.CANAIS = { abrir, carregar: carregarCanais };
})();
