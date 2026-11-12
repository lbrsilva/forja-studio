/* A FILA: tudo que esta sendo gerado nesta maquina, venha de onde vier. (07/11/2026)
 *
 * Ele pediu: "cria um local para fila de geracao para ver o que esta sendo gerado mesmo que
 * seja o Claude.ia ou o GPT ou qualquer fluxo mande".
 *
 * Da para saber de onde veio porque TODO prompt que este painel manda leva um carimbo
 * dentro (extra_pnginfo.estudio_local). O que chega sem o carimbo veio de fora - e e
 * justamente o que ele quer enxergar.
 *
 * ⚠️ A narracao NAO entra: o VoiceStudio nao tem fila para consultar. A tela diz isso em vez
 * de deixar a pessoa achar que a lista esta completa.
 */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  let tic = null;

  function quando(seg) {
    if (!seg) return '';
    const d = Math.max(0, Math.round(Date.now() / 1000 - seg));
    if (d < 60) return 'há ' + d + ' s';
    return 'há ' + Math.floor(d / 60) + ' min ' + String(d % 60).padStart(2, '0') + ' s';
  }

  function cartao(i) {
    const el = document.createElement('div');
    el.className = 'fila-item' + (i.estado === 'rodando' ? ' rodando' : '');
    const etiqueta = i.de === 'estudio' ? 'deste painel'
      : i.de === 'musica' ? 'painel de música' : 'DE FORA';
    const modelos = (i.modelos || []).filter(Boolean).join(' · ');
    el.innerHTML =
      '<div class="fila-item-cab">' +
        '<span class="fila-estado">' + (i.estado === 'rodando' ? '● gerando'
          : '○ na fila' + (i.numero ? ' · ' + i.numero + 'º' : '')) + '</span>' +
        '<span class="fila-de' + (i.de === 'fora' ? ' fora' : '') + '">' + etiqueta + '</span>' +
      '</div>' +
      '<p class="fila-titulo"></p>' +
      (modelos ? '<p class="fila-modelos"></p>' : '') +
      (i.prompt ? '<p class="fila-prompt"></p>' : '') +
      '<p class="fila-rodape"><span class="fila-quem"></span>' +
        (i.comecou ? '<span class="fila-tempo">' + quando(i.comecou) + '</span>' : '') + '</p>';
    // tudo por textContent: estes textos vem de fora (de outro programa), nunca como HTML
    $('.fila-titulo', el).textContent = i.titulo || 'trabalho';
    if (modelos) $('.fila-modelos', el).textContent = modelos;
    if (i.prompt) $('.fila-prompt', el).textContent = i.prompt;
    $('.fila-quem', el).textContent = i.quem || '';
    return el;
  }

  const ABAS = [['todos', 'Todos'], ['imagem', 'Imagem'], ['video', 'Vídeo'], ['pessoa', 'Pessoa falando'],
    ['narracao', 'Narração'], ['musica', 'Música'], ['outros', 'Outros']];
  const ULT = { vivos: [], hist: [] };
  let aba = 'todos';
  try { aba = sessionStorage.getItem('forja_fila_aba') || 'todos'; } catch (e) { /* sem armazenamento */ }

  function tipoDe(i) {
    if (i.tipo) return i.tipo;
    if (i.fonte === 'voz') return 'narracao';
    if (i.fonte === 'musica') return 'musica';
    const s = String(i.saida || '').toLowerCase();
    return s.startsWith('imagem') ? 'imagem' : s.startsWith('v') ? 'video' : 'outros';
  }
  const doTipo = (lista) => (aba === 'todos' ? lista : lista.filter((i) => tipoDe(i) === aba));

  function desenharAbas() {
    const caixa = $('#filaAbas');
    if (!caixa) return;
    const todos = [...ULT.vivos, ...ULT.hist];
    const semMusica = typeof G !== 'undefined' && G.inicio && G.inicio.tem_musica === false;
    caixa.innerHTML = '';
    ABAS.forEach(([chave, rotulo]) => {
      const n = chave === 'todos' ? todos.length : todos.filter((i) => tipoDe(i) === chave).length;
      if ((chave === 'musica' && semMusica && !n) || (chave === 'outros' && !n)) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'tab');
      b.dataset.tipo = chave;
      b.setAttribute('aria-selected', String(chave === aba));
      b.textContent = rotulo + ' ';
      const c = document.createElement('span');
      c.className = 'fila-aba-n';
      c.textContent = n;
      b.append(c);
      caixa.append(b);
    });
  }

  function desenharVivos() {
    const lista = $('#filaLista');
    const itens = doTipo(ULT.vivos);
    lista.innerHTML = '';
    if (!itens.length) {
      const vazio = document.createElement('p');
      vazio.className = 'fila-vazio';
      vazio.textContent = aba === 'todos' ? 'Nada sendo gerado agora.' : 'Nada sendo gerado agora nesta aba.';
      lista.append(vazio);
    } else {
      itens.forEach((i) => lista.append(cartao(i)));
    }
  }

  function desenharHist() {
    const lista = $('#filaHistLista');
    const itens = doTipo(ULT.hist);
    lista.innerHTML = '';
    if (!itens.length) {
      const v = document.createElement('p');
      v.className = 'fila-vazio';
      v.textContent = ULT.limpoEm ? 'Histórico limpo. O que for gerado daqui para a frente entra aqui.'
        : aba === 'todos' ? 'Nada gerado ainda.' : 'Nada gerado ainda nesta aba.';
      lista.append(v);
      return;
    }
    itens.forEach((i) => lista.append(cartaoHist(i)));
  }

  function trocarAba(chave) {
    aba = chave;
    try { sessionStorage.setItem('forja_fila_aba', chave); } catch (e) { /* so nao lembra */ }
    desenharAbas();
    desenharVivos();
    desenharHist();
  }

  let ultimaAmostra = null;
  let nDown = 0;
  const gb = (b) => (b / 1e9).toLocaleString('pt-BR', { maximumFractionDigits: 1 });

  function duracao(seg) {
    if (!isFinite(seg) || seg < 0) return '';
    if (seg < 90) return Math.round(seg) + ' s';
    if (seg < 5400) return Math.round(seg / 60) + ' min';
    return Math.floor(seg / 3600) + ' h ' + String(Math.round((seg % 3600) / 60)).padStart(2, '0') + ' min';
  }

  async function puxarDown() {
    let prog, tam = {};
    try {
      const r = await fetch('/api/ias/progresso');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      prog = await r.json();
    } catch (e) { return; }
    const fila = prog.fila || [], agora = prog.baixando;
    nDown = fila.length;
    const caixa = $('#filaDown');
    const mostrar = !!(agora || fila.length || prog.erro);
    caixa.hidden = !mostrar;
    if (!mostrar) { ultimaAmostra = null; atualizarContador(0); return; }
    if (fila.length) {
      try {
        const r = await fetch('/api/ias');
        if (r.ok) Object.values((await r.json()).ias || {}).forEach((i) => { if (i.nome) tam[i.nome] = i.gb_falta; });
      } catch (e) { /* so o tamanho some */ }
    }
    const blocoAgora = $('#filaDownAgora');
    blocoAgora.innerHTML = '';
    if (agora) {
      const pct = agora.total ? Math.min(100, Math.round((agora.baixados / agora.total) * 100)) : 0;
      const t = Date.now() / 1000;
      let vel = null;
      if (ultimaAmostra && ultimaAmostra.arq === agora.arquivo && agora.baixados >= ultimaAmostra.b && t - ultimaAmostra.t > 0.5) {
        const v = (agora.baixados - ultimaAmostra.b) / (t - ultimaAmostra.t);
        vel = ultimaAmostra.v ? ultimaAmostra.v * 0.6 + v * 0.4 : v;
      }
      ultimaAmostra = { arq: agora.arquivo, b: agora.baixados, t, v: vel };
      const el = document.createElement('div');
      el.className = 'fila-down-item';
      el.innerHTML = '<p class="fila-down-nome"></p><p class="fila-down-arq"></p>'
        + '<div class="fila-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>'
        + '<div class="fila-down-info"></div>';
      $('.fila-down-nome', el).textContent = '⬇ ' + (agora.ia || '');
      $('.fila-down-arq', el).textContent = agora.arquivo || '';
      $('.fila-barra', el).setAttribute('aria-valuenow', pct);
      $('.fila-barra > i', el).style.width = pct + '%';
      const info = [pct + '%', gb(agora.baixados) + ' de ' + gb(agora.total) + ' GB'];
      if (vel) {
        info.push((vel / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' MB/s');
        if (agora.total) info.push('faltam ~' + duracao((agora.total - agora.baixados) / vel));
      }
      if (agora.continuou) info.push('continuando de onde parou');
      $('.fila-down-info', el).textContent = info.join(' · ');
      blocoAgora.append(el);
    } else {
      ultimaAmostra = null;
      const p = document.createElement('p');
      p.className = 'nota';
      p.textContent = prog.erro ? 'Os downloads pararam por causa do erro abaixo. Corrija e clique em baixar de novo na IA.' : (fila.length ? 'Preparando o próximo download…' : '');
      blocoAgora.append(p);
    }
    const prox = fila.filter((n) => !agora || n !== agora.ia);
    const blocoProx = $('#filaDownProx');
    blocoProx.innerHTML = '';
    if (prox.length) {
      const h = document.createElement('p');
      h.className = 'fila-down-tit';
      h.textContent = 'Próximos na fila (' + prox.length + ')';
      const ul = document.createElement('ul');
      ul.className = 'fila-down-prox';
      prox.forEach((n, i) => {
        const li = document.createElement('li');
        const nome = document.createElement('strong');
        nome.textContent = (i + 1) + '. ' + n;
        const sz = document.createElement('span');
        sz.textContent = tam[n] ? 'falta ' + tam[n].toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' GB' : '';
        li.append(nome, sz);
        ul.append(li);
      });
      blocoProx.append(h, ul);
    }
    $('#filaDownErro').textContent = prog.erro ? 'O último download parou: ' + prog.erro : '';
    atualizarContador(nDown);
  }

  let nTrabalhos = 0;
  function atualizarContador(extra) {
    const cont = $('#navFilaN');
    const n = nTrabalhos + (extra || 0);
    if (cont) { cont.textContent = n || ''; cont.hidden = !n; }
  }

  async function puxar() {
    let d;
    try {
      const r = await fetch('/api/fila');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      d = await r.json();
    } catch (e) {
      $('#filaQuando').textContent = 'Não consegui ler a fila: ' + String(e.message || e);
      return;
    }
    const todos = d.itens || [];
    const comfyFora = todos.some((i) => i.fonte === 'comfyui' && i.estado === 'erro');
    const itens = todos.filter((i) => !(i.fonte === 'comfyui' && i.estado === 'erro'));
    ULT.vivos = itens;
    desenharVivos();
    desenharAbas();
    const n = itens.filter((i) => i.estado === 'rodando' || i.estado === 'fila').length;
    nTrabalhos = n;
    atualizarContador(nDown);
    $('#filaQuando').textContent = [comfyFora ? 'ComfyUI desligada' : '', n
      ? n + (n === 1 ? ' trabalho' : ' trabalhos') : '', 'atualiza sozinho'].filter(Boolean).join(' · ');
    $('#filaAviso').textContent = d.aviso_narracao || '';
  }

  // ------------------------------------------------------------ o historico
  // "Deixa um historico do que foi gerado sempre e uma opcao de limpar o historico."
  // O historico da ComfyUI rotaciona (ela guarda os ultimos e joga o resto fora); este
  // acumula no nosso arquivo, e inclui o que veio de FORA, que o painel nunca registrou.
  function quandoData(seg) {
    if (!seg) return '';
    const d = new Date(seg * 1000), hoje = new Date();
    const hm = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    if (d.toDateString() === hoje.toDateString()) return 'hoje ' + hm;
    return String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0') + ' ' + hm;
  }

  function cartaoHist(i) {
    const el = document.createElement('div');
    el.className = 'fila-hist-item' + (i.deu_certo ? '' : ' falhou');
    const img = (i.arquivos || []).find((a) => /\.(png|jpe?g|webp|gif)$/i.test(a.nome || ''));
    const vid = !img && (i.arquivos || []).find((a) => /\.(mp4|webm|mov|m4v)$/i.test(a.nome || ''));
    el.innerHTML =
      (img ? '<img class="fila-hist-mini" loading="lazy" alt="">'
        : vid ? '<video class="fila-hist-mini" muted playsinline preload="metadata" aria-hidden="true"></video>'
        : '<div class="fila-hist-mini vazia"></div>') +
      '<div class="fila-hist-txt">' +
        '<p class="fila-hist-titulo"></p>' +
        '<p class="fila-hist-sub"></p>' +
      '</div>' +
      '<span class="fila-de' + (i.de === 'fora' ? ' fora' : '') + '"></span>';
    if (img) el.querySelector('img').src = img.url;
    if (vid) el.querySelector('video').src = vid.url + '#t=0.1';
    const som = !img && !vid && (i.arquivos || []).find((a) => /\.(wav|mp3|ogg|m4a|flac)$/i.test(a.nome || ''));
    if (som) {
      const player = document.createElement('audio');
      player.controls = true;
      player.preload = 'none';
      player.src = som.url;
      player.className = 'fila-hist-audio';
      el.querySelector('.fila-hist-txt').append(player);
    }
    el.querySelector('.fila-hist-titulo').textContent =
      (i.deu_certo ? '' : '⚠️ ') + (i.titulo || 'trabalho');
    el.querySelector('.fila-hist-sub').textContent =
      // i.saida diz o QUE saiu ("imagem", "vídeo", "música · 3:10"); na música ela carrega a
      // duração, que e o unico numero util quando nao ha arquivo para abrir.
      [quandoData(i.quando), i.saida, (i.arquivos || []).length ? (i.arquivos.length + ' arquivo' +
        (i.arquivos.length === 1 ? '' : 's')) : '', i.prompt].filter(Boolean).join(' · ');
    el.querySelector('.fila-de').textContent =
      i.de === 'estudio' ? 'deste painel' : i.de === 'musica' ? 'música' : 'DE FORA';
    return el;
  }

  async function puxarHist() {
    let d;
    try {
      const r = await fetch('/api/fila/historico?quantos=300');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      d = await r.json();
    } catch (e) {
      $('#filaHistN').textContent = '';
      return;
    }
    ULT.hist = d.itens || [];
    ULT.limpoEm = d.limpo_em || 0;
    $('#filaHistN').textContent = d.total ? '(' + d.total + ')' : '';
    desenharHist();
    desenharAbas();
  }

  function pedirLimpar() {
    const n = ($('#filaHistN').textContent || '').replace(/[()]/g, '') || '0';
    $('#filaLimparN').textContent = n + (n === '1' ? ' trabalho' : ' trabalhos');
    $('#filaLimparConfirma').hidden = false;
    $('#filaLimparStatus').textContent = '';
  }

  async function limparMesmo() {
    const st = $('#filaLimparStatus'), bt = $('#filaLimparSim');
    bt.disabled = true;
    st.className = 'nota';
    st.textContent = 'Limpando…';
    try {
      const r = await fetch('/api/fila/historico/limpar', { method: 'POST' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      $('#filaLimparConfirma').hidden = true;
      st.className = 'nota laudo-ok';
      st.textContent = '✅ ' + d.apagados + ' da lista. Os arquivos continuam no disco.';
      await puxarHist();
    } catch (e) {
      st.className = 'nota laudo-ruim';
      st.textContent = String(e.message || e).slice(0, 200);
    } finally {
      bt.disabled = false;
    }
  }

  function ligarBotoes() {
    if (ligarBotoes.feito) return;
    ligarBotoes.feito = true;
    $('#filaDownParar').addEventListener('click', async () => {
      try { await fetch('/api/ias/parar', { method: 'POST' }); } catch (e) { /* o proximo pulso mostra o estado */ }
      puxarDown();
    });
    $('#filaAbas').addEventListener('click', (e) => {
      const b = e.target.closest('[data-tipo]');
      if (b) trocarAba(b.dataset.tipo);
    });
    $('#filaLimpar').addEventListener('click', pedirLimpar);
    $('#filaLimparNao').addEventListener('click', () => {
      $('#filaLimparConfirma').hidden = true;
      $('#filaLimparStatus').textContent = '';
    });
    $('#filaLimparSim').addEventListener('click', limparMesmo);
  }

  function abrir() {
    ligarBotoes();
    puxar();
    puxarHist();
    puxarDown();
    if (!tic) tic = setInterval(() => { puxar(); puxarHist(); puxarDown(); }, 2000);
  }
  function fechar() {
    if (tic) { clearInterval(tic); tic = null; }
  }

  // o contador da barra lateral continua vivo com a tela fechada, mas devagar: e so um numero
  setInterval(() => { if (!tic) { puxar(); puxarDown(); } }, 15000);

  window.FILA = { abrir, fechar, puxar, puxarHist };
})();
