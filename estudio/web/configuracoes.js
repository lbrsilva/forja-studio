/* CONFIGURAÇÕES (11/11/2026): as chaves que o estúdio usa, num lugar só.
 *
 * Hugging Face: /api/chave-hf    -> API/huggingface.txt (baixar IAs de repositórios restritos, ex.: LTX 2.5)
 * ElevenLabs:   /api/chave-nuvem -> API/elevenlabs.txt  (vozes na nuvem da Narração)
 *
 * O servidor NUNCA devolve a chave: o GET só diz se existe uma (e, no Hugging Face, de onde ela vem).
 * Arquivo à parte de propósito: se ele faltar ou quebrar, o resto do estúdio continua inteiro.
 */
(() => {
  const $ = (s, r = document) => r.querySelector(s);

  const CARTOES = [
    { id: 'cfgHf', url: '/api/chave-hf', placeholder: 'hf_...', guardado: 'um token já está guardado — cole outro para trocar',
      conferindo: 'Conferindo o token com o Hugging Face…', colar: 'Cole o token antes de salvar.',
      remover: { titulo: 'Remover o token do Hugging Face?',
        texto: 'O token sai deste computador. As IAs que exigem conta deixam de baixar até você colocar outro.',
        sim: 'Remover o token' },
      aviso: (d) => (d.origem === 'variavel'
        ? 'O token está vindo da variável de ambiente HF_TOKEN, que vale no lugar do arquivo. '
          + 'Para trocá-lo por aqui, tire a variável e reinicie o estúdio.' : null),
      podeTirar: (d) => d.origem === 'arquivo' },
    { id: 'cfgEl', url: '/api/chave-nuvem', placeholder: 'cole a chave aqui', guardado: 'uma chave já está guardada — cole outra para trocar',
      conferindo: 'Conferindo a chave com o ElevenLabs…', colar: 'Cole a chave antes de salvar.',
      remover: { titulo: 'Remover a chave do ElevenLabs?',
        texto: 'A chave sai deste computador e as vozes da nuvem desaparecem da lista. A narração continua '
             + 'funcionando com as vozes locais, de graça.',
        sim: 'Remover a chave' },
      aviso: () => null,
      podeTirar: (d) => !!d.tem },
  ];

  async function chamar(url, corpo) {
    const r = await fetch(url, corpo === undefined ? {} : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
    });
    if (!r.ok) throw new Error((await r.text()) || `erro ${r.status}`);
    return r.json();
  }

  function preparar(c) {
    const el = (suf) => $('#' + c.id + suf);
    const recado = (txt, tipo) => {
      const m = el('Msg');
      if (!m) return;
      m.textContent = txt || '';
      m.className = 'nuvem-msg' + (tipo ? ' ' + tipo : '');
    };
    const pintar = (d) => {
      const tem = !!(d && d.tem);
      el('Selo').classList.toggle('on', tem);
      el('Chave').placeholder = tem ? c.guardado : c.placeholder;
      el('Tirar').disabled = !(d && c.podeTirar(d));
      const extra = d && c.aviso(d);
      if (extra) el('Pe').textContent = extra;
    };
    const atualizar = async () => {
      try { pintar(await chamar(c.url)); } catch (e) { recado('Não consegui ler o estado: ' + e.message, 'ruim'); }
    };

    el('Salvar').onclick = async () => {
      const campo = el('Chave');
      const chave = (campo.value || '').trim();
      if (!chave) { recado(c.colar, 'ruim'); return; }
      recado(c.conferindo);
      try {
        const d = await chamar(c.url, { chave });
        if (d.ok) campo.value = '';
        pintar(d);
        recado(d.mensagem, d.ok ? 'bom' : 'ruim');
      } catch (e) { recado(e.message, 'ruim'); }
    };
    el('Tirar').onclick = async () => {
      const ok = typeof confirmar === 'function'
        ? await confirmar({ ...c.remover, icone: 'lixo' })
        : window.confirm(c.remover.titulo);
      if (!ok) return;
      try {
        const d = await chamar(c.url, { chave: '' });
        el('Chave').value = '';
        pintar(d);
        recado(d.mensagem, 'bom');
      } catch (e) { recado(e.message, 'ruim'); }
    };
    return { atualizar, limpar: () => recado('') };
  }

  async function listarIAs() {
    const ul = $('#cfgIasLista'), vazio = $('#cfgIasVazio');
    let d;
    try { d = await (await fetch('/api/ias')).json(); } catch (e) { return; }
    const instaladas = Object.entries(d.ias || {}).filter(([, v]) => v.instalada);
    ul.innerHTML = '';
    vazio.hidden = instaladas.length > 0;
    instaladas.forEach(([id, v]) => {
      const li = document.createElement('li');
      const nome = document.createElement('span');
      nome.textContent = v.nome || id;
      const gb = document.createElement('span');
      gb.className = 'gb';
      gb.textContent = (v.gb_total || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' GB';
      const bt = document.createElement('button');
      bt.type = 'button';
      bt.className = 'ia-lixo';
      bt.title = 'Remover ' + (v.nome || id) + ' do computador';
      bt.setAttribute('aria-label', bt.title);
      bt.innerHTML = typeof ic === 'function' ? ic('lixo') : '×';
      bt.onclick = async () => {
        if (typeof removerIA !== 'function') return;
        if (window.lerIAs) await lerIAs();
        if (await removerIA(id)) listarIAs();
      };
      li.append(nome, gb, bt);
      ul.append(li);
    });
  }

  // Navegador da automação: Chrome, Edge, Brave, Chromium, Vivaldi ou Opera. O Safari fica
  // de fora porque não aceita as opções de linha de comando que a tela invisível usa.
  async function lerNavegador() {
    const sel = $('#cfgNavSel'), msg = $('#cfgNavMsg'), selo = $('#cfgNavSelo');
    if (!sel) return;
    try {
      const d = await (await fetch('/api/navegadores')).json();
      const opcoes = d.opcoes || [];
      sel.innerHTML = '';
      opcoes.forEach((n) => {
        const o = document.createElement('option');
        o.value = n.id;
        o.textContent = n.nome;
        sel.append(o);
      });
      if (d.escolhido) sel.value = d.escolhido;
      const achou = opcoes.some((n) => n.id === d.escolhido);
      if (selo) selo.classList.toggle('on', !!d.escolhido);
      sel.disabled = !opcoes.length;
      $('#cfgNavSalvar').disabled = !opcoes.length;
      if (!opcoes.length) {
        msg.textContent = 'Nenhum navegador Chromium encontrado. Instale o Chrome, o Edge, o Brave ou o Chromium.';
        msg.className = 'nuvem-msg ruim';
      } else if (!achou) {
        msg.textContent = 'O navegador salvo não está instalado; o estúdio usa ' + opcoes[0].nome + '.';
        msg.className = 'nuvem-msg';
      } else {
        msg.textContent = '';
        msg.className = 'nuvem-msg';
      }
    } catch (e) {
      msg.textContent = 'Não consegui ler os navegadores: ' + e.message;
      msg.className = 'nuvem-msg ruim';
    }
  }

  async function salvarNavegador() {
    const sel = $('#cfgNavSel'), msg = $('#cfgNavMsg');
    try {
      const d = await chamar('/api/navegadores', { id: sel.value });
      msg.textContent = 'Navegador da automação: ' + (d.escolhido || 'automático');
      msg.className = 'nuvem-msg bom';
      await lerNavegador();
    } catch (e) {
      msg.textContent = e.message;
      msg.className = 'nuvem-msg ruim';
    }
  }

  let prontos = null;
  let navegadorPronto = false;

  window.CONFIG = {
    abrir() {
      if (!prontos) prontos = CARTOES.map(preparar);
      prontos.forEach((p) => { p.limpar(); p.atualizar(); });
      listarIAs();
      if (!navegadorPronto) {
        const b = $('#cfgNavSalvar');
        if (b) { b.onclick = salvarNavegador; navegadorPronto = true; }
      }
      lerNavegador();
    },
  };
})();
