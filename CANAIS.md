# Canais - vários canais, produção automática e publicação

Esta camada nasceu para não mexer na esteira antiga (`estudio/canal.py`). Ela fica ao lado:
cada canal tem o próprio contexto, personagens, voz, formatos, produções, agenda e números.
As produções vivem em `estudio/canais/<id>/` e os trabalhos de imagem que a esteira dispara
vão marcados como `oculto`, então não aparecem na Fila nem em Minhas criações.

## O que a tela faz

Rota nova: `#/canais` (menu **Canais**).

- **Visão geral**: produções, próxima publicação, views e receita do período.
- **Produzir**: um briefing em texto vira roteiro com cenas, falas, descrições visuais e
  personagens. O número de cenas não é fixo: sai da duração e do próprio roteiro.
  A duração escolhida é um piso: se a fala sair menor, a última cena segura até o mínimo.
  **Gerar vídeo completo** faz roteiro, voz, imagens e montagem em um clique. **Só o
  roteiro** para no plano para você revisar.
- **Personagens**: o canal pode reaproveitar personagens de vídeos anteriores. Na aba
  Produzir, marque os que quer manter; sem marcar, a IA escolhe e repete a aparência.
  Cada personagem tem papel: principal, coadjuvante ou figurante. **Gerar personagens
  com IA** cria novos a partir do que já existe, incluindo coadjuvantes para novelinha.
- **Estilo visual**: escolha por canal ou por vídeo entre Papel, Lápis, Pixel, Pincel,
  Palavra animada, 3D, E se..., Novelinha, Anime, Mangá, Aquarela, Grafite, Quadrinhos,
  Cyberpunk, Vintage, Noir, Stop motion, Neon, Origami, Colagem, Minimalista, Terror,
  Comédia, Épico, Documentário e Adulto (18+, drama sensual sem nudez explícita). O estilo
  entra nos prompts de imagem e no roteiro.
- **Retratos**: cada personagem pode ter uma foto de referência gerada pela IA. Se não
  houver, a tela mostra as iniciais como placeholder. O botão **Gerar retratos** cria as
  que faltam e usa o mesmo modelo de imagem do canal.
- **Série em partes**: marque "Parte 1 de uma série" no primeiro vídeo. Depois de
  aprovado, **Próxima parte** continua com o mesmo elenco, estilo e história, abrindo com
  recap e fechando com gancho.
- **Inspiração**: cole a URL de um vídeo do YouTube ou TikTok e clique em **Ler referência**.
  O roteiro usa título e autor como referência de ritmo e clima, sem baixar nem copiar o vídeo.
- **Análise**: o estúdio lê views, receita, seguidores e engajamento direto das contas
  conectadas, atualiza sozinho a cada 30 minutos e também pelo botão **Atualizar agora**.
  O CSV/JSON manual fica como reserva quando uma plataforma não liberar a permissão.
- **Aprovação**: o vídeo sempre para em **Aguardando aprovação**. Você assiste, confere
  legenda e imagens e então escolhe **Aprovar e limpar arquivos**, **Agendar** ou
  **Publicar agora**. Antes da aprovação, a agenda recusa o vídeo. A aprovação apaga
  imagens, vozes por cena e temporários; ficam só os vídeos finais, os personagens e os
  metadados.
- **Contexto com IA**: em Ajustes, **Gerar contexto com IA** preenche tema, público, tom,
  identidade visual, personagens, regras, referências, chamada e hashtags a partir do nome
  e da descrição. Cada campo tem **Melhorar** para reescrever só ele. No canal novo,
  **Sugerir descrição pelo nome** pede a descrição quando o nome é genérico.
- **Agenda**: escolha produção, formato, plataformas e data/hora. O servidor publica
  sozinho no horário, mesmo com a tela fechada (o estúdio precisa estar aberto). Pode
  publicar em YouTube, TikTok, Instagram e Facebook no mesmo agendamento.
- **Ajustes**: contexto do canal, personagens, voz, formatos com tamanho próprio,
  publicação automática, horários e contas das plataformas.

## Formatos

Cada formato tem nome, plataforma, largura, altura e legenda. O padrão vem com YouTube
horizontal (1920x1080), YouTube Shorts, Instagram Reels, Instagram Stories e TikTok
(1080x1920). Você pode mudar as medidas ou criar um formato novo em Ajustes.

Formatos com a mesma proporção e a mesma decisão de legenda reaproveitam o mesmo arquivo:
Reels, Stories e TikTok saem do mesmo 9:16. O padrão é **Automático**: uma imagem gerada
por proporção ativa. Assim o YouTube horizontal recebe imagens 16:9 de verdade, e o
vertical recebe 9:16, sem cortar o assunto. A opção **Uma só** reaproveita a mesma imagem
com fundo desfocado, gastando menos placa.

## Contexto isolado

O contexto do canal entra em todo pedido de roteiro:

- tema, público, tom, idioma;
- personagens com descrição e aparência visual;
- identidade visual (entra nos prompts de imagem);
- regras, o que não fazer, referências, chamada final e hashtags.

Trocar de canal troca o contexto inteiro. Nada de personagem ou tema de um canal vaza
para outro.

## Contas e publicação

As credenciais ficam em `estudio/canais/segredos.json` com permissão 600. A tela nunca
devolve o valor de um token; só diz se a conta está conectada.

### YouTube

Precisa de um app OAuth no Google Cloud com a YouTube Data API v3 habilitada:

1. Crie credenciais OAuth do tipo "App para computador".
2. Autorize a conta do canal com os escopos
   `https://www.googleapis.com/auth/youtube.upload`,
   `https://www.googleapis.com/auth/youtube.readonly` e
   `https://www.googleapis.com/auth/yt-analytics.readonly`.
