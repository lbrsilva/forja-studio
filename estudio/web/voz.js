/* Estúdio Local — Narração (voz local, de graça, pelo VoiceStudio).

   Arquivo SEPARADO do app.js de propósito: se isto aqui quebrar, o resto do estúdio continua
   inteiro. O app.js só sabe duas coisas a respeito: a rota '#/voz' existe e, ao entrar nela,
   chama VOZ.abrir(). Nada mais.

   Conversa só com o nosso servidor (/api/voz/*), que por sua vez fala com o VoiceStudio.
   Nenhuma chamada à internet, nenhuma chave, nenhum texto saindo da máquina. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Pontos de partida e emoções: são os mesmos nomes que o VoiceStudio usa na janela dele.
  const ESTILOS = ['narrador', 'conversa', 'âncora', 'sussurro', 'animado', 'sério', 'triste', 'surpreso'];
  const EMOCOES = ['neutro', 'caloroso', 'animado', 'sério', 'triste', 'suave', 'firme'];
  // Letras por segundo MEDIDO na voz do senhor (13,2). É estimativa: o áudio é que confirma,
  // e por isso a tela mostra os dois números lado a lado depois de gerar.
  const LETRAS_SEG = 13.2;
  const SELOS = {
    ok: ['ok', 'pode publicar'], limite: ['alerta', 'tem limite'],
    duvida: ['alerta', 'licença não conferida'], proibido: ['alerta', 'só rascunho'],
  };

  const E = { iniciado: false, estado: null, vozes: [], pagina: 'falar', estilo: null,
    emocao: null, arquivoRef: null, ocupado: false };

  // ------------------------------------------------------------------ rede
  async function pedir(caminho, corpo, formulario) {
    const op = corpo === undefined ? { method: 'GET' }
      : formulario ? { method: 'POST', body: corpo }
        : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) };
    const r = await fetch(caminho, op);
    if (!r.ok) throw new Error((await r.text()) || ('Erro ' + r.status));
    return r.json();
  }

  function avisar(msg, tipo) {   // reusa o aviso do estúdio quando existe
    if (window.aviso) { window.aviso(msg, tipo || 'aviso'); return; }
    console.log(msg);
  }

  // ------------------------------------------------------------------ instalar o VoiceStudio
  let tInstal = null, tMotor = null;
  function pintarInstalacao(i) {
    if (!i || i.fase === 'parado') return false;
    E.instalMsg = true;
    const pct = i.fase === 'baixando' && i.total ? ` · ${Math.floor((i.baixados / i.total) * 100)}%` : '';
    const mb = i.fase === 'baixando' && i.total ? ` (${Math.round(i.baixados / 1048576)} de ${Math.round(i.total / 1048576)} MB)` : '';
    $('#vozOffDetalhe').textContent = (i.mensagem || '') + mb + pct;
    return ['procurando', 'baixando', 'conferindo', 'instalando'].includes(i.fase);
  }
  async function acompanharInstalacao() {
    clearTimeout(tInstal);
    let i;
    try { i = await pedir('/api/voz/instalar-app'); } catch (e) { return; }
    const andando = pintarInstalacao(i);
    $('#vozInstalar').disabled = andando;
    if (andando) { tInstal = setTimeout(acompanharInstalacao, 1500); return; }
    if (i.fase === 'pronto') esperarMotor();
  }
  function esperarMotor(n = 0) {
    clearTimeout(tMotor);
    if (n > 240) return;
    tMotor = setTimeout(async () => {
      let est;
      try { est = await pedir('/api/voz/estado'); } catch (e) { return esperarMotor(n + 1); }
      if (est.no_ar) { E.instalMsg = false; checar(); return; }
      if (est.motor_instalado) {
        $('#vozLigar').hidden = false;
        $('#vozInstalar').hidden = true;
        $('#vozOffDetalhe').textContent = 'O motor de voz está pronto. Clique em Ligar a voz local.';
        return;
      }
      esperarMotor(n + 1);
    }, 10000);
  }

  // ------------------------------------------------------------------ abrir a tela
  async function abrir() {
    montarUmaVez();
    await checar();
    // a lista das narracoes salvas nao depende do motor estar ligado: sao arquivos no disco.
    // Por isso vem DEPOIS do checar(), sem await no meio dele, e sem derrubar a aba se falhar.
    carregarGuardadas();
  }

  async function checar() {
    let est;
    try {
      est = await pedir('/api/voz/estado');
    } catch (e) {
      est = { no_ar: false, detalhe: String(e.message || e) };
    }
    E.estado = est;
    E.vozes = est.vozes || [];
    const ligado = !!est.no_ar;
    const semMotor = est.motor_instalado === false;
    $('#vozInstalar').hidden = ligado || !semMotor;
    $('#vozLigar').hidden = !ligado && semMotor;
    if (!ligado && est.instalacao && est.instalacao.fase !== 'parado') {
      const andando = pintarInstalacao(est.instalacao);
      $('#vozInstalar').disabled = andando;
      if (andando) acompanharInstalacao();
      else if (est.instalacao.fase === 'pronto') esperarMotor();
    }
    $('#vozOff').hidden = ligado;
    $('#vozTela').hidden = false;
    $('#vVoz').classList.toggle('voz-desligada', !ligado);
    if (!ligado) {
      if (E.instalMsg) return;
      $('#vozOffDetalhe').textContent = est.detalhe
        ? 'Detalhe técnico: ' + String(est.detalhe).slice(0, 180)
        : 'Procurei em ' + (est.url || 'http://127.0.0.1:3900') + ' e não houve resposta.';
      return;
    }
    const p = $('#vozMaq');
    p.classList.add('ligado');
    $('span', p).textContent = est.gpu ? 'no ar · ' + est.gpu : 'no ar';
    // qual motor esta ligado e se ELE pode ser publicado: e daqui que as vozes herdam o selo
    const m = est.motor, el = $('#vozMotor');
    el.hidden = !m;
    if (m) {
      el.className = 'voz-motor ' + (m.licenca === 'ok' ? 'ok' : 'alerta');
      el.innerHTML = '<b>' + esc(String(m.nome).split('(')[0].trim()) + '</b><br>'
        + esc(m.licenca_txt || '');
    }
    encherVozes();
    encherIdiomas();
  }

  function encherVozes() {
    const sel = $('#vozVoz'), antes = sel.value;
    if (!E.vozes.length) {
      sel.innerHTML = '<option value="">Nenhuma voz ainda — crie ou clone uma</option>';
      marcarVoz(null);
      return;
    }
    sel.innerHTML = E.vozes.map((v) =>
      `<option value="${esc(v.id)}">${esc(v.nome)}${v.motor ? ' · ' + esc(v.motor) : ''}</option>`).join('');
    // guarda a escolha anterior; senão, a primeira da lista (que vem ordenada pela licença:
    // as liberadas para publicar aparecem antes das proibidas, de propósito)
    sel.value = E.vozes.some((v) => v.id === antes) ? antes : E.vozes[0].id;
    marcarVoz(sel.value);
  }

  function marcarVoz(id) {
    const v = E.vozes.find((x) => x.id === id);
    const chip = $('#vozChipVoz'), selo = $('#vozChipLic'), lic = $('#vozLicenca');
    chip.textContent = v ? v.nome : 'Nenhuma voz escolhida';
    if (!v) { selo.hidden = true; lic.textContent = ''; return; }
    const [classe, curto] = SELOS[v.licenca] || SELOS.duvida;
    selo.hidden = false;
    selo.className = 'voz-selo ' + classe;
    selo.textContent = curto;
    lic.className = 'voz-licenca ' + classe;
    lic.textContent = v.licenca_txt || '';
  }

  function encherIdiomas() {
    const sel = $('#vozIdioma');
    if (sel.options.length) return;
    const lista = (E.estado.idiomas || []).slice();
    // Português na frente, sempre. É o idioma de quem usa este estúdio, e deixar "Automático"
    // escolhendo foi o que fez a voz sair embaralhada nos testes que rodaram por aí.
    const pt = lista.filter((l) => /^pt/i.test(l.codigo));
    const resto = lista.filter((l) => !/^pt/i.test(l.codigo));
    const todos = pt.length ? pt.concat(resto) : [{ codigo: 'pt', nome: 'Português' }].concat(resto);
    sel.innerHTML = todos.map((l) => `<option value="${esc(l.codigo)}">${esc(l.nome)}</option>`).join('');
    sel.value = (todos.find((l) => /^pt.?br/i.test(l.codigo)) || todos[0]).codigo;
  }

  // ------------------------------------------------------------------ montar (uma vez só)
  function montarUmaVez() {
    if (E.iniciado) return;
    E.iniciado = true;

    $('#vozEstilos').innerHTML = ESTILOS.map((s) =>
      `<button type="button" aria-pressed="false" data-estilo="${esc(s)}">${esc(s)}</button>`).join('');
    $('#vozEmocoes').innerHTML = EMOCOES.map((s) =>
      `<button type="button" aria-pressed="false" data-emocao="${esc(s)}">${esc(s)}</button>`).join('');
    if (window.ic) $$('#vVoz [data-ic]').forEach((el) => { if (!el.firstElementChild) el.innerHTML = window.ic(el.dataset.ic); });

    $('#vozReprocurar').addEventListener('click', checar);
    $('#vozInstalar').addEventListener('click', async () => {
      $('#vozInstalar').disabled = true;
      E.instalMsg = true;
      try {
        const r = await pedir('/api/voz/instalar-app', {});
        pintarInstalacao(r);
        acompanharInstalacao();
      } catch (e) {
        $('#vozOffDetalhe').textContent = String(e.message || e).slice(0, 250);
        $('#vozInstalar').disabled = false;
      }
    });
    $('#vozLigar').addEventListener('click', async () => {
      const bt = $('#vozLigar');
      bt.disabled = true;
      $('#vozOffDetalhe').textContent = 'Ligando… a primeira vez leva uns 30 segundos.';
      try {
        const r = await pedir('/api/voz/ligar', {});
        $('#vozOffDetalhe').textContent = r.recado || '';
        await checar();
      } catch (e) {
        $('#vozOffDetalhe').textContent = String(e.message || e).slice(0, 250);
      } finally { bt.disabled = false; }
    });
    $$('.voz-lado-bt').forEach((b) => b.addEventListener('click', () => trocarPagina(b.dataset.tela)));

    // --- texto para fala
    const ta = $('#vozTexto');
    ta.addEventListener('input', contar);
    contar();
    $('#vozLimpar').addEventListener('click', () => { ta.value = ''; contar(); ta.focus(); });
    $('#vozFalar').addEventListener('click', falar);
    $('#vozVoz').addEventListener('change', (ev) => marcarVoz(ev.target.value));
    $('#vozVel').addEventListener('input', (ev) =>
      { $('#vozVelVal').textContent = Number(ev.target.value).toFixed(2).replace('.', ',') + '×'; });
    $('#vozSteps').addEventListener('input', (ev) =>
      { $('#vozStepsVal').textContent = ev.target.value; });

    $('#vozEmocoes').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-emocao]');
      if (!b) return;
      const igual = E.emocao === b.dataset.emocao;
      E.emocao = igual ? null : b.dataset.emocao;   // clicar de novo desmarca
      $$('#vozEmocoes button').forEach((c) => c.setAttribute('aria-pressed', String(!igual && c === b)));
    });
    $('#vozIrCriar').addEventListener('click', () => {
      trocarPagina('desenhar');
      const d = $('#vozDesc');
      const i = instrucao();
      if (i && !d.value.includes(i)) d.value = (d.value + ', ' + i).trim();
      d.focus();
      descreverAgora();
    });

    // --- criar voz pela descrição
    $('#vozEstilos').addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-estilo]');
      if (!b) return;
      const igual = E.estilo === b.dataset.estilo;
      E.estilo = igual ? null : b.dataset.estilo;
      $$('#vozEstilos button').forEach((c) => c.setAttribute('aria-pressed', String(!igual && c === b)));
    });
    let t = null;
    $('#vozDesc').addEventListener('input', () => { clearTimeout(t); t = setTimeout(descreverAgora, 700); });
    $('#vozCriar').addEventListener('click', criarVoz);

    // --- clonar
    const up = $('#vozUp'), inp = $('input', up);
    inp.addEventListener('change', () => pegarArquivo(inp.files[0]));
    up.addEventListener('dragover', (ev) => { ev.preventDefault(); up.classList.add('sobre'); });
    up.addEventListener('dragleave', () => up.classList.remove('sobre'));
    up.addEventListener('drop', (ev) => {
      ev.preventDefault(); up.classList.remove('sobre');
      pegarArquivo(ev.dataTransfer.files[0]);
    });
    $('#vozClonar').addEventListener('click', clonar);
    $('#vozDescobrir').addEventListener('click', descobrirTexto);

    // --- apagar voz (07/11/2026)
    $('#vozApagar').addEventListener('click', pedirApagar);
    $('#vozApagarNao').addEventListener('click', () => {
      $('#vozApagarConfirma').hidden = true;
      $('#vozApagarStatus').textContent = '';
    });
    $('#vozApagarSim').addEventListener('click', apagarMesmo);
    $('#vozVoz').addEventListener('change', () => { $('#vozApagarConfirma').hidden = true; });
  }

  function trocarPagina(nome) {
    E.pagina = nome;
    $$('.voz-lado-bt').forEach((b) =>
      b.toggleAttribute('aria-current', b.dataset.tela === nome));
    $$('.voz-pagina').forEach((p) => { p.hidden = p.dataset.pagina !== nome; });
  }

  // A entrega: o que esta escrito na caixa manda; os botoes sao so atalhos para ela.
  function instrucao() {
    const livre = ($('#vozInstruct') && $('#vozInstruct').value.trim()) || '';
    if (livre) return livre;
    return E.emocao ? ('fale de um jeito ' + E.emocao) : '';
  }

  // ------------------------------------------------------------------ texto para fala
  function contar() {
    const n = $('#vozTexto').value.trim().length;
    $('#vozLetras').textContent = n.toLocaleString('pt-BR');
    const s = n / LETRAS_SEG;
    $('#vozEstimado').textContent = s < 60 ? s.toFixed(1).replace('.', ',') + ' s'
      : Math.floor(s / 60) + 'min ' + Math.round(s % 60) + 's';
  }

  async function falar() {
    if (E.ocupado) return;
    const texto = $('#vozTexto').value.trim();
    if (!texto) { avisar('Escreva o texto da narração primeiro.', 'aviso'); return; }
    const bt = $('#vozFalar');
    E.ocupado = true;
    bt.disabled = true;
    $('span:last-child', bt).textContent = 'Gerando…';
    const parar = await comecarBarra(texto.length);
    try {
      const r = await pedir('/api/voz/falar', {
        texto, voz: $('#vozVoz').value || null, idioma: $('#vozIdioma').value || 'pt',
        // os nomes sao os que o motor realmente aceita (conferidos na lista de ferramentas
        // dele): instruct = a entrega, speed = velocidade, steps = capricho.
        // A ENTREGA nao vai aqui: o motor so a aceita ao CRIAR ou CLONAR a voz
        // (conferido em 30/10 - generate_speech devolve 400 com ela).
        speed: Number($('#vozVel').value), steps: Number($('#vozSteps').value),
      });
      mostrarAudio(r);
    } catch (e) {
      avisar(String(e.message || e).slice(0, 300), 'erro');
    } finally {
      parar();
      E.ocupado = false;
      bt.disabled = false;
      $('span:last-child', bt).textContent = 'Gerar narração';
    }
  }

  // ------------------------------------------------- a barra de progresso (07/11/2026)
  // Ele clicou em Gerar e ficou sem saber quanto falta: "ficou so pensando e nao faco ideia
  // de quando terminar".
  //
  // ⚠️ O motor NAO manda progresso - e uma chamada so, que volta quando acaba. Entao aqui
  // nao existe porcentagem de verdade: o que existe e o CRONOMETRO (fato) e uma previsao
  // feita com os tempos que ja medimos nesta maquina. A tela diz qual e qual:
  //   - o tempo CORRIDO e sempre mostrado, porque e verdade;
  //   - a barra so aparece quando ha medida para prever, e vem rotulada "estimativa";
  //   - passando do previsto ela NAO fica presa em 99% fingindo: assume que errou e diz
  //     que ainda esta gerando. Barra que mente em 99% e pior do que barra nenhuma.
  function seg(n) {
    n = Math.max(0, Math.round(n));
    return n < 60 ? n + ' s' : Math.floor(n / 60) + ' min ' + String(n % 60).padStart(2, '0') + ' s';
  }

  async function comecarBarra(letras) {
    const caixa = $('#vozProgresso'), barra = $('#vozProgressoBarra'),
          txt = $('#vozProgressoTxt');
    if (!caixa) return () => {};
    let prev = null;
    try {
      const r = await pedir('/api/voz/previsao?letras=' + letras);
      if (r && r.segundos) prev = r;
    } catch (e) { /* sem previsao a barra some e fica so o cronometro */ }

    const t0 = Date.now();
    caixa.hidden = false;
    barra.parentElement.hidden = !prev;
    const tic = setInterval(() => {
      const passou = (Date.now() - t0) / 1000;
      if (!prev) {
        txt.textContent = 'Gerando há ' + seg(passou) + '. (Ainda não medi quanto isto '
          + 'costuma levar aqui — depois desta eu já consigo prever.)';
        return;
      }
      const pct = Math.min(99, Math.round((passou / prev.segundos) * 100));
      barra.style.width = pct + '%';
      if (passou < prev.segundos) {
        txt.textContent = pct + '% · faltam ~' + seg(prev.segundos - passou)
          + ' (estimativa, de ' + prev.amostras + ' geraç' + (prev.amostras === 1 ? 'ão' : 'ões')
          + ' medida' + (prev.amostras === 1 ? '' : 's') + ')'
          + (prev.frio ? ' · motor frio, a primeira é sempre mais lenta' : '');
      } else {
        barra.classList.add('passou');
        txt.textContent = 'Passou da estimativa (' + seg(prev.segundos) + ') e ainda está '
          + 'gerando — já são ' + seg(passou) + '. Errei a previsão; o motor não avisa '
          + 'quanto falta.';
      }
    }, 250);

    return () => {
      clearInterval(tic);
      caixa.hidden = true;
      barra.style.width = '0%';
      barra.classList.remove('passou');
      txt.textContent = '';
    };
  }

  function mostrarAudio(r) {
    $('#vozSaida').hidden = false;
    const a = $('#vozAudio');
    a.src = r.url + '?t=' + Date.now();
    a.load();
    $('#vozBaixar').href = r.url;
    $('#vozBaixar').setAttribute('download', r.arquivo || 'narracao.wav');
    carregarGuardadas();   // a que acabou de nascer ja entra na lista
    const real = r.segundos;
    const partes = [];
    if (real != null) partes.push('<b>' + String(real).replace('.', ',') + ' s</b> de verdade');
    if (r.estimado != null && real != null) {
      const dif = real - r.estimado;
      partes.push((Math.abs(dif) < 0.3 ? 'bate com a estimativa'
        : (dif > 0 ? '+' : '') + dif.toFixed(1).replace('.', ',') + ' s contra a estimativa'));
    }
    partes.push('gerado em ' + String(r.demorou).replace('.', ',') + ' s');
    $('#vozSaidaInfo').innerHTML = partes.join(' · ');
    // o número real é o que serve para encaixar o @segundo da narração; deixa visível em cima
    if (real != null) {
      const el = $('#vozReal');
      el.hidden = false;
      el.textContent = '· real: ' + String(real).replace('.', ',') + ' s';
    }
  }

  // ------------------------------------------------------------------ criar voz
  async function descreverAgora() {
    const d = $('#vozDesc').value.trim(), alvo = $('#vozEntendeu');
    if (d.length < 3) { alvo.textContent = ''; return; }
    let r;
    try {
      r = await pedir('/api/voz/descrever', { descricao: d });
    } catch (e) { alvo.textContent = ''; return; }
    const ent = Object.entries(r.entendeu || {});
    const ign = r.ignorou || [];
    let html = '';
    if (ent.length) html += '<span class="ok">Entendi: ' + esc(ent.map(([k, v]) => k + ' ' + v).join(', ')) + '</span>';
    // Isto é o ouro desta tela: dizer QUAL palavra não valeu nada, ENQUANTO ele escreve,
    // em vez de ele esperar a geração para descobrir.
    if (ign.length) html += '<span class="alerta">Não entendi: ' + esc(ign.join(', ')) + ' — troque por algo concreto.</span>';
    alvo.innerHTML = html;
  }

  async function criarVoz() {
    const desc = $('#vozDesc').value.trim();
    if (!desc) { avisar('Descreva a voz primeiro.', 'aviso'); return; }
    const bt = $('#vozCriar'), st = $('#vozCriarStatus');
    bt.disabled = true;
    st.textContent = 'Criando a voz… a primeira vez é a mais demorada.';
    try {
      const r = await pedir('/api/voz/desenhar', {
        descricao: E.estilo ? desc + ', entrega de ' + E.estilo : desc,
        nome: $('#vozDescNome').value.trim() || null,
        entrega: instrucao() || null,
      });
      E.vozes = r.vozes || E.vozes;
      encherVozes();
      $('#vozVoz').value = r.id;
      marcarVoz(r.id);
      st.textContent = 'Pronto. A voz já está escolhida — vá em "Texto para fala" e ouça.';
      trocarPagina('falar');
    } catch (e) {
      st.textContent = String(e.message || e).slice(0, 300);
    } finally {
      bt.disabled = false;
    }
  }

  // ------------------------------------------------------------------ clonar
  function pegarArquivo(f) {
    if (!f) return;
    E.arquivoRef = f;
    E.laudoRef = null;
    $('.up-txt', $('#vozUp')).textContent = f.name + ' · ' + Math.round(f.size / 1024) + ' KB';
    conferirRef(f);
  }

  // 07/11/2026: a conferência acontece ao ESCOLHER o arquivo, não ao clicar em Clonar. O clone
  // leva minutos; dizer "esse áudio tem música tocando o tempo todo" depois disso não serve de
  // nada. Foi o que aconteceu com a referência da YAMI em 06/11.
  async function conferirRef(f) {
    const st = $('#vozRefLaudo');
    if (!st) return;
    st.className = 'nota';
    st.textContent = 'Conferindo o áudio…';
    const fd = new FormData();
    fd.append('arquivo', f);
    try {
      const r = await pedir('/api/voz/conferir-ref', fd, true);
      E.laudoRef = r;
      const selo = { ok: '✅', alerta: '⚠️', ruim: '⛔' }[r.veredito] || '';
      st.className = 'nota laudo-' + (r.veredito || 'ok');
      st.textContent = selo + ' ' + (r.motivos || []).join(' ');
      // O botao NUNCA e desligado pelo laudo (07/11/2026). Ele avisa; quem decide e quem
      // esta com o audio. "Nem todo mundo vai saber disso" - e quem nao sabe nao pode ficar
      // preso numa tela que diz nao sem explicar como sair.
      $('#vozClonar').disabled = false;
    } catch (e) {
      // Falhar a conferência NÃO trava o clone: sem ffmpeg não há medida, e tentar é melhor
      // do que impedir. Só avisa que não deu para olhar.
      E.laudoRef = null;
      st.className = 'nota';
      st.textContent = 'Não deu para conferir o áudio (' + String(e.message || e).slice(0, 120) +
        '). Pode clonar, mas se sair embaralhado o problema está na referência.';
      $('#vozClonar').disabled = false;
    }
  }

  async function clonar() {
    if (!E.arquivoRef) { avisar('Envie o áudio de referência.', 'aviso'); return; }
    // 07/11/2026: AQUI havia "Escreva o que esta falado no audio - sem isso a voz sai
    // embaralhada", e o botao nao seguia. Contradizia o proprio rotulo do campo ("pode
    // deixar em branco") E o que foi medido em 31/10: com transcricao ERRADA a frase saiu
    // cortada em 2,6 s; SEM transcricao nenhuma saiu inteira em 6,2 s. Em branco o motor se
    // vira sozinho. Exigir o campo so empurrava a pessoa a inventar - que e o caso ruim.
    const tr = $('#vozTransc').value.trim();
    const bt = $('#vozClonar'), st = $('#vozClonarStatus');
    const fd = new FormData();
    fd.append('arquivo', E.arquivoRef);
    fd.append('transcricao', tr);
    fd.append('nome', $('#vozClonNome').value.trim());
    fd.append('idioma', $('#vozIdioma').value || 'pt');
    if (instrucao()) fd.append('entrega', instrucao());
    bt.disabled = true;
    st.textContent = 'Clonando… pode levar alguns minutos.';
    try {
      const r = await pedir('/api/voz/clonar', fd, true);
      E.vozes = r.vozes || E.vozes;
      encherVozes();
      $('#vozVoz').value = r.id;
      marcarVoz(r.id);
      st.textContent = 'Pronto. Ouça um trecho curto antes de gerar a narração inteira.';
      trocarPagina('falar');
    } catch (e) {
      st.textContent = String(e.message || e).slice(0, 300);
    } finally {
      bt.disabled = false;
    }
  }

  // ------------------------------------------------------------------ apagar voz
  // 07/11/2026. Ele pediu: "poder gerenciar as vozes criadas, poder apagar". A confirmacao
  // MOSTRA O NOME em vez de perguntar "tem certeza?": o que protege e ver o que vai sumir,
  // nao clicar duas vezes. E o pedido leva o nome junto, para o servidor recusar se a lista
  // tiver mudado entre o clique e o envio.
  function vozEscolhida() {
    const id = $('#vozVoz').value;
    return (E.vozes || []).find((v) => String(v.id) === String(id)) || null;
  }

  function pedirApagar() {
    const v = vozEscolhida();
    const st = $('#vozApagarStatus');
    st.className = 'nota';
    if (!v) { st.textContent = 'Escolha uma voz primeiro.'; return; }
    $('#vozApagarNome').textContent = v.nome;
    $('#vozApagarConfirma').hidden = false;
    st.textContent = '';
  }

  async function apagarMesmo() {
    const v = vozEscolhida();
    if (!v) return;
    const st = $('#vozApagarStatus'), bt = $('#vozApagarSim');
    bt.disabled = true;
    st.className = 'nota';
    st.textContent = 'Apagando…';
    try {
      const r = await pedir('/api/voz/apagar', { id: v.id, nome: v.nome });
      E.vozes = r.vozes || [];
      encherVozes();
      $('#vozApagarConfirma').hidden = true;
      st.className = 'nota laudo-ok';
      st.textContent = '✅ "' + r.nome + '" foi apagada.';
    } catch (e) {
      st.className = 'nota laudo-ruim';
      st.textContent = String(e.message || e).slice(0, 300);
    } finally {
      bt.disabled = false;
    }
  }

  // ------------------------------------------------------- narracoes salvas (07/11/2026)
  // Ele pediu: "as narracoes ficar salvas nas narracoes mesmo". Elas SEMPRE foram gravadas
  // no disco - o que faltava era a tela mostrar. Le a pasta a cada vez que a aba abre e
  // depois de cada narracao nova; nao guarda estado proprio, para nunca mostrar uma lista
  // que nao existe mais no disco.
  function quando(seg) {
    const d = new Date(seg * 1000), hoje = new Date();
    const hm = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    const mesmoDia = d.toDateString() === hoje.toDateString();
    if (mesmoDia) return 'hoje ' + hm;
    return String(d.getDate()).padStart(2, '0') + '/' +
           String(d.getMonth() + 1).padStart(2, '0') + ' ' + hm;
  }

  async function carregarGuardadas() {
    const caixa = $('#vozGuardadas'), lista = $('#vozGuardadasLista');
    if (!caixa) return;
    let r;
    try {
      r = await pedir('/api/voz/gravadas');
    } catch (e) {
      caixa.hidden = true;
      return;
    }
    const itens = r.narracoes || [];
    caixa.hidden = itens.length === 0;
    $('#vozGuardadasN').textContent = itens.length ? '(' + itens.length + ')' : '';
    lista.innerHTML = '';
    itens.forEach((n) => {
      const li = document.createElement('div');
      li.className = 'voz-guardada';
      const txt = n.texto ? n.texto : '(gerada antes desta lista existir)';
      li.innerHTML =
        '<div class="voz-guardada-cab">' +
          '<span class="voz-guardada-quando">' + quando(n.quando) + '</span>' +
          '<span class="voz-guardada-kb">' + n.kb + ' KB' +
            (n.segundos ? ' · ' + n.segundos + ' s' : '') + '</span>' +
        '</div>' +
        '<p class="voz-guardada-txt' + (n.texto ? '' : ' vazio') + '"></p>' +
        '<audio controls preload="none" src="' + n.url + '"></audio>' +
        '<div class="voz-guardada-bts">' +
          '<a class="voz-gerir-bt" download href="' + n.url + '">' +
            '<span data-ic="baixar"></span>Baixar</a>' +
          '<button type="button" class="voz-gerir-bt perigo" data-apagar="' + n.arquivo + '">Apagar</button>' +
        '</div>';
      // o texto entra por textContent, nunca por innerHTML: ele veio do que a pessoa digitou
      li.querySelector('.voz-guardada-txt').textContent = txt;
      li.querySelector('[data-apagar]').addEventListener('click', (ev) =>
        apagarGuardada(ev.currentTarget));
      lista.append(li);
    });
    if (window.ICONES && window.ICONES.pintar) window.ICONES.pintar(lista);
  }

  async function apagarGuardada(bt) {
    // Duas etapas no proprio botao: o primeiro clique vira "Apagar mesmo?" e volta sozinho
    // em 4 s. Narracao se refaz em segundos, entao nao merece a janela de confirmar - mas
    // merece nao sumir com um clique torto.
    if (bt.dataset.certeza !== '1') {
      bt.dataset.certeza = '1';
      bt.textContent = 'Apagar mesmo?';
      setTimeout(() => {
        if (bt.isConnected && bt.dataset.certeza === '1') {
          bt.dataset.certeza = '0';
          bt.textContent = 'Apagar';
        }
      }, 4000);
      return;
    }
    const st = $('#vozGuardadasStatus');
    bt.disabled = true;
    try {
      await pedir('/api/voz/gravadas/apagar', { arquivo: bt.dataset.apagar });
      st.className = 'nota';
      st.textContent = '';
      await carregarGuardadas();
    } catch (e) {
      bt.disabled = false;
      st.className = 'nota laudo-ruim';
      st.textContent = String(e.message || e).slice(0, 200);
    }
  }

  // --------------------------------------------------- descobrir o texto (07/11/2026)
  // "E quando eu nao sei?" - nao precisa saber. O motor transcreve, e transcreve o MESMO
  // trecho que vai ser clonado. O texto cai no campo para ele CONFERIR antes de clonar:
  // transcricao automatica tambem erra, e texto errado e pior que campo vazio.
  async function descobrirTexto() {
    if (!E.arquivoRef) {
      const st0 = $('#vozDescobrirStatus');
      st0.className = 'nota laudo-ruim';
      st0.textContent = 'Envie o áudio primeiro.';
      return;
    }
    const bt = $('#vozDescobrir'), st = $('#vozDescobrirStatus');
    bt.disabled = true;
    st.className = 'nota';
    st.textContent = 'Ouvindo o áudio…';
    const fd = new FormData();
    fd.append('arquivo', E.arquivoRef);
    fd.append('idioma', $('#vozIdioma').value || 'pt');
    try {
      const r = await pedir('/api/voz/transcrever-ref', fd, true);
      $('#vozTransc').value = r.texto || '';
      st.className = 'nota laudo-alerta';
      st.textContent = '⚠️ Isto foi o que ele ouviu nos ' + (r.segundos || 25) + ' s que vão ' +
        'ser clonados' + (r.trecho ? ' (a partir de ' + Math.round(r.trecho) + ' s)' : '') +
        '. LEIA e corrija o que estiver errado — ou apague tudo, que em branco também funciona.';
    } catch (e) {
      st.className = 'nota laudo-ruim';
      st.textContent = 'Não consegui transcrever (' + String(e.message || e).slice(0, 140) +
        '). Deixe o campo em branco: o motor se vira.';
    } finally {
      bt.disabled = false;
    }
  }

  window.VOZ = { abrir, checar };
})();

