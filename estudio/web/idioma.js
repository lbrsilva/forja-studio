/* O idioma da tela: português (padrão) ou inglês.
 *
 * ## A regra de ouro deste arquivo
 *
 * O PORTUGUÊS FICA ESCRITO NO HTML. O inglês só troca por cima, no navegador. Três
 * consequências, e as três são de propósito:
 *
 *   1. tradução que falta não deixa buraco na tela - fica o português, que está certo;
 *   2. dá para traduzir uma tela por vez sem a tela ficar pela metade;
 *   3. quem lê o código (ou o HTML) continua lendo português, que é a língua do projeto.
 *
 * Metade traduzido seria pior que nada: a pessoa troca para inglês e vê uma tela
 * misturada, sem saber se é defeito. Com a sobra em português, o pior caso é "esta
 * parte ainda não foi traduzida" - feio, mas honesto e usável.
 *
 * ## Como marcar um texto para traduzir
 *
 *   <span data-i18n="nav.inicio">Início</span>          texto simples
 *   <h1 data-i18n-html="inicio.titulo">O que ...</h1>    quando tem <em>, <b> dentro
 *   <input data-i18n-attr="placeholder:busca.dica">      atributo (placeholder, title...)
 *
 * O texto português original é guardado na primeira troca, então voltar para o
 * português devolve exatamente o que o HTML trazia.
 *
 * ## Para quem for continuar (11/11/2026)
 *
 * Idiomas: português (o HTML), inglês e espanhol. Para acrescentar um quarto, basta criar
 * o dicionário, pôr a sigla em DICIONARIOS e em ETIQUETA, e um <option> no seletor - nada
 * mais no resto do programa precisa saber que ele existe.
 *
 * Isto cobre a CASCA (topo, menu) e a tela de Início. O resto da tela continua em
 * português mesmo com outro idioma escolhido - e é assim que tem de ser até alguém traduzir.
 *
 * ## NÃO marque texto que o JavaScript reescreve
 *
 * Marcar o title do chip da máquina foi erro meu: o app.js escreve ali o estado da
 * máquina a cada pulso. Trocar de idioma apagava um aviso vivo, e o pulso seguinte
 * apagava a tradução de volta. Só se marca aqui o que está PARADO no HTML.
 * As mensagens que nascem no server.py NÃO passam por aqui: são outro trabalho, e o
 * maior deles.
 */