3. Cole em Ajustes: `client_id`, `client_secret` e `refresh_token`.

O agendamento usa `publishAt` do YouTube: o vídeo sobe privado e o YouTube publica na hora
marcada. Depois de publicado, o link aparece na Agenda.

### TikTok

Precisa do TikTok Content Posting API com `video.upload` e `video.publish`:

1. Crie um app em developers.tiktok.com.
2. Autorize a conta com `video.upload`, `video.publish`, `user.info.basic` e `video.list`.
3. Cole em Ajustes o `access_token` e a privacidade (`PUBLIC_TO_EVERYONE` ou `SELF_ONLY`).

Enquanto o app não passa pela auditoria do TikTok, publique com `SELF_ONLY`. O TikTok não
tem agendamento nativo nesta API: o estúdio guarda a hora e envia no momento certo.

### Instagram

Precisa de uma conta profissional do Instagram ligada a uma Página do Facebook e do
Instagram Graph API:
1. Crie um app no Meta for Developers e pegue um token com `instagram_content_publish`
   e `instagram_manage_insights`.
2. Descubra o `ig_user_id` da conta.
3. O Graph API exige uma URL pública do vídeo. Configure `video_base_url` apontando para
   uma pasta servida por link público (túnel, CDN, servidor próprio). O arquivo final
   precisa estar acessível em `<video_base_url>/<nome-do-arquivo>`.
4. Cole `access_token`, `ig_user_id` e `video_base_url`.

Sem `video_base_url` a publicação no Instagram fica como pendente, com a explicação na
Agenda. O pacote manual (legenda + caminho do vídeo) é sempre gravado em
`publicacao/` dentro da produção.

### Facebook

Precisa de uma Página do Facebook e de um token de Página:

1. Crie um app no Meta for Developers com `pages_manage_posts` e
   `pages_read_engagement`.
2. Descubra o `page_id` da Página.
3. Cole `page_id` e `access_token` da Página em Ajustes.

O vídeo sobe direto pelo Graph API, sem URL pública. Publicação futura usa
`scheduled_publish_time` do Facebook. A análise lê seguidores e vídeos da Página; views por
vídeo dependem da permissão de insights.

## Isolamento do histórico

- Produções: `estudio/canais/<canal>/producoes/<data-hora>/`
- Roteiro: `roteiro.json`, `narracao.txt`, `cenas.txt`, `legendas.txt`, `personagens.json`
- Voz: `voz/voz_01.wav`, `voz.wav`, `duracoes.txt`
- Imagens: `cenas/cena_01.png`
- Vídeos: `saida/final-<formato>.mp4`
- Aprovados: `personagens.json`, `producao.json`, `saida/` e `publicacao/` ficam; imagens,
  vozes por cena e temporários são apagados na aprovação.
- Andamento: `producao.json` (etapas, progresso, log, erro)

Os trabalhos de imagem entram no histórico do estúdio com `oculto: true` e são filtrados
de `/api/trabalhos`, de Minhas criações e do histórico da Fila.

## API

Todas as rotas abaixo ficam em `/api/canais`.

| Método | Rota | Para quê |
|---|---|---|
| GET/POST | `/api/canais` | listar / criar |
| GET/POST/DELETE | `/api/canais/{id}` | detalhe / salvar config e contexto / arquivar |
| GET/POST | `/api/canais/{id}/contexto` | ler / gravar contexto |
| POST | `/api/canais/{id}/contexto/ia` | gerar contexto inteiro ou melhorar um campo |
| POST | `/api/canais/{id}/personagens/gerar` | criar personagens novos com IA |
| POST | `/api/canais/{id}/personagens/retrato` | gerar retrato de um personagem |
| GET | `/api/canais/{id}/personagens/retrato/{arquivo}` | servir o retrato |
| POST | `/api/canais/sugerir` | descrição a partir do nome do canal |
| POST | `/api/inspiracao` | título/autor de um vídeo de referência |
| POST | `/api/canais/{id}/plano` | briefing -> roteiro |
| POST | `/api/canais/{id}/produzir` | plano -> produção em segundo plano |
| GET | `/api/canais/{id}/producoes` | lista de produções |
| GET/POST | `/api/canais/{id}/producoes/{pid}` | andamento / cancelar |
| POST | `/api/canais/{id}/producoes/{pid}/aprovar` | aprovar (e limpar brutos) ou rejeitar |
| POST | `/api/canais/{id}/producoes/{pid}/proxima-parte` | gerar a continuação da série |
| GET | `/api/canais/{id}/producoes/{pid}/video/{formato}` | baixar o vídeo final |
| GET/POST | `/api/canais/{id}/agenda` | listar / agendar |
| POST/DELETE | `/api/canais/{id}/agenda/{aid}` | publicar agora / cancelar |
| GET/POST | `/api/canais/{id}/credenciais` | estado / gravar conta |
| GET/POST | `/api/canais/{id}/analytics` | dashboard / importar números |

## Limites conhecidos

- A publicação só roda enquanto o estúdio está aberto. Computador desligado não publica.
- A geração usa a mesma placa da ComfyUI e a mesma voz do VoiceStudio. Duas produções
  podem ficar na fila, mas a placa e a voz trabalham uma por vez.
- A análise automática depende da permissão de análise em cada app. Sem ela, a plataforma
  mostra o motivo na aba Análise e o CSV/JSON manual continua funcionando.
- TikTok não devolve receita orgânica e o Instagram também não: a receita aparece quando a
  plataforma entrega esse número (YouTube monetizado) ou quando você importa um CSV.
- Instagram exige URL pública do vídeo. Não existe publicação local sem isso.
