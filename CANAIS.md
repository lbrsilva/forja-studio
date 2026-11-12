# Canais - vários canais, produção automática e publicação

Esta camada nasceu para não mexer na esteira antiga (`estudio/canal.py`). Ela fica ao lado:
cada canal tem o próprio contexto, personagens, voz, formatos, produções, agenda e números.
As produções vivem em `estudio/canais/<id>/` e os trabalhos de imagem que a esteira dispara
vão marcados como `oculto`, então não aparecem na Fila nem em Minhas criações.

## O que a tela faz

Rota nova: `#/canais` (menu **Canais**).

- **Visão geral**: produções, próxima publicação, views e receita do período.
- **Produzir**: um briefing em texto vira roteiro com cenas, falas, descrições visuais e
  personagens. Tudo é editável antes de mandar produzir. A esteira gera voz por cena,
  uma imagem por cena e monta o vídeo em todos os formatos ativos do canal.
- **Agenda**: escolha produção, formato, plataformas e data/hora. O servidor publica
  sozinho no horário, mesmo com a tela fechada (o estúdio precisa estar aberto).
- **Análise**: importe CSV/JSON das plataformas e veja views, receita, seguidores,
  engajamento, série diária, melhores horários, plataformas e vídeos que puxaram o canal.
- **Ajustes**: contexto do canal, personagens, voz, formatos com tamanho próprio,
  publicação automática, horários e contas das plataformas.

## Formatos

Cada formato tem nome, plataforma, largura, altura e legenda. O padrão vem com YouTube
horizontal (1920x1080), YouTube Shorts, Instagram Reels, Instagram Stories e TikTok
(1080x1920). Você pode mudar as medidas ou criar um formato novo em Ajustes.

Formatos com o mesmo tamanho e a mesma decisão de legenda reaproveitam o mesmo arquivo:
Reels, Stories e TikTok saem do mesmo 9:16. O horizontal usa fundo desfocado atrás da
imagem para não cortar o assunto.

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
   `https://www.googleapis.com/auth/youtube.upload` e
   `https://www.googleapis.com/auth/youtube.readonly`.
3. Cole em Ajustes: `client_id`, `client_secret` e `refresh_token`.

O agendamento usa `publishAt` do YouTube: o vídeo sobe privado e o YouTube publica na hora
marcada. Depois de publicado, o link aparece na Agenda.

### TikTok

Precisa do TikTok Content Posting API com `video.upload` e `video.publish`:

1. Crie um app em developers.tiktok.com.
2. Autorize a conta e guarde o `access_token`.
3. Cole em Ajustes o `access_token` e a privacidade (`PUBLIC_TO_EVERYONE` ou `SELF_ONLY`).

Enquanto o app não passa pela auditoria do TikTok, publique com `SELF_ONLY`. O TikTok não
tem agendamento nativo nesta API: o estúdio guarda a hora e envia no momento certo.

### Instagram

Precisa de uma conta profissional do Instagram ligada a uma Página do Facebook e do
Instagram Graph API:

1. Crie um app no Meta for Developers e pegue um token com `instagram_content_publish`.
2. Descubra o `ig_user_id` da conta.
3. O Graph API exige uma URL pública do vídeo. Configure `video_base_url` apontando para
   uma pasta servida por link público (túnel, CDN, servidor próprio). O arquivo final
   precisa estar acessível em `<video_base_url>/<nome-do-arquivo>`.
4. Cole `access_token`, `ig_user_id` e `video_base_url`.

Sem `video_base_url` a publicação no Instagram fica como pendente, com a explicação na
Agenda. O pacote manual (legenda + caminho do vídeo) é sempre gravado em
`publicacao/` dentro da produção.

## Isolamento do histórico

- Produções: `estudio/canais/<canal>/producoes/<data-hora>/`
- Roteiro: `roteiro.json`, `narracao.txt`, `cenas.txt`, `legendas.txt`, `personagens.json`
- Voz: `voz/voz_01.wav`, `voz.wav`, `duracoes.txt`
- Imagens: `cenas/cena_01.png`
- Vídeos: `saida/final-<formato>.mp4`
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
| POST | `/api/canais/{id}/plano` | briefing -> roteiro |
| POST | `/api/canais/{id}/produzir` | plano -> produção em segundo plano |
| GET | `/api/canais/{id}/producoes` | lista de produções |
| GET/POST | `/api/canais/{id}/producoes/{pid}` | andamento / cancelar |
| GET | `/api/canais/{id}/producoes/{pid}/video/{formato}` | baixar o vídeo final |
| GET/POST | `/api/canais/{id}/agenda` | listar / agendar |
| POST/DELETE | `/api/canais/{id}/agenda/{aid}` | publicar agora / cancelar |
| GET/POST | `/api/canais/{id}/credenciais` | estado / gravar conta |
| GET/POST | `/api/canais/{id}/analytics` | dashboard / importar números |

## Limites conhecidos

- A publicação só roda enquanto o estúdio está aberto. Computador desligado não publica.
- A geração usa a mesma placa da ComfyUI e a mesma voz do VoiceStudio. Duas produções
  podem ficar na fila, mas a placa e a voz trabalham uma por vez.
- A análise não puxa números sozinha: ela lê o CSV/JSON exportado por cada plataforma
  e registra o que foi publicado pelo próprio estúdio. Coleta automática exigiria
  permissões de analytics em cada app, que são separadas das permissões de publicação.
- Instagram exige URL pública do vídeo. Não existe publicação local sem isso.
