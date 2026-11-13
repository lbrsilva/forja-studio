/* A porta de entrada do Forja Studio (03/11/2026).

   Mostra a tela de login enquanto nao houver licenca valida nesta maquina, e depois pendura
   o nome da pessoa no canto. Nada aqui tranca as ferramentas: o login tranca a TELA.

   Por que nao trancar as rotas tambem: todo atalho .bat que a pessoa escreveu fala HTTP
   direto com o estudio, sem navegador e sem login. Trancar as rotas mataria o atalho - que
   e justamente o jeito barato de usar isto. O que protege o plano pago nao e esta tela: e a
   chave da API ficar no servidor, do outro lado.

   Se o JavaScript quebrar, a porta nunca aparece e o estudio abre normalmente. Isso e de
   proposito: ninguem fica preso para fora da propria maquina por causa de um defeito meu. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];

  const E = { modo: 'entrar', estado: null, ocupado: false };

  async function pedir(caminho, corpo) {
    const r = await fetch(caminho, corpo === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
    let d = null;
    try { d = await r.json(); } catch (_) { /* resposta sem JSON: cai no erro abaixo */ }
    if (!r.ok) throw new Error((d && d.erro) || `O estúdio respondeu ${r.status}.`);
    return d;
  }

  // ------------------------------------------------------------------ a porta
  function trocarModo(modo) {
    E.modo = modo;
    const criando = modo === 'criar';
    $('#abaEntrar').setAttribute('aria-selected', String(!criando));
    $('#abaCriar').setAttribute('aria-selected', String(criando));
    $$('#portaForm .so-criar').forEach((l) => { l.hidden = !criando; });
    $$('#portaForm .so-criar input').forEach((i) => { i.required = criando; });
    $('#portaBt').textContent = criando ? 'Criar conta e entrar' : 'Entrar';
    $('#cSenha').setAttribute('autocomplete', criando ? 'new-password' : 'current-password');
    const esq = $('#portaEsqueci');
    if (esq) esq.hidden = criando;      // no cadastro o botao nao faz sentido
    $('#portaSub').textContent = criando
      ? 'Uma conta, duas máquinas. As ferramentas daqui são de graça e geram na sua própria placa de vídeo.'
      : 'As ferramentas daqui são de graça e geram na sua própria placa de vídeo. A conta é só para a licença ficar no seu nome.';
    erro('');
  }

  // ------------------------------------------------------ esqueci minha senha (05/11)
  // O servidor responde "ok" exista a conta ou nao, de proposito: se respondesse
  // "esse e-mail nao existe", qualquer um descobriria quem tem conta so tentando
  // enderecos. Por isso a mensagem aqui tambem e a mesma nos dois casos - se ela
  // mudasse, o cuidado do servidor nao valeria de nada.
  async function esqueciSenha() {
    const email = $('#cEmail').value.trim();
    if (!email || email.indexOf('@') < 0) {
      erro('Escreva o seu e-mail aqui em cima e clique de novo.');
      $('#cEmail').focus();
      return;
    }
    const bt = $('#portaEsqueci');
    const antes = bt.textContent;
    bt.disabled = true;
    bt.textContent = 'Mandando…';
    try {
      await pedir('/api/conta/recuperar', { email });
    } catch (e) {
      // nem o erro muda a resposta: o que a pessoa ve e sempre o mesmo
    }
    bt.textContent = antes;
    bt.disabled = false;
    const p = $('#portaErro');
    p.hidden = false;
    p.classList.add('porta-erro-ok');
    p.innerHTML = 'Se existir uma conta com <b>' + email.replace(/[<>&]/g, '') + '</b>, '
      + 'o link para trocar a senha chegou nesse e-mail. Ele vale por 1 hora.'
      + '<br>Não achou? Olhe no spam.';
  }

  function erro(msg) {
    const p = $('#portaErro');
    p.classList.remove('porta-erro-ok');
    p.textContent = msg || '';
    p.hidden = !msg;
  }

  // 12/11/2026: este pé de página dizia só "não consegui identificar esta máquina", e
  // mandava "abrir o estúdio do jeito de sempre" — que não resolvia nada, porque o
  // problema não era o jeito de abrir: era a leitura do equipamento falhando calada.
  // Agora ele diz QUAL característica não deu, que é o que permite consertar.
  function pe(estado) {
    const n = estado && estado.campos_da_maquina;
    const total = (estado && estado.maquina && estado.maquina.total) || 5;
    const faltou = (estado && estado.maquina_faltou) || [];
    const partes = [];
    if (n != null) {
      if (n >= 2) {
        partes.push(`Esta máquina foi reconhecida por <b>${n} de ${total}</b> características do equipamento.`);
      } else {
        partes.push('<b>Não consegui identificar esta máquina.</b>'
          + (faltou.length
              ? ' Não deu para ler ' + faltou.join(', ') + '.'
              : '')
          + ' <b>Atualize o Forja Studio</b> e abra de novo: a versão nova lê o'
          + ' equipamento por dois caminhos diferentes, e basta um deles responder.');
      }
    }
    partes.push('Guardamos nome, e-mail e telefone. A senha fica embaralhada, e os números de '
      + 'série do seu equipamento <b>não saem daqui</b> — só um resumo que não volta atrás.');
    $('#portaPe').innerHTML = partes.join(' ');
  }

  async function enviar(ev) {
    ev.preventDefault();
    if (E.ocupado) return;
    const email = $('#cEmail').value.trim();
    const senha = $('#cSenha').value;
    if (!email || senha.length < 8) {
      erro('Escreva o e-mail e uma senha de pelo menos 8 letras ou números.');
      return;
    }
    E.ocupado = true;
    $('#portaBt').disabled = true;
    $('#portaBt').textContent = E.modo === 'criar' ? 'Criando…' : 'Entrando…';
    erro('');
    try {
      const corpo = E.modo === 'criar'
        ? { nome: $('#cNome').value.trim(), email, telefone: $('#cTel').value.trim(), senha }
        : { email, senha };
      E.estado = await pedir(E.modo === 'criar' ? '/api/conta/criar' : '/api/conta/entrar', corpo);
      $('#cSenha').value = '';
      aplicar(E.estado);
    } catch (e) {
      erro(String(e.message || e));
      pe(E.estado);
    } finally {
      E.ocupado = false;
      $('#portaBt').disabled = false;
      trocarModo(E.modo);
    }
  }

  // ------------------------------------------------------- a conta depois de entrar
  function chip(estado) {
    const onde = $('#contaCanto');
    if (!onde) return;
    const pago = estado.plano === 'pago';
    const quando = estado.dias != null ? Math.max(0, Math.round(estado.dias)) : null;
    const limpa = (t) => String(t || '').replace(/[&<>"']/g, (c) => '&#' + c.charCodeAt(0) + ';');
    const completo = (estado.nome || estado.email || '').trim();
    const primeiro = estado.nome ? estado.nome.trim().split(/\s+/)[0] : String(estado.email || '').split('@')[0];
    onde.innerHTML =
      '<span class="conta-chip">' +
        '<span class="conta-plano' + (pago ? ' pago' : '') + '">' + (pago ? 'pago' : 'grátis') + '</span>' +
        '<b title="' + limpa(completo) + '">' + limpa(primeiro) + '</b>' +
        '<button type="button" class="conta-sair" id="contaSair">sair</button>' +
      '</span>';
    const bt = $('#contaSair');
    if (bt) {
      bt.title = quando != null
        ? `Licença conferida; vale por ${quando} dia(s) sem internet.`
        : 'Sair desta máquina.';
      bt.addEventListener('click', async () => {
        if (!confirm('Sair da conta nesta máquina?\n\nO que você já criou continua no HD. '
                     + 'Para usar o estúdio de novo, é só entrar outra vez.')) return;
        try { await pedir('/api/conta/sair', {}); } catch (_) { /* sair nao pode falhar */ }
        location.reload();
      });
    }
  }

  function recado(estado) {
    const onde = $('#contaRecado');
    if (!onde) return;
    if (estado.na_folga) {
      onde.innerHTML = '<p class="conta-recado">A licença venceu e eu não consegui falar com o '
        + 'servidor de contas. O estúdio continua funcionando por alguns dias; quando a '
        + 'internet voltar, ele se renova sozinho.</p>';
    } else if (estado.dias != null && estado.dias < 2) {
      onde.innerHTML = '<p class="conta-recado">A licença se renova em menos de 2 dias. '
        + 'Nada para fazer: o estúdio cuida disso sozinho quando estiver on-line.</p>';
    } else {
      onde.innerHTML = '';
    }
  }

  function aplicar(estado) {
    E.estado = estado;
    // Sem conta E sem servidor de contas no ar: o estudio ABRE, com um aviso. Trancar
    // alguem para fora do proprio computador porque um servidor nosso nao respondeu seria
    // o pior dos dois mundos - ela nao usa a ferramenta e ainda acha que esta quebrada.
    if (estado && !estado.entrou && estado.servidor_no_ar === false) {
      $('#porta').hidden = true;
      document.body.classList.remove('sem-conta');
      const onde = $('#contaRecado');
      if (onde) {
        onde.innerHTML = '<p class="conta-recado">Você está usando o estúdio <b>sem conta</b>: '
          + 'não consegui falar com o servidor de contas. Tudo funciona normalmente — a conta '
          + 'serve para a licença ficar no seu nome.</p>';
      }
      return true;
    }
    const dentro = !!(estado && estado.entrou);
    $('#porta').hidden = dentro;
    document.body.classList.toggle('sem-conta', !dentro);
    if (dentro) {
      chip(estado);
      recado(estado);
    } else {
      pe(estado);
    }
    return dentro;
  }

  // ------------------------------------------------------------------ comeco
  async function comecar() {
    let estado = null;
    try {
      estado = await pedir('/api/conta/estado');
    } catch (e) {
      // o estudio nao sabe de conta (versao antiga, ou rota fora do ar): abre normal.
      console.warn('[conta] sem /api/conta/estado — o estúdio abre sem a porta.', e);
      return;
    }
    $('#abaEntrar').addEventListener('click', () => trocarModo('entrar'));
    $('#abaCriar').addEventListener('click', () => trocarModo('criar'));
    $('#portaForm').addEventListener('submit', enviar);
    const esq = $('#portaEsqueci');
    if (esq) esq.addEventListener('click', esqueciSenha);
    const olho = $('#cVer');
    olho.addEventListener('click', () => {
      const i = $('#cSenha');
      const mostrando = i.type === 'text';
      i.type = mostrando ? 'password' : 'text';
      olho.textContent = mostrando ? 'ver' : 'ocultar';
      olho.setAttribute('aria-label', mostrando ? 'Mostrar a senha' : 'Esconder a senha');
    });
    if (estado && estado.motivo) erro(estado.motivo);
    if (!aplicar(estado)) {
      trocarModo('entrar');
      setTimeout(() => $('#cEmail').focus(), 60);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', comecar);
  } else {
    comecar();
  }

  window.CONTA = { estado: () => E.estado, aplicar };
})();