/* ---------------------------------------- vozes na nuvem: a chave de QUEM USA (03/11/2026)
   O pacote do GitHub nao leva chave nenhuma. Quem tiver conta no ElevenLabs poe a propria
   aqui; quem nao tiver nem precisa abrir isto, porque a voz local e de graca e e o padrao.
   A tela nunca MOSTRA a chave de volta - so diz se existe uma guardada. */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);

  async function falar(caminho, corpo) {
    const r = await fetch(caminho, corpo === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
    let d = null;
    try { d = await r.json(); } catch (_) { /* sem JSON */ }
    if (!r.ok) throw new Error((d && (d.erro || d.mensagem)) || `O estúdio respondeu ${r.status}.`);
    return d;
  }

  function recado(texto, tipo) {
    const m = $('#nuvemMsg');
    if (!m) return;
    m.textContent = texto || '';
    m.className = 'nuvem-msg' + (tipo ? ' ' + tipo : '');
  }

  // 09/11/2026: o ponto verde acendia so por existir arquivo de chave, mesmo quando o
  // ElevenLabs nao devolvia voz nenhuma. Agora "serve" manda: luz verde = funciona.
  function selo(tem, serve) {
    const bom = serve === undefined ? !!tem : !!serve;
    const s = $('#nuvemSelo');
    if (s) {
      s.classList.toggle('on', bom);
      s.title = bom ? 'Uma chave está guardada e funcionando.'
        : tem ? 'Chave guardada, mas o ElevenLabs não devolveu nenhuma voz.'
              : 'Sem chave: só voz local.';
    }
    const i = $('#nuvemChave');
    if (i) i.placeholder = tem ? 'uma chave já está guardada — cole outra para trocar'
                               : 'cole a chave aqui';
  }

  async function olhar() {
    // O GET diz se EXISTE chave, nunca se ela funciona. Quem responde isso e a lista de
    // vozes: chave guardada + lista vazia = chave que nao serve.
    try {
      const d = await falar('/api/chave-nuvem');
      const tem = !!(d && d.tem);
      let serve = false;
      if (tem) {
        try {
          const v = await falar('/api/vozes11');
          serve = Array.isArray(v && v.vozes) && v.vozes.length > 0;
        } catch (_) { serve = false; }
      }
      selo(tem, serve);
    } catch (_) { /* estudio velho: o bloco so fica quieto */ }
  }

  function ligar() {
    const bloco = $('#nuvemBloco');
    if (!bloco) return;
    olhar();
    $('#nuvemSalvar').addEventListener('click', async () => {
      const campo = $('#nuvemChave');
      const chave = (campo.value || '').trim();
      if (!chave) { recado('Cole a chave antes de salvar.', 'ruim'); return; }
      recado('Conferindo a chave com o ElevenLabs…');
      try {
        const d = await falar('/api/chave-nuvem', { chave });
        campo.value = '';
        selo(d.tem, d.ok);
        recado(d.mensagem, d.ok ? 'bom' : 'ruim');
        if (d.ok && window.VOZ && window.VOZ.recarregarVozes) window.VOZ.recarregarVozes();
      } catch (e) {
        recado(String(e.message || e), 'ruim');
      }
    });
    $('#nuvemTirar').addEventListener('click', async () => {
      if (!confirm('Remover a chave do ElevenLabs desta máquina?\n\n'
                   + 'A narração continua funcionando com a voz local, de graça.')) return;
      try {
        const d = await falar('/api/chave-nuvem', { chave: '' });
        $('#nuvemChave').value = '';
        selo(false);
        recado(d.mensagem, 'bom');
        if (window.VOZ && window.VOZ.recarregarVozes) window.VOZ.recarregarVozes();
      } catch (e) {
        recado(String(e.message || e), 'ruim');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ligar);
  } else {
    ligar();
  }
})();