(function () {
  'use strict';

  var CHAVE = 'forja_idioma';
  var PADRAO = 'pt';

  // ------------------------------------------------------------------ o dicionário
  // Só o inglês: o português é o que já está escrito no HTML.
  var EN = {
    // ---- topo e menu
    'nav.inicio': 'Home',
    'nav.tudo': 'My creations',
    'nav.imagem': 'Image',
    'nav.video': 'Video',
    'nav.apresentador': 'Talking person',
    'nav.plano': 'One-take scene',
    'nav.canal': 'Channel',
    'nav.voz': 'Narration',
    'nav.musica': 'Music',
    'nav.fila': 'Queue',
    'nav.config': 'Settings',
    'nav.secoes': 'Sections',
    'topo.marca': 'JerS Forja Studio — home',

    // ---- o seletor de idioma
    'idioma.rotulo': 'Language',
    'idioma.pt': 'Português',
    'idioma.en': 'English',
    'idioma.es': 'Español',

    // ---- tela de Início
    'inicio.titulo': 'What are we <em>forging</em> today?',
    'inicio.sub': 'Images, video, talking people, narration and music — forged on your own '
      + 'graphics card. No monthly fee, no cloud, no waiting in anyone’s queue.',

    // ---- os cartões das IAs (o texto fixo; o nome e o resumo vêm do preset)
    'ia.velocidade': 'Speed',
    'ia.qualidade': 'Quality',
    'ia.deCinco': '{n} out of 5',
    'ia.carregada': 'already loaded',
    'ia.carregadaDica': 'This was the last AI used: the model should still be in memory, so '
      + 'the next one comes out faster.',
    'ia.escolhida': 'Selected',
    'ia.saiba': 'Learn more',
    'ia.saibaSobre': 'Learn more about {q}',
    'ia.nenhuma': 'No AI available in this section.',
    'ia.quantasNaSecao': '{n} AIs in this section. Tap one to choose it.',
    'ia.recolher': 'Collapse',
    'ia.trocar': 'Switch AI · {n} options',
    'ia.baixando': 'Downloading… {pc}%',
    'ia.de': 'of',
    'ia.faltaAntes': 'Not installed yet —',
    'ia.faltaMao': 'Not installed yet — {gb} GB, download by hand',
    'ia.faltaDica': '{q} is not installed yet. {gb} GB. Click to download.',
    'ia.semLinkDica': '{n} file(s) have no known download address. See IAS-INSTALADAS.md.',
    'ia.confirmaBaixar': 'Download "{q}"?\n\nThat is {gb} GB. You can keep using the studio '
      + 'while it downloads, and if it stops halfway it resumes from where it stopped.',
    'ia.comecando': 'Starting the download.',
    'ia.naoComecou': 'Could not start.',
    'ia.semEstudio': 'I could not reach the studio.',

    // ---- o resto da tela (texto parado no HTML, marcado em 11/11/2026)
    'tela.configuracoes-de-api': 'API settings',
    'tela.sao-todas-opcionais-o-estudio': 'They are all optional: the studio works in full '
      + 'without any of them. Each one unlocks something extra, and stays only on your '
      + 'computer.',
    'tela.entre-na-sua-conta': 'Sign in to your account',
    'tela.as-ferramentas-daqui-sao-de': 'The tools here are free and run on your own graphics '
      + 'card. The account is only so the licence is in your name.',
    'tela.ja-tenho-conta': 'I already have an account',
    'tela.criar-conta': 'Create account',
    'tela.entrar': 'Sign in',
    'tela.esqueci-minha-senha': 'I forgot my password',
    'tela.continue-de-onde-parou': 'Pick up where you left off',
    'tela.sua-maquina': 'Your machine',
    'tela.sem-programar-voce-descreve-ela': 'No coding. You describe it, it writes the '
      + 'shortcut, you click.',
    'tela.o-que-colar-na-conversa': 'What to paste into the chat with the AI (click to open)',
    'tela.cole-este-bloco-e-ela': 'Paste this block and it already knows how to talk to the studio:',
    'tela.conheca-as-ias-do-estudio': 'Meet the studio’s AIs',
    'tela.clique-numa-ia-para-ver': 'Click an AI to see its full sheet.',
    'tela.escolha-a-ia': 'Choose the AI',
    'tela.em-teste-ainda-nao-liberadas': 'In testing — not released yet',
    'tela.como-comecar': 'How to start',
    'tela.clique-arraste-ou-cole-ctrl': 'Click, drag or paste (Ctrl+V) the image',
    'tela.descrever-esta-imagem': 'Describe this image',
    'tela.adicionar-imagens-rosto-roupa-carro': 'Add images (face, clothes, car, scenery…)',
    'tela.video-de-movimento': 'Motion video',
    'tela.1-pessoa-camera-parada-corpo': '1 person, still camera, full body',
    'tela.enquadramento-do-personagem': 'Framing the character',
    'tela.video-1-quadro': 'Video (1st frame)',
    'tela.personagem-enquadrado': 'Character framed',
    'tela.escrever-o-texto': 'Write the text',
    'tela.antes': 'Before',
    'tela.usar-como-prompt': 'Use as prompt',
    'tela.juntar-ao-prompt': 'Add to the prompt',
    'tela.desfazer': 'Undo',
    'tela.voz-e-motor-do-video': 'Voice and video engine',
    'tela.idioma-da-fala': 'Spoken language',
    'tela.escolha-uma-salva-ou-clone': '(pick a saved one or clone a new one)',
    'tela.clonar-uma-voz-nova-envie': 'Clone a new voice: send 10–20 s of the voice alone '
      + '(no music)',
    'tela.opcional': '(optional)',
    'tela.chave-do-elevenlabs': 'ElevenLabs key',
    'tela.opcional-ele-dubla-esse-audio': '(optional · it dubs this audio instead of the text)',
    'tela.clique-ou-arraste-o-audio': 'Click or drag the audio it will speak',
    'tela.motor-do-video': 'Video engine',
    'tela.ajustes': 'Settings',
    'tela.estilo': 'Style',
    'tela.formato': 'Format',
    'tela.resolucao': 'Resolution',
    'tela.duracao': 'Length',
    'tela.qualidade': 'Quality',
    'tela.forca-da-transformacao': 'Strength of the change',
    'tela.baixa-fica-parecida-com-a': 'Low = stays close to the original. High = changes more.',
    'tela.avancado': 'Advanced',
    'tela.vazio-aleatoria-repita-a-mesma': '(empty = random; repeat the same one to redo it '
      + 'identically)',
    'tela.o-painel-de-musica-esta': 'The music panel is off',
    'tela.ele-gera-musicas-com-letra': 'It makes songs with sung lyrics, instrumentals, and '
      + 'separates the voice (YuE2, ACE-Step, MiniMax Music, Stable Audio). Turning it on '
      + 'takes about 30 seconds.',
    'tela.ligar-musica': 'Turn on music',
    'tela.o-que-a-maquina-esta': 'What the machine is making right now',
    'tela.limpar-historico': 'Clear history',
    'tela.sim-limpar': 'Yes, clear it',
    'tela.deixa': 'Never mind',
    'tela.uma-tomada-so-sem-corte': 'One take, no cuts',
    'tela.a-cena-em-portugues': 'The scene, in your own words',
    'tela.duracao-2': 'Length',
    'tela.tamanho-do-quadro': 'Frame size',
    'tela.opcional-2': '(optional)',
    'tela.clique-ou-arraste-a-foto': 'Click or drag the photo (optional — without it, the '
      + 'studio invents the person)',
    'tela.tirar-a-foto': 'Remove the photo',
    'tela.ficha-tecnica-e-o-que': 'Spec sheet and what we have learned',
    'tela.a-configuracao': 'The configuration',
    'tela.o-que-ja-aprendemos': 'What we have learned',
    'tela.gerar-a-tomada': 'Make the take',
    'tela.tomadas-geradas': 'Takes made',
    'tela.nenhuma-tomada-ainda-conte-a': 'No takes yet. Describe the scene on the side, pick '
      + 'the length and click Make the take.',
    'tela.nada-por-aqui-ainda': 'Nothing here yet.',
    'tela.carregar-mais': 'Load more',
    'tela.do-texto-ao-video-pronto': 'From text to finished video',
    'tela.video-novo': 'New video',
    'tela.o-texto-da-narracao': 'The narration text',
    'tela.titulo-vira-o-nome-da': 'Title (becomes the folder name)',
    'tela.0-min-de-placa': '0 min of card time',
    'tela.cancelar': 'Cancel',
    'tela.criar-o-video': 'Create the video',
    'tela.limpar-selecao': 'Clear selection',
    'tela.fazer-os-escolhidos': 'Make the selected ones',
    'tela.imagens-de-apoio': 'Supporting images',
    'tela.quantas-imagens': 'How many images',
    'tela.fechar': 'Close',
    'tela.a-voz-local-esta-desligada': 'The local voice is off',
    'tela.ligar-a-voz-local': 'Turn on the local voice',
    'tela.como-ligar-na-mao-nao': 'How to turn it on by hand / I do not have VoiceStudio',
    'tela.abra-o-voicestudio-icone-na': 'Open VoiceStudio (icon on the Desktop or in the '
      + 'Start menu).',
    'tela.espere-a-janela-dele-carregar': 'Wait for its window to finish loading.',
    'tela.texto-para-fala': 'Text to speech',
    'tela.criar-uma-voz': 'Create a voice',
    'tela.clonar-uma-voz': 'Clone a voice',
    'tela.chave-do-elevenlabs-2': 'ElevenLabs key',
    'tela.salvar': 'Save',
    'tela.remover': 'Remove',
    'tela.nenhuma-voz-escolhida': 'No voice chosen',
    'tela.gerar-narracao': 'Make the narration',
    'tela.descreva-a-voz-que-voce': 'Describe the voice you want',
    'tela.ponto-de-partida': 'Starting point',
    'tela.nome-desta-voz': 'Name for this voice',
    'tela.criar-a-voz': 'Create the voice',
    'tela.audio-de-referencia': 'Reference audio',
    'tela.clique-ou-arraste-um-audio': 'Click or drag a clean audio file — one person only, '
      + 'no music. Send 30 s to 1 min: I pick the best 25 s from inside it',
    'tela.pode-deixar-em-branco': '(you can leave this blank)',
    'tela.nao-sei-descobre-pelo-audio': 'I do not know — work it out from the audio',
    'tela.nome-desta-voz-2': 'Name for this voice',
    'tela.clone-apenas-a-sua-propria': 'Only clone your own voice, or the voice of someone '
      + 'who gave you permission.',
    'tela.clonar-a-voz': 'Clone the voice',
    'tela.configuracoes': 'Settings',
    'tela.voz': 'Voice',
    'tela.apagar-esta-voz': 'Delete this voice',
    'tela.sim-apagar': 'Yes, delete it',
    'tela.deixa-2': 'Never mind',
    'tela.idioma': 'Language',
    'tela.emocao-e-entrega': 'Emotion and delivery',
    'tela.criar-uma-voz-com-essa': 'Create a voice with this delivery',
    'tela.devagar': 'slow',
    'tela.rapido': 'fast',
    'tela.ajuste-fino': 'Fine tuning',
    'tela.rapido-2': 'fast',
    'tela.caprichado': 'careful',
    'tela.mais-passos-mais-tempo-de': 'More steps = more card time for the same speech. At 16 '
      + 'the narration comes out well and faster than real time.',
    'tela.tudo-isto-roda-no-seu': 'All of this runs on your computer. No text leaves here and '
      + 'there is no monthly fee.',

    // ---- as dicas e os campos em branco (title, placeholder, aria-label)
    'dica.como-voce-quer-ser': 'What should we call you',
    'dica.voce-exemplo-com': 'you@example.com',
    'dica.pelo-menos-8-letras': 'at least 8 letters or numbers',
    'dica.mostrar-a-senha': 'Show the password',
    'dica.conte-a-cena-inteira': 'Tell the whole scene, as if you were describing a take.\n\n'
      + 'E.g.: A young man sitting on his bedroom bed, headphones on, presses play on an old '
      + 'tape recorder. He closes his eyes as the tape starts rolling, lowers his head slowly '
      + 'and takes a deep breath.',
    'dica.buscar-no-prompt': 'Search in the prompt',
    'dica.buscar-nas-criacoes': 'Search your creations',
    'dica.filtrar-por-tipo': 'Filter by type',
    'dica.ex-a-pedra-de': 'E.g.: The stone of Ebenezer',
    'dica.cole-aqui-a-narracao': 'Paste the whole narration here.\n\nA hook in the first 5 '
      + 'seconds, one idea only, the reference spoken in full, and a question at the end.',
    'dica.ferramentas-de-voz': 'Voice tools',
    'dica.cole-a-chave-aqui': 'paste the key here',
    'dica.escreva-aqui-o-texto': 'Write the narration text here.\n\nTip: ellipses… are where '
      + 'the voice breathes. Do not write numbers as digits (6:33) — write them out (Matthew '
      + 'six), or it reads them wrong.',
    'dica.ex-homem-idoso-voz': 'E.g.: elderly man, deep voice, calm and warm, speaks slowly '
      + 'like someone telling a story',
    'dica.ponto-de-partida': 'Starting point',
    'dica.ex-senhor-da-varanda': 'E.g.: The man on the porch',
    'dica.as-palavras-que-a': 'The WORDS the person says in the audio, exactly as they say '
      + 'them. When in doubt, leave it empty.',
    'dica.ex-minha-voz': 'E.g.: My voice',
    'dica.configuracoes-da-narracao': 'Narration settings',
    'dica.emocao': 'Emotion',
    'dica.ou-escreva-fale-devagar': 'or write: speak slowly, calmly, like someone telling a story'
  };

  // Espanhol (11/11/2026). Entrou pelos vizinhos: toda a América Latina menos o Brasil.
  // É a língua mais barata de manter ao lado do português, porque as duas andam juntas.
  var ES = {
    // ---- topo e menu
    'nav.inicio': 'Inicio',
    'nav.tudo': 'Mis creaciones',
    'nav.imagem': 'Imagen',
    'nav.video': 'Vídeo',
    'nav.apresentador': 'Persona hablando',
    'nav.plano': 'Plano secuencia',
    'nav.canal': 'Canal',
    'nav.voz': 'Narración',
    'nav.musica': 'Música',
    'nav.fila': 'Cola',
    'nav.config': 'Ajustes',
    'nav.secoes': 'Secciones',
    'topo.marca': 'JerS Forja Studio — inicio',

    // ---- o seletor de idioma
    'idioma.rotulo': 'Idioma',
    'idioma.pt': 'Português',
    'idioma.en': 'English',
    'idioma.es': 'Español',

    // ---- tela de Início
    'inicio.titulo': '¿Qué vamos a <em>forjar</em> hoy?',
    'inicio.sub': 'Imágenes, vídeo, personas hablando, narración y música — forjados en tu '
      + 'propia tarjeta gráfica. Sin mensualidad, sin nube, sin esperar en la cola de nadie.',

    // ---- os cartões das IAs (o texto fixo; o nome e o resumo vêm do preset)
    'ia.velocidade': 'Velocidad',
    'ia.qualidade': 'Calidad',
    'ia.deCinco': '{n} de 5',
    'ia.carregada': 'ya cargada',
    'ia.carregadaDica': 'Fue la última IA usada: el modelo debería seguir en memoria, así '
      + 'que la próxima sale más rápido.',
    'ia.escolhida': 'Elegida',
    'ia.saiba': 'Saber más',
    'ia.saibaSobre': 'Saber más sobre {q}',
    'ia.nenhuma': 'No hay ninguna IA disponible en esta sección.',
    'ia.quantasNaSecao': '{n} IAs en esta sección. Toca una para elegirla.',
    'ia.recolher': 'Plegar',
    'ia.trocar': 'Cambiar de IA · {n} opciones',
    'ia.baixando': 'Descargando… {pc}%',
    'ia.de': 'de',
    'ia.faltaAntes': 'Falta instalar —',
    'ia.faltaMao': 'Falta instalar — {gb} GB, descargar a mano',
    'ia.faltaDica': '{q} todavía no está instalada. {gb} GB. Pulsa para descargar.',
    'ia.semLinkDica': 'Faltan {n} archivo(s) sin dirección de descarga conocida. Mira '
      + 'IAS-INSTALADAS.md.',
    'ia.confirmaBaixar': '¿Descargar "{q}"?\n\nSon {gb} GB. Puedes seguir usando el estudio '
      + 'mientras descarga, y si se corta por la mitad sigue desde donde se quedó.',
    'ia.comecando': 'Empezando a descargar.',
    'ia.naoComecou': 'No se pudo empezar.',
    'ia.semEstudio': 'No conseguí hablar con el estudio.',

    // ---- o resto da tela (texto parado no HTML, marcado em 11/11/2026)
    'tela.configuracoes-de-api': 'Ajustes de API',
    'tela.sao-todas-opcionais-o-estudio': 'Son todas opcionales: el estudio funciona entero '
      + 'sin ninguna. Cada una desbloquea algo más, y se queda solo en tu ordenador.',
    'tela.entre-na-sua-conta': 'Entra en tu cuenta',
    'tela.as-ferramentas-daqui-sao-de': 'Las herramientas de aquí son gratis y generan en tu '
      + 'propia tarjeta gráfica. La cuenta es solo para que la licencia quede a tu nombre.',
    'tela.ja-tenho-conta': 'Ya tengo cuenta',
    'tela.criar-conta': 'Crear cuenta',
    'tela.entrar': 'Entrar',
    'tela.esqueci-minha-senha': 'Olvidé mi contraseña',
    'tela.continue-de-onde-parou': 'Sigue donde lo dejaste',
    'tela.sua-maquina': 'Tu ordenador',
    'tela.sem-programar-voce-descreve-ela': 'Sin programar. Tú lo describes, ella escribe el '
      + 'atajo, tú pulsas.',
    'tela.o-que-colar-na-conversa': 'Qué pegar en la conversación con la IA (pulsa para abrir)',
    'tela.cole-este-bloco-e-ela': 'Pega este bloque y ya sabe hablar con el estudio:',
    'tela.conheca-as-ias-do-estudio': 'Conoce las IAs del estudio',
    'tela.clique-numa-ia-para-ver': 'Pulsa en una IA para ver su ficha completa.',
    'tela.escolha-a-ia': 'Elige la IA',
    'tela.em-teste-ainda-nao-liberadas': 'En pruebas — todavía no liberadas',
    'tela.como-comecar': 'Cómo empezar',
    'tela.clique-arraste-ou-cole-ctrl': 'Pulsa, arrastra o pega (Ctrl+V) la imagen',
    'tela.descrever-esta-imagem': 'Describir esta imagen',
    'tela.adicionar-imagens-rosto-roupa-carro': 'Añadir imágenes (cara, ropa, coche, escenario…)',
    'tela.video-de-movimento': 'Vídeo de movimiento',
    'tela.1-pessoa-camera-parada-corpo': '1 persona, cámara quieta, cuerpo entero',
    'tela.enquadramento-do-personagem': 'Encuadre del personaje',
    'tela.video-1-quadro': 'Vídeo (1.er fotograma)',
    'tela.personagem-enquadrado': 'Personaje encuadrado',
    'tela.escrever-o-texto': 'Escribir el texto',
    'tela.antes': 'Antes',
    'tela.usar-como-prompt': 'Usar como prompt',
    'tela.juntar-ao-prompt': 'Añadir al prompt',
    'tela.desfazer': 'Deshacer',
    'tela.voz-e-motor-do-video': 'Voz y motor del vídeo',
    'tela.idioma-da-fala': 'Idioma del habla',
    'tela.escolha-uma-salva-ou-clone': '(elige una guardada o clona una nueva)',
    'tela.clonar-uma-voz-nova-envie': 'Clonar una voz nueva: envía 10–20 s solo de la voz '
      + '(sin música)',
    'tela.opcional': '(opcional)',
    'tela.chave-do-elevenlabs': 'Clave de ElevenLabs',
    'tela.opcional-ele-dubla-esse-audio': '(opcional · dobla ese audio en vez del texto)',
    'tela.clique-ou-arraste-o-audio': 'Pulsa o arrastra el audio que va a hablar',
    'tela.motor-do-video': 'Motor del vídeo',
    'tela.ajustes': 'Ajustes',
    'tela.estilo': 'Estilo',
    'tela.formato': 'Formato',
    'tela.resolucao': 'Resolución',
    'tela.duracao': 'Duración',
    'tela.qualidade': 'Calidad',
    'tela.forca-da-transformacao': 'Fuerza del cambio',
    'tela.baixa-fica-parecida-com-a': 'Baja = se parece a la original. Alta = cambia más.',
    'tela.avancado': 'Avanzado',
    'tela.vazio-aleatoria-repita-a-mesma': '(vacío = al azar; repite la misma para rehacerla '
      + 'igual)',
    'tela.o-painel-de-musica-esta': 'El panel de música está apagado',
    'tela.ele-gera-musicas-com-letra': 'Hace canciones con letra cantada, instrumentales, y '
      + 'separa la voz (YuE2, ACE-Step, MiniMax Music, Stable Audio). Encenderlo tarda unos '
      + '30 segundos.',
    'tela.ligar-musica': 'Encender la música',
    'tela.o-que-a-maquina-esta': 'Lo que el ordenador está generando ahora',
    'tela.limpar-historico': 'Borrar el historial',
    'tela.sim-limpar': 'Sí, borrar',
    'tela.deixa': 'Déjalo',
    'tela.uma-tomada-so-sem-corte': 'Una sola toma, sin cortes',
    'tela.a-cena-em-portugues': 'La escena, en tus palabras',
    'tela.duracao-2': 'Duración',
    'tela.tamanho-do-quadro': 'Tamaño del fotograma',
    'tela.opcional-2': '(opcional)',
    'tela.clique-ou-arraste-a-foto': 'Pulsa o arrastra la foto (opcional — sin ella, el '
      + 'estudio se inventa a la persona)',
    'tela.tirar-a-foto': 'Quitar la foto',
    'tela.ficha-tecnica-e-o-que': 'Ficha técnica y lo que hemos aprendido',
    'tela.a-configuracao': 'La configuración',
    'tela.o-que-ja-aprendemos': 'Lo que hemos aprendido',
    'tela.gerar-a-tomada': 'Generar la toma',
    'tela.tomadas-geradas': 'Tomas generadas',
    'tela.nenhuma-tomada-ainda-conte-a': 'Todavía no hay tomas. Cuenta la escena al lado, '
      + 'elige la duración y pulsa Generar la toma.',
    'tela.nada-por-aqui-ainda': 'Aquí todavía no hay nada.',
    'tela.carregar-mais': 'Cargar más',
    'tela.do-texto-ao-video-pronto': 'Del texto al vídeo terminado',
    'tela.video-novo': 'Vídeo nuevo',
    'tela.o-texto-da-narracao': 'El texto de la narración',
    'tela.titulo-vira-o-nome-da': 'Título (será el nombre de la carpeta)',
    'tela.0-min-de-placa': '0 min de tarjeta',
    'tela.cancelar': 'Cancelar',
    'tela.criar-o-video': 'Crear el vídeo',
    'tela.limpar-selecao': 'Limpiar la selección',
    'tela.fazer-os-escolhidos': 'Hacer los elegidos',
    'tela.imagens-de-apoio': 'Imágenes de apoyo',
    'tela.quantas-imagens': 'Cuántas imágenes',
    'tela.fechar': 'Cerrar',
    'tela.a-voz-local-esta-desligada': 'La voz local está apagada',
    'tela.ligar-a-voz-local': 'Encender la voz local',
    'tela.como-ligar-na-mao-nao': 'Cómo encenderla a mano / no tengo VoiceStudio',
    'tela.abra-o-voicestudio-icone-na': 'Abre VoiceStudio (icono en el Escritorio o en el '
      + 'menú Inicio).',
    'tela.espere-a-janela-dele-carregar': 'Espera a que su ventana termine de cargar.',
    'tela.texto-para-fala': 'Texto a voz',
    'tela.criar-uma-voz': 'Crear una voz',
    'tela.clonar-uma-voz': 'Clonar una voz',
    'tela.chave-do-elevenlabs-2': 'Clave de ElevenLabs',
    'tela.salvar': 'Guardar',
    'tela.remover': 'Quitar',
    'tela.nenhuma-voz-escolhida': 'Ninguna voz elegida',
    'tela.gerar-narracao': 'Generar la narración',
    'tela.descreva-a-voz-que-voce': 'Describe la voz que quieres',
    'tela.ponto-de-partida': 'Punto de partida',
    'tela.nome-desta-voz': 'Nombre de esta voz',
    'tela.criar-a-voz': 'Crear la voz',
    'tela.audio-de-referencia': 'Audio de referencia',
    'tela.clique-ou-arraste-um-audio': 'Pulsa o arrastra un audio limpio — una sola persona, '
      + 'sin música. Manda de 30 s a 1 min: yo elijo los mejores 25 s de dentro',
    'tela.pode-deixar-em-branco': '(puedes dejarlo en blanco)',
    'tela.nao-sei-descobre-pelo-audio': 'No lo sé — descúbrelo por el audio',
    'tela.nome-desta-voz-2': 'Nombre de esta voz',
    'tela.clone-apenas-a-sua-propria': 'Clona solo tu propia voz, o la de quien te haya dado '
      + 'permiso.',
    'tela.clonar-a-voz': 'Clonar la voz',
    'tela.configuracoes': 'Configuración',
    'tela.voz': 'Voz',
    'tela.apagar-esta-voz': 'Borrar esta voz',
    'tela.sim-apagar': 'Sí, borrar',
    'tela.deixa-2': 'Déjalo',
    'tela.idioma': 'Idioma',
    'tela.emocao-e-entrega': 'Emoción y entrega',
    'tela.criar-uma-voz-com-essa': 'Crear una voz con esa entrega',
    'tela.devagar': 'despacio',
    'tela.rapido': 'rápido',
    'tela.ajuste-fino': 'Ajuste fino',
    'tela.rapido-2': 'rápido',
    'tela.caprichado': 'cuidado',
    'tela.mais-passos-mais-tempo-de': 'Más pasos = más tiempo de tarjeta para la misma frase. '
      + 'En 16 la narración sale bien y más rápida que el tiempo real.',
    'tela.tudo-isto-roda-no-seu': 'Todo esto funciona en tu ordenador. Ningún texto sale de '
      + 'aquí y no hay ninguna mensualidad.',

    // ---- as dicas e os campos em branco (title, placeholder, aria-label)
    'dica.como-voce-quer-ser': 'Cómo quieres que te llamemos',
    'dica.voce-exemplo-com': 'tu@ejemplo.com',
    'dica.pelo-menos-8-letras': 'al menos 8 letras o números',
    'dica.mostrar-a-senha': 'Mostrar la contraseña',
    'dica.conte-a-cena-inteira': 'Cuenta la escena entera, como si describieras una toma.\n\n'
      + 'Ej.: Un chico sentado en la cama de su cuarto, con auriculares, pulsa play en una '
      + 'grabadora antigua. Cierra los ojos mientras la cinta empieza a girar, baja la cabeza '
      + 'despacio y respira hondo.',
    'dica.buscar-no-prompt': 'Buscar en el prompt',
    'dica.buscar-nas-criacoes': 'Buscar en tus creaciones',
    'dica.filtrar-por-tipo': 'Filtrar por tipo',
    'dica.ex-a-pedra-de': 'Ej.: La piedra de Ebenezer',
    'dica.cole-aqui-a-narracao': 'Pega aquí la narración entera.\n\nUn gancho en los primeros '
      + '5 segundos, una sola idea, la referencia dicha completa y una pregunta al final.',
    'dica.ferramentas-de-voz': 'Herramientas de voz',
    'dica.cole-a-chave-aqui': 'pega la clave aquí',
    'dica.escreva-aqui-o-texto': 'Escribe aquí el texto de la narración.\n\nConsejo: los '
      + 'puntos suspensivos… son donde la voz respira. No escribas números en cifras (6:33) — '
      + 'escríbelos con letras (Mateo seis), o los lee mal.',
    'dica.ex-homem-idoso-voz': 'Ej.: hombre mayor, voz grave, tranquila y acogedora, habla '
      + 'despacio como quien cuenta una historia',
    'dica.ponto-de-partida': 'Punto de partida',
    'dica.ex-senhor-da-varanda': 'Ej.: El señor del porche',
    'dica.as-palavras-que-a': 'Las PALABRAS que la persona dice en el audio, tal como las '
      + 'dice. Si dudas, déjalo vacío.',
    'dica.ex-minha-voz': 'Ej.: Mi voz',
    'dica.configuracoes-da-narracao': 'Configuración de la narración',
    'dica.emocao': 'Emoción',
    'dica.ou-escreva-fale-devagar': 'o escribe: habla despacio, con calma, como quien cuenta '
      + 'una historia'
  };

  // O português NÃO entra aqui: ele é o que já está escrito no HTML.
  var DICIONARIOS = { en: EN, es: ES };

  // ------------------------------------------------------- as frases soltas do app.js
  // Aqui a chave É a frase em português, do jeito que está escrita no código. Ver tx().
  var FRASES_EN = {
    // avisos que aparecem no canto da tela
    'Bloco copiado. Cole na conversa com a IA de código.':
      'Block copied. Paste it into the chat with the coding AI.',
    'Carregando as IAs do estúdio… a seção abre sozinha em instantes.':
      'Loading the studio’s AIs… the section opens by itself in a moment.',
    'Configurações carregadas no formulário. Ajuste o que quiser e clique em Gerar.':
      'Settings loaded into the form. Change whatever you like and click Generate.',
    'Envie a imagem primeiro.': 'Send the image first.',
    'Essa IA foi removida do estúdio: não dá para reusar este trabalho.':
      'This AI was removed from the studio: this job cannot be reused.',
    'Esse tipo de arquivo não serve aqui.': 'That kind of file does not work here.',
    'Geração cancelada.': 'Generation cancelled.',
    'Não consegui apagar a voz: ': 'I could not delete the voice: ',
    'Não consegui cancelar: ': 'I could not cancel: ',
    'Não consegui copiar (o navegador bloqueou). Selecione o texto e use Ctrl+C.':
      'I could not copy (the browser blocked it). Select the text and press Ctrl+C.',
    'Não consegui copiar sozinho — o bloco está selecionado, use Ctrl+C.':
      'I could not copy it myself — the block is selected, press Ctrl+C.',
    'Não consegui ligar a música: ': 'I could not turn the music on: ',
    'Não consegui ligar agora: ': 'I could not turn it on right now: ',
    'Não consegui remover: ': 'I could not remove it: ',
    'Não consegui tocar essa música (o painel de música está ligado?).':
      'I could not play that track (is the music panel on?).',
    'Prompt copiado.': 'Prompt copied.',
    'Tem geração rodando ou na fila: espere terminar para liberar a memória.':
      'Something is generating or waiting in the queue: wait for it to finish before freeing memory.',
    'Voz apagada.': 'Voice deleted.',
    'Já estava ligado (ou ligando).': 'It was already on (or turning on).',
    'Memória liberada: os modelos foram descarregados.':
      'Memory freed: the models were unloaded.',
    'Não deu para liberar agora.': 'It could not be freed right now.',
    'Painel de música ligado.': 'Music panel is on.',
    'O painel de música não respondeu a tempo. Tente de novo em instantes.':
      'The music panel did not answer in time. Try again in a moment.',
    'Começando a baixar.': 'Starting the download.',
    'Não deu para começar.': 'Could not start.',
    'Não consegui falar com o estúdio.': 'I could not reach the studio.',

    // quando o estúdio não responde
    'O estúdio demorou demais para responder.': 'The studio took too long to answer.',
    'Sem resposta do estúdio (o servidor está ligado?).':
      'No answer from the studio (is the server running?).',
    'O servidor do estúdio teve um erro interno (500).':
      'The studio server hit an internal error (500).',
    'Não encontrado (404).': 'Not found (404).',
    'Resposta incompleta do estúdio.': 'Incomplete answer from the studio.',

    // o chip da máquina, no alto
    'Estúdio sem resposta': 'Studio not answering',
    'tentando de novo…': 'trying again…',
    'O estúdio não respondeu agora. A tela tenta de novo sozinha a cada poucos segundos.':
      'The studio did not answer just now. The screen retries by itself every few seconds.',
    'Nada gerando agora. Clique para ver a sua máquina no Início.':
      'Nothing generating right now. Click to see your machine on the Home screen.',
    'Trabalhos do estúdio esperando a vez na placa de vídeo (uma geração por vez).':
      'Studio jobs waiting their turn on the graphics card (one generation at a time).',
    'A IA de texto está usando a placa de vídeo por alguns segundos (ela sai sozinha ao terminar).':
      'The text AI is using the graphics card for a few seconds (it leaves on its own when done).',
    'A ComfyUI de imagem e vídeo está ligando (leva 1–2 min).':
      'The image and video ComfyUI is starting up (takes 1–2 min).',
    'A ComfyUI de imagem e vídeo está desligada. Clique para ir ao Início e ligar.':
      'The image and video ComfyUI is off. Click to go Home and turn it on.',
    'A ComfyUI de vídeo está gerando algo que não foi pedido pelo estúdio.':
      'The video ComfyUI is generating something the studio did not ask for.',

    // os cartões do Início
    'Fotos realistas, ilustrações, cartazes com texto escrito certo e transformação de uma imagem sua.':
      'Realistic photos, illustration, posters with the text spelled right, and turning an '
      + 'image of yours into something else.',
    'Texto ou imagem viram vídeo: com som, emendando cenas ou copiando o movimento de um vídeo real.':
      'Text or an image becomes video: with sound, stitching scenes, or copying the motion of '
      + 'a real video.',
    'Uma foto de frente e um texto viram alguém falando para a câmera, com voz e boca sincronizada.':
      'A front-facing photo and a text become someone speaking to the camera, with the voice '
      + 'and lips in sync.',
    'Pessoa de verdade numa tomada contínua, sem corte: a cena sai inteira, de 16 a 32 segundos.':
      'A real person in one continuous take, no cuts: the scene comes out whole, 16 to 32 seconds.',
    'Texto vira voz falada no seu computador, de graça: criar uma voz pela descrição ou clonar a sua.':
      'Text becomes a spoken voice on your computer, for free: create a voice from a '
      + 'description or clone your own.',
    'Músicas com letra cantada, instrumentais, covers e separação da voz (YuE2, ACE-Step e outros).':
      'Songs with sung lyrics, instrumentals, covers and voice separation (YuE2, ACE-Step and others).',

    // nomes das seções
    'Início': 'Home', 'Imagem': 'Image', 'Vídeo': 'Video', 'Pessoa falando': 'Talking person',
    'Narração': 'Narration', 'Canal automático': 'Automatic channel',
    'Plano-sequência': 'One-take scene', 'Música': 'Music', 'Fila': 'Queue',
    'Minhas criações': 'My creations',
    'Criar imagem': 'Create image', 'Criar vídeo': 'Create video', 'Apresentador': 'Presenter',
    'Criações de imagem': 'Image creations', 'Criações de vídeo': 'Video creations',
    'Pessoas falando': 'Talking people',
    'Gerar imagem': 'Generate image', 'Gerar vídeo': 'Generate video',
    'Gerar pessoa falando': 'Generate talking person',
    'Nenhuma imagem ainda. Escolha uma IA, descreva a ideia e clique em Gerar imagem.':
      'No images yet. Choose an AI, describe the idea and click Generate image.',
    'Nenhum vídeo ainda. Escolha uma IA, descreva a cena e clique em Gerar vídeo.':
      'No videos yet. Choose an AI, describe the scene and click Generate video.',
    'Nenhum vídeo de pessoa falando ainda. Envie uma foto de frente, escreva o texto e clique em Gerar.':
      'No talking-person videos yet. Send a front-facing photo, write the text and click Generate.',

    // a ficha da IA
    'O que faz': 'What it does', 'Melhor para': 'Best for', 'Evite para': 'Avoid it for',
    'Tempo típico (medido nesta máquina)': 'Typical time (measured on this machine)',
    // ---- a seção Configurações de API
    'guardada': 'saved',
    'não tem nenhuma — e tudo bem': 'none saved — and that is fine',
    'Onde criar a chave': 'Where to create the key',
    'já tem uma guardada — cole outra para trocar': 'one is saved — paste another to replace it',
    'cole aqui': 'paste it here',
    'Salvar': 'Save',
    'Remover': 'Remove',
    'fica só no seu computador, em': 'stays only on your computer, in',
    'Remover esta chave? O estúdio continua funcionando sem ela.':
      'Remove this key? The studio keeps working without it.',
    'Cole a chave no campo antes de salvar.': 'Paste the key into the box before saving.',
    'Pronto.': 'Done.',
    'Crie uma conta (é de graça)': 'Create an account (it is free)',
    'Aceite a licença nesta página': 'Accept the licence on this page',
    'Crie um token de LEITURA e cole aqui': 'Create a READ token and paste it here',
    'vozes na nuvem, na aba Narração. Sem ela, a narração continua funcionando com as vozes locais, de graça.':
      'cloud voices, on the Narration tab. Without it, narration keeps working with the '
      + 'local voices, for free.',
    'baixar o LTX 2.5. Dos 19 repositórios de modelos, 18 abrem sem nada; só o Lightricks/LTX-2.5 pede conta e aceitar a licença.':
      'downloading LTX 2.5. Of the 19 model repositories, 18 open with nothing; only '
      + 'Lightricks/LTX-2.5 asks for an account and the licence.',
    'A mais rápida e a mais caprichada': 'The fastest and the most careful',
    // ---- ligar e desligar os serviços
    'Serviços': 'Services', 'Ligar tudo': 'Turn all on', 'Desligar tudo': 'Turn all off',
    'Ligar imagem e vídeo': 'Turn on image and video', 'Ligar música': 'Turn on music',
    'Desligar': 'Turn off', 'Abrir': 'Open', 'Desligando…': 'Turning off…',
    'Desligado.': 'Turned off.', 'porta': 'port',
    'Imagem e vídeo (ComfyUI)': 'Image and video (ComfyUI)',
    'Painel de música': 'Music panel', 'ComfyUI de música': 'Music ComfyUI',
    'ACE-Step (música)': 'ACE-Step (music)', 'Hermes (IA que conversa)': 'Hermes (the AI that talks)',
    'Telegram do Hermes (avisos no celular)': 'Hermes Telegram (alerts on your phone)',
    'Ligar tudo o que está desligado': 'Turn on everything that is off',
    'Desligar todas as IAs para liberar memória': 'Turn off every AI to free memory',
    'Ligar a IA de imagem e vídeo (ComfyUI)': 'Turn on the image and video AI (ComfyUI)',
    'Ligar as IAs de música (painel, ComfyUI de música e ACE-Step)':
      'Turn on the music AIs (panel, music ComfyUI and ACE-Step)',
    'Desligar todas as IAs para liberar memória? (A página continua aberta. Para usar de novo, clique em Ligar.)':
      'Turn off every AI to free memory? (The page stays open. To use them again, click Turn on.)',
    'Desliga para liberar memória; liga de novo pelo botão Ligar':
      'Turns it off to free memory; turn it back on with the Turn on button',
    'Abrir o Hermes no navegador': 'Open Hermes in the browser',
    'Abrir o painel do Hermes': 'Open the Hermes panel',
    'Ligando a ComfyUI de imagem e vídeo (leva 1–2 min)…':
      'Starting the image and video ComfyUI (takes 1–2 min)…',
    'Ligando a música (painel, ComfyUI de música e ACE-Step)…':
      'Starting the music (panel, music ComfyUI and ACE-Step)…',
    'Ligando a IA de texto no processador…': 'Starting the text AI on the processor…',
    'Ligando o Hermes (painel web, uns 6 s)…': 'Starting Hermes (web panel, about 6 s)…',
    'Ligando o Telegram do Hermes (uns 20 s)…': 'Starting the Hermes Telegram (about 20 s)…',
    'Ligando o que estava desligado…': 'Starting whatever was off…',
    'Ligando o painel de música…': 'Starting the music panel…',
    'Para ter o botão Desligar, feche e abra o estúdio de novo.':
      'To get the Turn off button, close and open the studio again.',
    'Não consegui guardar a preferência: ': 'I could not save the preference: ',
    'Esta versão do servidor do estúdio ainda não liga os serviços pelo Início. Feche o estúdio pelo atalho “Desligar Estúdio” (com nada gerando) e abra de novo para ativar os botões.':
      'This version of the studio server cannot start the services from the Home screen yet. '
      + 'Close the studio with the “Desligar Estúdio” shortcut (with nothing generating) '
      + 'and open it again to enable the buttons.',
    'Mais rápida': 'Fastest',

    // Os botõezinhos de ajuste. ⚠ A CHAVE É O TEXTO DEPOIS DO rot(): o preset guarda
    // "Rapido (8 passos)" sem acento, o rot() acentua, e só então o TX procura. Chave
    // sem acento aqui não acha nada - e não dá erro, só fica em português para sempre.
    'Livre': 'Free', 'Traço artístico': 'Artistic line', 'Cartoon 2D': '2D cartoon',
    'Ghibli aquarela': 'Ghibli watercolour',
    'Rápido': 'Fast', 'Rápido (4 passos)': 'Fast (4 steps)', 'Rápido (8 passos)': 'Fast (8 steps)',
    'Turbo (8 passos)': 'Turbo (8 steps)', 'Turbo (12 passos)': 'Turbo (12 steps)',
    'Normal': 'Normal', 'Normal (20 passos)': 'Normal (20 steps)',
    'Caprichado': 'Careful', 'Caprichado (30 passos)': 'Careful (30 steps)',
    'Máxima': 'Maximum', 'Máxima (48 passos)': 'Maximum (48 steps)',
    '1:1 grande (2048)': '1:1 large (2048)',
    'Só texto': 'Text only', 'Com imagem': 'With an image',
    'Personagem + movimento': 'Character + motion',
    'Começar de uma imagem': 'Start from an image',
    'Primeiro/último quadro': 'First/last frame',
    'Com imagens de referência': 'With reference images',
    'Com imagem de referência': 'With a reference image',

    // mensagens do caminho de trabalho
    'Enviando e convertendo para 16 fps…': 'Uploading and converting to 16 fps…',
    'Detectando a pose… (alguns segundos; se a GPU estiver gerando, espera a geração atual)':
      'Detecting the pose… (a few seconds; if the GPU is busy generating, it waits for the '
      + 'current job)',
    'Usa a imagem como está. Se o vídeo for de perto e a imagem de corpo inteiro, o personagem pode sair cortado.':
      'Uses the image as it is. If the video is a close-up and the image is full body, the '
      + 'character may end up cropped.',
    'Envie a imagem e o vídeo: o personagem é recortado para ficar do mesmo tamanho e posição da pessoa do vídeo.':
      'Send the image and the video: the character is cropped to match the size and position '
      + 'of the person in the video.',
    'modelo já carregado (mais rápido)': 'model already loaded (faster)',
    'baseada nas suas gerações': 'based on your own generations',
    'estimativa inicial (melhora com o uso)': 'first estimate (gets better with use)',
    'Uma chave esta guardada e funcionando.': 'A key is stored and working.',
    'uma chave ja esta guardada — cole outra para trocar':
      'a key is already stored — paste another one to replace it',
    'Conferindo a chave com o ElevenLabs…': 'Checking the key with ElevenLabs…',
    'Nova (ainda não salva)': 'New (not saved yet)',
    'Voz padrão': 'Default voice',
    'Voz nova enviada. Dê um nome e salve para reusar depois sem enviar de novo.':
      'New voice uploaded. Give it a name and save it to reuse later without uploading again.',
    'Escreva um nome para a voz.': 'Write a name for the voice.',
    'rodou na placa de vídeo': 'ran on the graphics card',
    'Texto escrito pela IA': 'Text written by the AI',
    'Descrição da imagem': 'Description of the image',
    'A placa de vídeo estava ocupada: a IA rápida rodou no processador para não atrapalhar a geração.':
      'The graphics card was busy: the fast AI ran on the processor so it would not get in the '
      + 'way of the generation.',
    'Rodou na placa de vídeo e foi descarregada dela logo depois (a placa já está livre de novo).':
      'It ran on the graphics card and was unloaded right after (the card is free again).',
    'Escreva o TEMA na caixa (ex.: 3 dicas para dormir melhor) e clique de novo.':
      'Write the TOPIC in the box (e.g. 3 tips for sleeping better) and click again.',
    'Escreva o pedido primeiro (pode ser curto, em português).':
      'Write what you want first (it can be short).',
    'Começando…': 'Starting…',
    'Não deu certo: ': 'It did not work: ',
    'Vídeo do trabalho reusado': 'Video from the reused job',
    'Áudio do trabalho reusado': 'Audio from the reused job',
    'Com erro ou cancelados': 'Failed or cancelled',
    'Carregar estas configurações no formulário': 'Load these settings into the form',
    'Essa IA foi removida do estúdio: não dá para reusar':
      'This AI was removed from the studio: it cannot be reused',
    'O arquivo já não está no HD: tira este trabalho da lista (e apaga o que sobrou dele)':
      'The file is no longer on the drive: removes this job from the list (and deletes what is '
      + 'left of it)',
    'Cancelar esta geração?': 'Cancel this generation?',
    'Cancelar geração': 'Cancel generation',
    'A ComfyUI não respondeu; o trabalho foi marcado como cancelado aqui.':
      'ComfyUI did not answer; the job was marked as cancelled here.',
    'Esta versão do servidor do estúdio manda só as 120 criações mais recentes desta aba; as mais antigas continuam no HD (pasta output da ComfyUI).':
      'This version of the studio server only sends the 120 most recent creations of this tab; '
      + 'the older ones are still on the drive (ComfyUI’s output folder).'
  };

  var FRASES_ES = {
    'Bloco copiado. Cole na conversa com a IA de código.':
      'Bloque copiado. Pégalo en la conversación con la IA de programación.',
    'Carregando as IAs do estúdio… a seção abre sozinha em instantes.':
      'Cargando las IAs del estudio… la sección se abre sola en un momento.',
    'Configurações carregadas no formulário. Ajuste o que quiser e clique em Gerar.':
      'Ajustes cargados en el formulario. Cambia lo que quieras y pulsa Generar.',
    'Envie a imagem primeiro.': 'Envía primero la imagen.',
    'Essa IA foi removida do estúdio: não dá para reusar este trabalho.':
      'Esa IA se quitó del estudio: este trabajo no se puede reutilizar.',
    'Esse tipo de arquivo não serve aqui.': 'Ese tipo de archivo no sirve aquí.',
    'Geração cancelada.': 'Generación cancelada.',
    'Não consegui apagar a voz: ': 'No pude borrar la voz: ',
    'Não consegui cancelar: ': 'No pude cancelar: ',
    'Não consegui copiar (o navegador bloqueou). Selecione o texto e use Ctrl+C.':
      'No pude copiar (el navegador lo bloqueó). Selecciona el texto y pulsa Ctrl+C.',
    'Não consegui copiar sozinho — o bloco está selecionado, use Ctrl+C.':
      'No pude copiarlo solo — el bloque está seleccionado, pulsa Ctrl+C.',
    'Não consegui ligar a música: ': 'No pude encender la música: ',
    'Não consegui ligar agora: ': 'No pude encenderlo ahora: ',
    'Não consegui remover: ': 'No pude quitarlo: ',
    'Não consegui tocar essa música (o painel de música está ligado?).':
      'No pude reproducir esa música (¿está encendido el panel de música?).',
    'Prompt copiado.': 'Prompt copiado.',
    'Tem geração rodando ou na fila: espere terminar para liberar a memória.':
      'Hay algo generándose o en la cola: espera a que termine para liberar la memoria.',
    'Voz apagada.': 'Voz borrada.',
    'Já estava ligado (ou ligando).': 'Ya estaba encendido (o encendiéndose).',
    'Memória liberada: os modelos foram descarregados.':
      'Memoria liberada: los modelos se descargaron.',
    'Não deu para liberar agora.': 'No se pudo liberar ahora.',
    'Painel de música ligado.': 'Panel de música encendido.',
    'O painel de música não respondeu a tempo. Tente de novo em instantes.':
      'El panel de música no respondió a tiempo. Inténtalo de nuevo en un momento.',
    'Começando a baixar.': 'Empezando a descargar.',
    'Não deu para começar.': 'No se pudo empezar.',
    'Não consegui falar com o estúdio.': 'No conseguí hablar con el estudio.',

    'O estúdio demorou demais para responder.': 'El estudio tardó demasiado en responder.',
    'Sem resposta do estúdio (o servidor está ligado?).':
      'Sin respuesta del estudio (¿está encendido el servidor?).',
    'O servidor do estúdio teve um erro interno (500).':
      'El servidor del estudio tuvo un error interno (500).',
    'Não encontrado (404).': 'No encontrado (404).',
    'Resposta incompleta do estúdio.': 'Respuesta incompleta del estudio.',

    'Estúdio sem resposta': 'El estudio no responde',
    'tentando de novo…': 'intentándolo de nuevo…',
    'O estúdio não respondeu agora. A tela tenta de novo sozinha a cada poucos segundos.':
      'El estudio no respondió ahora. La pantalla lo vuelve a intentar sola cada pocos segundos.',
    'Nada gerando agora. Clique para ver a sua máquina no Início.':
      'No se está generando nada. Pulsa para ver tu ordenador en Inicio.',
    'Trabalhos do estúdio esperando a vez na placa de vídeo (uma geração por vez).':
      'Trabajos del estudio esperando turno en la tarjeta gráfica (una generación cada vez).',
    'A IA de texto está usando a placa de vídeo por alguns segundos (ela sai sozinha ao terminar).':
      'La IA de texto está usando la tarjeta gráfica unos segundos (se va sola al terminar).',
    'A ComfyUI de imagem e vídeo está ligando (leva 1–2 min).':
      'La ComfyUI de imagen y vídeo se está encendiendo (tarda 1–2 min).',
    'A ComfyUI de imagem e vídeo está desligada. Clique para ir ao Início e ligar.':
      'La ComfyUI de imagen y vídeo está apagada. Pulsa para ir a Inicio y encenderla.',
    'A ComfyUI de vídeo está gerando algo que não foi pedido pelo estúdio.':
      'La ComfyUI de vídeo está generando algo que el estudio no pidió.',

    'Fotos realistas, ilustrações, cartazes com texto escrito certo e transformação de uma imagem sua.':
      'Fotos realistas, ilustraciones, carteles con el texto bien escrito y transformación de '
      + 'una imagen tuya.',
    'Texto ou imagem viram vídeo: com som, emendando cenas ou copiando o movimento de um vídeo real.':
      'Texto o imagen se convierten en vídeo: con sonido, enlazando escenas o copiando el '
      + 'movimiento de un vídeo real.',
    'Uma foto de frente e um texto viram alguém falando para a câmera, com voz e boca sincronizada.':
      'Una foto de frente y un texto se convierten en alguien hablando a la cámara, con la voz '
      + 'y la boca sincronizadas.',
    'Pessoa de verdade numa tomada contínua, sem corte: a cena sai inteira, de 16 a 32 segundos.':
      'Una persona de verdad en una toma continua, sin cortes: la escena sale entera, de 16 a '
      + '32 segundos.',
    'Texto vira voz falada no seu computador, de graça: criar uma voz pela descrição ou clonar a sua.':
      'El texto se convierte en voz hablada en tu ordenador, gratis: crea una voz por '
      + 'descripción o clona la tuya.',
    'Músicas com letra cantada, instrumentais, covers e separação da voz (YuE2, ACE-Step e outros).':
      'Canciones con letra cantada, instrumentales, versiones y separación de la voz (YuE2, '
      + 'ACE-Step y otros).',

    'Início': 'Inicio', 'Imagem': 'Imagen', 'Vídeo': 'Vídeo', 'Pessoa falando': 'Persona hablando',
    'Narração': 'Narración', 'Canal automático': 'Canal automático',
    'Plano-sequência': 'Plano secuencia', 'Música': 'Música', 'Fila': 'Cola',
    'Minhas criações': 'Mis creaciones',
    'Criar imagem': 'Crear imagen', 'Criar vídeo': 'Crear vídeo', 'Apresentador': 'Presentador',
    'Criações de imagem': 'Creaciones de imagen', 'Criações de vídeo': 'Creaciones de vídeo',
    'Pessoas falando': 'Personas hablando',
    'Gerar imagem': 'Generar imagen', 'Gerar vídeo': 'Generar vídeo',
    'Gerar pessoa falando': 'Generar persona hablando',
    'Nenhuma imagem ainda. Escolha uma IA, descreva a ideia e clique em Gerar imagem.':
      'Todavía no hay imágenes. Elige una IA, describe la idea y pulsa Generar imagen.',
    'Nenhum vídeo ainda. Escolha uma IA, descreva a cena e clique em Gerar vídeo.':
      'Todavía no hay vídeos. Elige una IA, describe la escena y pulsa Generar vídeo.',
    'Nenhum vídeo de pessoa falando ainda. Envie uma foto de frente, escreva o texto e clique em Gerar.':
      'Todavía no hay vídeos de persona hablando. Envía una foto de frente, escribe el texto y '
      + 'pulsa Generar.',

    'O que faz': 'Qué hace', 'Melhor para': 'Mejor para', 'Evite para': 'Evítala para',
    'Tempo típico (medido nesta máquina)': 'Tiempo típico (medido en este ordenador)',
    // ---- a seção Configurações de API
    'guardada': 'guardada',
    'não tem nenhuma — e tudo bem': 'no hay ninguna — y está bien',
    'Onde criar a chave': 'Dónde crear la clave',
    'já tem uma guardada — cole outra para trocar': 'ya hay una guardada — pega otra para cambiarla',
    'cole aqui': 'pégala aquí',
    'Salvar': 'Guardar',
    'Remover': 'Quitar',
    'fica só no seu computador, em': 'se queda solo en tu ordenador, en',
    'Remover esta chave? O estúdio continua funcionando sem ela.':
      '¿Quitar esta clave? El estudio sigue funcionando sin ella.',
    'Cole a chave no campo antes de salvar.': 'Pega la clave en la caja antes de guardar.',
    'Pronto.': 'Listo.',
    'Crie uma conta (é de graça)': 'Crea una cuenta (es gratis)',
    'Aceite a licença nesta página': 'Acepta la licencia en esta página',
    'Crie um token de LEITURA e cole aqui': 'Crea un token de LECTURA y pégalo aquí',
    'vozes na nuvem, na aba Narração. Sem ela, a narração continua funcionando com as vozes locais, de graça.':
      'voces en la nube, en la pestaña Narración. Sin ella, la narración sigue funcionando '
      + 'con las voces locales, gratis.',
    'baixar o LTX 2.5. Dos 19 repositórios de modelos, 18 abrem sem nada; só o Lightricks/LTX-2.5 pede conta e aceitar a licença.':
      'descargar LTX 2.5. De los 19 repositorios de modelos, 18 se abren sin nada; solo '
      + 'Lightricks/LTX-2.5 pide cuenta y aceptar la licencia.',
    'A mais rápida e a mais caprichada': 'La más rápida y la más cuidada',
    // ---- ligar e desligar os serviços
    'Serviços': 'Servicios', 'Ligar tudo': 'Encender todo', 'Desligar tudo': 'Apagar todo',
    'Ligar imagem e vídeo': 'Encender imagen y vídeo', 'Ligar música': 'Encender la música',
    'Desligar': 'Apagar', 'Abrir': 'Abrir', 'Desligando…': 'Apagando…',
    'Desligado.': 'Apagado.', 'porta': 'puerto',
    'Imagem e vídeo (ComfyUI)': 'Imagen y vídeo (ComfyUI)',
    'Painel de música': 'Panel de música', 'ComfyUI de música': 'ComfyUI de música',
    'ACE-Step (música)': 'ACE-Step (música)', 'Hermes (IA que conversa)': 'Hermes (la IA que conversa)',
    'Telegram do Hermes (avisos no celular)': 'Telegram de Hermes (avisos en el móvil)',
    'Ligar tudo o que está desligado': 'Encender todo lo que está apagado',
    'Desligar todas as IAs para liberar memória': 'Apagar todas las IAs para liberar memoria',
    'Ligar a IA de imagem e vídeo (ComfyUI)': 'Encender la IA de imagen y vídeo (ComfyUI)',
    'Ligar as IAs de música (painel, ComfyUI de música e ACE-Step)':
      'Encender las IAs de música (panel, ComfyUI de música y ACE-Step)',
    'Desligar todas as IAs para liberar memória? (A página continua aberta. Para usar de novo, clique em Ligar.)':
      '¿Apagar todas las IAs para liberar memoria? (La página sigue abierta. Para usarlas otra '
      + 'vez, pulsa Encender.)',
    'Desliga para liberar memória; liga de novo pelo botão Ligar':
      'Lo apaga para liberar memoria; se vuelve a encender con el botón Encender',
    'Abrir o Hermes no navegador': 'Abrir Hermes en el navegador',
    'Abrir o painel do Hermes': 'Abrir el panel de Hermes',
    'Ligando a ComfyUI de imagem e vídeo (leva 1–2 min)…':
      'Encendiendo la ComfyUI de imagen y vídeo (tarda 1–2 min)…',
    'Ligando a música (painel, ComfyUI de música e ACE-Step)…':
      'Encendiendo la música (panel, ComfyUI de música y ACE-Step)…',
    'Ligando a IA de texto no processador…': 'Encendiendo la IA de texto en el procesador…',
    'Ligando o Hermes (painel web, uns 6 s)…': 'Encendiendo Hermes (panel web, unos 6 s)…',
    'Ligando o Telegram do Hermes (uns 20 s)…': 'Encendiendo el Telegram de Hermes (unos 20 s)…',
    'Ligando o que estava desligado…': 'Encendiendo lo que estaba apagado…',
    'Ligando o painel de música…': 'Encendiendo el panel de música…',
    'Para ter o botão Desligar, feche e abra o estúdio de novo.':
      'Para tener el botón Apagar, cierra y abre el estudio otra vez.',
    'Não consegui guardar a preferência: ': 'No pude guardar la preferencia: ',
    'Esta versão do servidor do estúdio ainda não liga os serviços pelo Início. Feche o estúdio pelo atalho “Desligar Estúdio” (com nada gerando) e abra de novo para ativar os botões.':
      'Esta versión del servidor del estudio todavía no enciende los servicios desde Inicio. '
      + 'Cierra el estudio con el acceso directo “Desligar Estúdio” (sin nada '
      + 'generándose) y ábrelo otra vez para activar los botones.',
    'Mais rápida': 'La más rápida',

    // Os botõezinhos de ajuste. ⚠ A CHAVE É O TEXTO DEPOIS DO rot(): o preset guarda
    // "Rapido (8 passos)" sem acento, o rot() acentua, e só então o TX procura. Chave
    // sem acento aqui não acha nada - e não dá erro, só fica em português para sempre.
    'Livre': 'Libre', 'Traço artístico': 'Trazo artístico', 'Cartoon 2D': 'Cartoon 2D',
    'Ghibli aquarela': 'Ghibli acuarela',
    'Rápido': 'Rápido', 'Rápido (4 passos)': 'Rápido (4 pasos)',
    'Rápido (8 passos)': 'Rápido (8 pasos)',
    'Turbo (8 passos)': 'Turbo (8 pasos)', 'Turbo (12 passos)': 'Turbo (12 pasos)',
    'Normal': 'Normal', 'Normal (20 passos)': 'Normal (20 pasos)',
    'Caprichado': 'Cuidado', 'Caprichado (30 passos)': 'Cuidado (30 pasos)',
    'Máxima': 'Máxima', 'Máxima (48 passos)': 'Máxima (48 pasos)',
    '1:1 grande (2048)': '1:1 grande (2048)',
    'Só texto': 'Solo texto', 'Com imagem': 'Con imagen',
    'Personagem + movimento': 'Personaje + movimiento',
    'Começar de uma imagem': 'Empezar desde una imagen',
    'Primeiro/último quadro': 'Primer/último fotograma',
    'Com imagens de referência': 'Con imágenes de referencia',
    'Com imagem de referência': 'Con imagen de referencia',

    // mensagens do caminho de trabalho
    'Enviando e convertendo para 16 fps…': 'Subiendo y convirtiendo a 16 fps…',
    'Detectando a pose… (alguns segundos; se a GPU estiver gerando, espera a geração atual)':
      'Detectando la pose… (unos segundos; si la GPU está generando, espera al trabajo actual)',
    'Usa a imagem como está. Se o vídeo for de perto e a imagem de corpo inteiro, o personagem pode sair cortado.':
      'Usa la imagen tal cual. Si el vídeo es de cerca y la imagen de cuerpo entero, el '
      + 'personaje puede salir cortado.',
    'Envie a imagem e o vídeo: o personagem é recortado para ficar do mesmo tamanho e posição da pessoa do vídeo.':
      'Envía la imagen y el vídeo: el personaje se recorta para quedar del mismo tamaño y '
      + 'posición que la persona del vídeo.',
    'modelo já carregado (mais rápido)': 'modelo ya cargado (más rápido)',
    'baseada nas suas gerações': 'basada en tus propias generaciones',
    'estimativa inicial (melhora com o uso)': 'estimación inicial (mejora con el uso)',
    'Uma chave esta guardada e funcionando.': 'Hay una clave guardada y funcionando.',
    'uma chave ja esta guardada — cole outra para trocar':
      'ya hay una clave guardada — pega otra para cambiarla',
    'Conferindo a chave com o ElevenLabs…': 'Comprobando la clave con ElevenLabs…',
    'Nova (ainda não salva)': 'Nueva (todavía sin guardar)',
    'Voz padrão': 'Voz por defecto',
    'Voz nova enviada. Dê um nome e salve para reusar depois sem enviar de novo.':
      'Voz nueva subida. Ponle un nombre y guárdala para reutilizarla sin volver a subirla.',
    'Escreva um nome para a voz.': 'Escribe un nombre para la voz.',
    'rodou na placa de vídeo': 'funcionó en la tarjeta gráfica',
    'Texto escrito pela IA': 'Texto escrito por la IA',
    'Descrição da imagem': 'Descripción de la imagen',
    'A placa de vídeo estava ocupada: a IA rápida rodou no processador para não atrapalhar a geração.':
      'La tarjeta gráfica estaba ocupada: la IA rápida funcionó en el procesador para no '
      + 'estorbar a la generación.',
    'Rodou na placa de vídeo e foi descarregada dela logo depois (a placa já está livre de novo).':
      'Funcionó en la tarjeta gráfica y se descargó justo después (la tarjeta ya está libre).',
    'Escreva o TEMA na caixa (ex.: 3 dicas para dormir melhor) e clique de novo.':
      'Escribe el TEMA en la caja (ej.: 3 consejos para dormir mejor) y pulsa otra vez.',
    'Escreva o pedido primeiro (pode ser curto, em português).':
      'Escribe primero lo que quieres (puede ser corto).',
    'Começando…': 'Empezando…',
    'Não deu certo: ': 'No salió bien: ',
    'Vídeo do trabalho reusado': 'Vídeo del trabajo reutilizado',
    'Áudio do trabalho reusado': 'Audio del trabajo reutilizado',
    'Com erro ou cancelados': 'Con error o cancelados',
    'Carregar estas configurações no formulário': 'Cargar estos ajustes en el formulario',
    'Essa IA foi removida do estúdio: não dá para reusar':
      'Esa IA se quitó del estudio: no se puede reutilizar',
    'O arquivo já não está no HD: tira este trabalho da lista (e apaga o que sobrou dele)':
      'El archivo ya no está en el disco: quita este trabajo de la lista (y borra lo que quede '
      + 'de él)',
    'Cancelar esta geração?': '¿Cancelar esta generación?',
    'Cancelar geração': 'Cancelar la generación',
    'A ComfyUI não respondeu; o trabalho foi marcado como cancelado aqui.':
      'ComfyUI no respondió; el trabajo se marcó como cancelado aquí.',
    'Esta versão do servidor do estúdio manda só as 120 criações mais recentes desta aba; as mais antigas continuam no HD (pasta output da ComfyUI).':
      'Esta versión del servidor del estudio solo manda las 120 creaciones más recientes de '
      + 'esta pestaña; las más antiguas siguen en el disco (carpeta output de ComfyUI).'
  };

  var FRASES = { en: FRASES_EN, es: FRASES_ES };

  // Frases que terminam em ": " e ganham o recado do servidor colado no fim.
  var PREFIXOS = ['Não consegui apagar a voz: ', 'Não consegui cancelar: ',
    'Não consegui ligar a música: ', 'Não consegui ligar agora: ', 'Não consegui remover: ',
    'Não consegui guardar a preferência: ', 'Não deu certo: '];

  // pt-BR porque é o português que está escrito no HTML; os outros vão como estão.
  var ETIQUETA = { pt: 'pt-BR', en: 'en', es: 'es' };

  // ------------------------------------------------------------------ o estado
  function conhecido(v) {
    // O português é válido sem dicionário - ele é o HTML.
    return v === 'pt' || Object.prototype.hasOwnProperty.call(DICIONARIOS, v);
  }

  function guardado() {
    try {
      var v = localStorage.getItem(CHAVE);
      return conhecido(v) ? v : PADRAO;
    } catch (e) {
      return PADRAO;   // navegador com armazenamento bloqueado: segue em português
    }
  }

  var atual = guardado();

  function t(chave, sobra) {
    var d = DICIONARIOS[atual];
    if (d && d[chave]) return d[chave];
    return sobra === undefined ? chave : sobra;
  }

  // ------------------------------------------------------------------ traduzir PELO TEXTO
  // Para as frases que nascem espalhadas no app.js, inventar uma chave para cada uma sairia
  // caro e daria chave errada. Aqui a CHAVE É A PRÓPRIA FRASE EM PORTUGUÊS - que continua
  // escrita no código, onde quem programa a lê. Frase que não está no dicionário sai em
  // português, que é o certo.
  //
  // Serve para embrulhar a FUNÇÃO que mostra (aviso, título), não cada chamada: assim as 43
  // chamadas de aviso() continuam como estão e passam a falar três línguas de uma vez.
  function tx(portugues) {
    if (portugues == null) return portugues;
    var d = FRASES[atual];
    if (!d) return portugues;
    var s = String(portugues);
    if (d[s]) return d[s];
    // A frase pode vir com um pedaço colado no fim ("Não consegui ligar agora: 500").
    // Nesse caso traduz o começo conhecido e deixa o resto, que é recado do servidor.
    for (var i = 0; i < PREFIXOS.length; i += 1) {
      var p = PREFIXOS[i];
      if (s.indexOf(p) === 0) return d[p] + s.slice(p.length);
    }
    return s;
  }

  // ------------------------------------------------------------------ aplicar na tela
  function original(el, campo) {
    // Guarda o português do HTML na primeira vez, para a volta ser exata.
    var guarda = 'pt' + campo;
    if (el.dataset[guarda] === undefined) {
      el.dataset[guarda] = campo === 'Html' ? el.innerHTML : el.textContent;
    }
    return el.dataset[guarda];
  }

  function aplicar(raiz) {
    var onde = raiz || document;
    var d = DICIONARIOS[atual];

    onde.querySelectorAll('[data-i18n]').forEach(function (el) {
      var pt = original(el, 'Texto');
      var k = el.getAttribute('data-i18n');
      el.textContent = (d && d[k]) || pt;
    });

    onde.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      var pt = original(el, 'Html');
      var k = el.getAttribute('data-i18n-html');
      el.innerHTML = (d && d[k]) || pt;
    });

    // "placeholder:busca.dica" ou "title:botao.dica, aria-label:topo.marca"
    onde.querySelectorAll('[data-i18n-attr]').forEach(function (el) {
      el.getAttribute('data-i18n-attr').split(',').forEach(function (par) {
        var p = par.split(':');
        if (p.length !== 2) return;
        var attr = p[0].trim();
        var k = p[1].trim();
        var guarda = 'ptAttr' + attr.replace(/[^a-z]/gi, '');
        if (el.dataset[guarda] === undefined) el.dataset[guarda] = el.getAttribute(attr) || '';
        el.setAttribute(attr, (d && d[k]) || el.dataset[guarda]);
      });
    });

    document.documentElement.lang = ETIQUETA[atual] || 'pt-BR';
  }

  function trocar(novo) {
    if (!conhecido(novo)) return;
    atual = novo;
    try {
      localStorage.setItem(CHAVE, novo);
    } catch (e) { /* sem armazenamento: vale só para esta aba */ }
    // O seletor também é tela: se alguém trocar por fora (I18N.trocar), ele tem de
    // mostrar o idioma de verdade, e não o de antes.
    var sel = document.getElementById('idiomaSel');
    if (sel && sel.value !== novo) sel.value = novo;
    aplicar();
    // Quem desenha conteúdo por JavaScript escuta isto para redesenhar. Hoje ninguém
    // escuta ainda - fica pronto para quando as outras telas forem traduzidas.
    document.dispatchEvent(new CustomEvent('idioma-mudou', { detail: { idioma: novo } }));
  }

  // ------------------------------------------------------------------ o seletor
  function montarSeletor() {
    var canto = document.getElementById('idiomaCanto');
    if (!canto) return;
    canto.innerHTML =
      '<label class="sr-only" for="idiomaSel" data-i18n="idioma.rotulo">Idioma</label>'
      + '<select id="idiomaSel" class="idioma-sel" title="Idioma / Language">'
      + '<option value="pt">PT</option><option value="en">EN</option>'
      + '<option value="es">ES</option></select>';
    var sel = document.getElementById('idiomaSel');
    sel.value = atual;
    sel.addEventListener('change', function () { trocar(sel.value); });
  }

  function comecar() {
    montarSeletor();
    aplicar();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', comecar);
  } else {
    comecar();
  }

  window.I18N = {
    t: t,
    tx: tx,
    aplicar: aplicar,
    trocar: trocar,
    get idioma() { return atual; }
  };
})();
