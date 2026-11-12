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
  // 13/11/2026: codigo primeiro, senha depois. O pedido agora chega de verdade ao servidor
  // (a rota nao existia no painel) e, se ele falhar, a tela DIZ - nao finge mais sucesso.
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
      pedirCodigo({ motivo: 'senha', email, enviado: true });
    } catch (e) {
      erro('Não consegui pedir o código agora: ' + String(e.message || e));
    }
    bt.textContent = antes;
    bt.disabled = false;
  }
  // (a versao de 05/11, que mandava o link e nunca funcionou no painel; sem uso)
  async function esqueciSenhaAntigo() {
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
      const d = await pedir(E.modo === 'criar' ? '/api/conta/criar' : '/api/conta/entrar', corpo);
      $('#cSenha').value = '';
      if (d && d.precisa_confirmar) { pedirCodigo(d); return; }
      E.estado = d;
      if (aplicar(E.estado)) recarregar();
    } catch (e) {
      erro(String(e.message || e));
      pe(E.estado);
    } finally {
      E.ocupado = false;
      $('#portaBt').disabled = false;
      trocarModo(E.modo);
    }
  }

  // ------------------------------------------- o codigo do e-mail (13/11/2026)
  // O servidor aceitou a senha (ou o cadastro) mas so entrega a licenca depois dos 6
  // numeros. Sao dois casos com o MESMO campo e textos diferentes:
  //   cadastro     conta nova: o codigo termina o cadastro;
  //   atualizacao  conta de antes de o e-mail confirmado virar obrigatorio.
  function erroCodigo(msg, bom) {
    const p = $('#codigoErro');
    p.classList.toggle('porta-erro-ok', !!bom);
    p.textContent = msg || '';
    p.hidden = !msg;
  }
  function pedirCodigo(d) {
    E.codigo = d;
    const email = String(d.email || '').replace(/[<>&]/g, '');
    let txt;
    if (d.motivo === 'senha') {
      // a mesma frase exista a conta ou nao: a tela nao pode entregar quem tem cadastro
      txt = 'Se existir uma conta com <b>' + email + '</b>, mandamos um código de 6 números para '
        + 'esse e-mail. Digite ele aqui e a sua senha vai para o mesmo e-mail.'
        + '<br><br>Se não achar, olhe no spam.';
    } else if (d.motivo === 'atualizacao') {
      txt = '<b>Estamos fazendo uma atualização de cadastro.</b> Mandamos um código de 6 números '
        + 'para <b>' + email + '</b>. Por favor, confirme o código: sem ele não dá para entrar.'
        + '<br><br>Se você não tem mais acesso a esse e-mail, crie uma conta nova com um '
        + 'e-mail que você usa.';
    } else {
      txt = 'Mandamos um código de 6 números para <b>' + email + '</b>. Digite ele aqui para '
        + 'terminar o cadastro. Se não achar, olhe no spam.';
    }
    if (d.espere) txt += '<br><br>Já mandamos um código há pouco: use o que chegou.';
    else if (!d.enviado) txt += '<br><br><b>Não consegui mandar o e-mail agora.</b> Espere um '
      + 'minuto e clique em "Mandar outro código".';
    $('#codigoTxt').innerHTML = txt;
    $('#codigoVoltar').textContent = d.motivo === 'atualizacao' ? 'Criar uma conta nova' : 'Voltar';
    $('#portaTitulo').textContent = d.motivo === 'senha' ? 'Esqueci minha senha'
      : d.motivo === 'atualizacao' ? 'Atualização de cadastro' : 'Confirme o seu e-mail';
    $('#codigoBt').textContent = rotuloDoCodigo();
    $('#portaSub').hidden = true;
    $$('.porta-abas').forEach((a) => { a.hidden = true; });
    $('#portaForm').hidden = true;
    $('#portaCodigo').hidden = false;
    $('#cCodigo').value = '';
    erroCodigo('');
    $('#cCodigo').focus();
  }
  function rotuloDoCodigo() {
    return E.codigo && E.codigo.motivo === 'senha' ? 'Confirmar e receber a senha' : 'Confirmar e entrar';
  }
  function sairDoCodigo(modo) {
    E.codigo = null;
    $('#portaCodigo').hidden = true;
    $('#portaForm').hidden = false;
    $('#portaSub').hidden = false;
    $$('.porta-abas').forEach((a) => { a.hidden = false; });
    $('#portaTitulo').textContent = 'Entre na sua conta';
    trocarModo(modo || 'entrar');
  }
  async function enviarCodigo(ev) {
    ev.preventDefault();
    if (E.ocupado || !E.codigo) return;
    const codigo = $('#cCodigo').value.replace(/\D/g, '');
    if (codigo.length !== 6) { erroCodigo('O código tem 6 números.'); return; }
    E.ocupado = true;
    $('#codigoBt').disabled = true;
    $('#codigoBt').textContent = 'Conferindo…';
    erroCodigo('');
    try {
      if (E.codigo.motivo === 'senha') {
        const email = E.codigo.email;
        const r = await pedir('/api/conta/senha-por-codigo', { email, codigo });
        sairDoCodigo('entrar');
        $('#cEmail').value = email;
        const p = $('#portaErro');
        p.hidden = false;
        p.classList.add('porta-erro-ok');
        p.innerHTML = r && r.como === 'link'
          ? 'Código certo. Esta conta é de antes de guardarmos a senha, então mandamos para <b>'
            + email.replace(/[<>&]/g, '') + '</b> um link para você escolher uma senha nova. Ele vale por 1 hora.'
          : 'Código certo. A sua senha foi enviada para <b>' + email.replace(/[<>&]/g, '')
            + '</b>. Abra o e-mail, copie a senha e entre aqui.';
        return;
      }
      E.estado = await pedir('/api/conta/codigo', { email: E.codigo.email, codigo });
      sairDoCodigo('entrar');
      if (aplicar(E.estado)) recarregar();
    } catch (e) {
      erroCodigo(String(e.message || e));
    } finally {
      E.ocupado = false;
      $('#codigoBt').disabled = false;
      $('#codigoBt').textContent = rotuloDoCodigo();
    }
  }
  async function outroCodigo() {
    if (!E.codigo) return;
    const bt = $('#codigoDeNovo');
    bt.disabled = true;
    try {
      await pedir(E.codigo.motivo === 'senha' ? '/api/conta/recuperar' : '/api/conta/reenviar-codigo',
        { email: E.codigo.email });
      erroCodigo('Pronto: se dois minutos já passaram desde o último, um código novo está a caminho. '
        + 'O anterior deixa de valer.', true);
    } catch (e) {
      erroCodigo(String(e.message || e));
    }
    setTimeout(() => { bt.disabled = false; }, 20000);   // nao deixa metralhar o botao
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

  // Acabou de entrar: a pagina foi montada ANTES do login, com o cofre dos presets fechado,
  // e por isso mostrava "Nenhuma IA nesta secao" e so a musica na lista (14/11/2026, na
  // reinstalacao do dono - parecia que as IAs instaladas tinham sumido). Carrega de novo,
  // agora com tudo aberto.
  function recarregar() {
    document.documentElement.classList.add('conferindo');
    location.reload();
  }

  // ------------------------------------------------------------------ comeco
  async function comecar() {
    // a pagina nasce escondida (marca "conferindo" no index.html) e so aparece aqui, ja com a
    // porta no lugar certo - aconteca o que acontecer la dentro.
    try { await preparar(); } finally { document.documentElement.classList.remove('conferindo'); }
  }

  async function preparar() {
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
    $('#portaCodigo').addEventListener('submit', enviarCodigo);
    $('#codigoDeNovo').addEventListener('click', outroCodigo);
    $('#codigoVoltar').addEventListener('click', () => sairDoCodigo(E.codigo && E.codigo.motivo === 'atualizacao' ? 'criar' : 'entrar'));
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
