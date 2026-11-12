# Estratégia de canais, canal dark e cortes

Este documento é uma leitura de mecânica de mercado, não um ranking ao vivo de canais.
Números de CPM/RPM variam por país, época, anunciante e formato. O que vale é o padrão:
quem ganha muito combina nicho de alto valor, retenção alta e uma esteira de publicação
constante.

## 1. De onde vem o dinheiro

Quatro motores, em ordem de previsibilidade:

1. **AdSense (RPM)**: paga por mil views. Finanças, negócios, tecnologia, saúde, seguros,
   imóveis e educação costumam ter RPM maior. Terror, true crime e histórias bizarras têm
   alcance e retenção, mas RPM menor e risco de desmonetização.
2. **Patrocínio direto**: o mais rentável por vídeo quando o canal tem audiência definida.
   Exige mídia kit, número de views por vídeo e público.
3. **Afiliado/produto próprio**: curso, mentoria, assinatura, comunidade, template, licença.
   É onde o canal deixa de depender do AdSense.
4. **Licenciamento e cortes**: vender ou distribuir recortes com permissão, ou usar cortes
   como funil para o vídeo longo. Sem permissão, vira risco de copyright e de conteúdo
   reutilizado.

## 2. O que "canal dark" pode significar

Há duas leituras que se misturam:

- **Estética dark**: mistério, terror, true crime, histórias estranhas, finanças sombrias,
  psicologia obscura, bastidores de poder. O motor é curiosidade + tensão + série.
- **Operação dark**: canal sem rosto, com voz sintética, produção em lote e várias marcas.
  O motor é volume + consistência + baixo custo por vídeo.

O canal que escala bem costuma juntar as duas: identidade visual forte, narração
reconhecível, episódios em série e uma operação que produz toda semana sem depender de
uma pessoa aparecendo.

### O que funciona nesse nicho

- **Série, não vídeo solto**: "caso 01", "arquivo 02", "parte 1 de 3". Isso aumenta retorno
  e sessão.
- **Gancho de 3 segundos**: uma pergunta, um número, uma contradição ou uma cena estranha.
- **Promessa clara**: "o que ninguém te contou sobre X", "o caso que mudou Y", "a conta que
  não fecha em Z".
- **Áudio e ritmo**: voz grave/baixa, pausas, som ambiente, cortes secos. Estética dark
  vive de som e ritmo tanto quanto de imagem.
- **Personagem recorrente**: narrador, investigador, "arquivo", "diário". Coadjuvantes
  ajudam a criar mundo.
- **Pacote**: título + miniatura + primeiro minuto. Sem isso, o melhor roteiro morre.

### O que quebra o canal dark

- Acusar pessoa real sem prova, inventar polêmica, distorcer fala ou editar para criar
  conflito. Isso é risco jurídico e de plataforma, não estratégia.
- Conteúdo sensacionalista com violência explícita, tragédia real e menores. Pode render
  view e custar o canal.
- Reaproveitar vídeo de terceiro sem transformação real. A política de conteúdo
  reutilizado/inautêntico derruba monetização.
- Música e imagens sem licença.
- Volume sem identidade: o algoritmo até distribui, mas o público não volta.

## 3. O que o Forja já tem

- Canais isolados com contexto, personagens, papéis, voz, estilo visual e formatos.
- Roteiro automático com duração mínima, cenas calculadas, séries em partes e coadjuvantes.
- Esteira de voz, imagens por proporção, legendas e montagem.
- Aprovação obrigatória, limpeza de brutos, agenda e publicação em várias redes.
- Análise automática de YouTube, TikTok, Instagram e Facebook.
- 27 estilos visuais, de papel a novelinha e drama adulto.
- Retratos de personagens e biblioteca de elenco.

O que falta para competir de igual com os canais que mais ganham:

- Leitura de retenção e CTR, não só views e receita.
- Custo por vídeo e lucro por canal.
- Motor de pautas e ângulos.
- Cortes de vídeos longos.
- Teste de título/miniatura.
- Camada de risco (copyright, política, fact-check).

## 4. Ideias de evolução

### Alto impacto, esforço médio

1. **Dashboard de ROI por canal**: receita, custo de GPU/tempo, custo por vídeo, lucro,
   receita por mil views, break-even. Sem isso você não sabe qual canal escala.
2. **Retenção e CTR**: YouTube Analytics entrega `averageViewDuration`,
   `averageViewPercentage`, `impressions`, `impressionClickThroughRate`. Trazer isso para
   a aba Análise e comparar por estilo, duração e gancho.
3. **Módulo de Cortes**: o item da seção 5.
4. **Teste de título e miniatura**: gerar 3 títulos e 3 miniaturas, publicar variações ou
   testar antes. Miniatura é o maior alavancador de CTR que existe.
5. **Playbook por nicho**: perfis prontos (dark, true crime, finanças, histórias, infantil,
   educativo) que ajustam tom, ritmo, duração, CTA, estilo visual e regras de compliance.

### Alto impacto, esforço alto

6. **Motor de pautas**: cruzar tendências públicas, perguntas do público, comentários e
   concorrência para sugerir pauta, ângulo, gancho e série.
7. **Camada de compliance**: checklist de copyright, política, menores, violência, saúde,
   finanças e fact-check antes da aprovação.
8. **Biblioteca de ativos**: reaproveitar personagens, cenários, músicas, vozes e cenas
   entre vídeos, com controle de licença.
9. **Multi-canal como portfólio**: orçamento, metas, calendário e equipe por canal.
10. **Cortes longos a partir de Shorts**: o inverso também funciona, juntar Shorts em um
    vídeo longo com novas pontes e contexto.

### Experimentos baratos

11. **Ganchos A/B**: gerar 5 primeiros segundos e escolher o melhor antes de produzir.
12. **Série com continuidade**: já implementado; medir retorno de parte 2 contra vídeo único.
13. **Posting cadence**: comparar 3x/semana contra 7x/semana por canal.
14. **Duração ideal**: 30 s, 60 s e 8 min no mesmo tema, medindo retenção e RPM.

## 5. Cortes: dá para fazer?

Sim, e o estúdio já tem quase todas as peças: ffmpeg, transcrição local, IA de texto,
legendas, montagem vertical, agenda e aprovação.

### Pipeline possível

1. **Entrada**: arquivo local ou URL de vídeo do próprio canal.
2. **Transcrição**: faster-whisper com timestamps por palavra.
3. **Segmentação**: detectar falas, pausas, risadas, perguntas, números, viradas e temas.
4. **Pontuação**: a IA local dá nota para gancho, emoção, autossuficiência, clareza e
   potencial de retenção. Também marca início e fim exatos.
5. **Corte**: ffmpeg corta o trecho, refaz o enquadramento para 9:16, adiciona legenda
   queimada, gancho no topo e barra de progresso.
6. **Pacote**: título, legenda, hashtags, miniatura e plataforma sugerida.
7. **Aprovação**: você assiste, aprova e agenda. A limpeza apaga os brutos.
8. **Publicação**: YouTube Shorts, TikTok, Instagram, Facebook.

### O que é fácil

- Cortar por timestamp e legendar.
- Reframing central ou com fundo desfocado.
- Gerar 3 a 10 cortes por vídeo longo.
- Sugerir títulos e hashtags.

### O que exige cuidado

- **Direitos**: só cortar vídeo próprio, licenciado ou com autorização. Conteúdo de
  terceiro sem transformação real é risco de copyright e de conteúdo reutilizado.
- **Polêmica fabricada**: não inventar fala, não tirar de contexto e não acusar pessoa
  real. O caminho seguro é "tensão real", "opinião forte", "pergunta polêmica" e
  "contradição documentada", sempre com o trecho original.
- **Enquadramento**: corte vertical automático pode cortar rosto ou informação. Uma
  detecção de rosto/objeto ajuda, mas o padrão precisa de revisão humana.
- **Contexto**: corte sem começo e fim claros vira ruído. A IA precisa pontuar
  autossuficiência, não só emoção.

### Escopo realista

- Fase 1: arquivo local, transcrição, 5 cortes por vídeo, legenda, 9:16, aprovação.
- Fase 2: URL do próprio canal, pontuação por retenção, títulos e miniaturas.
- Fase 3: detecção de rosto e reframing inteligente, testes A/B de gancho.

## 6. Playbook de canal dark

### Formatos

- **Arquivo/expediente**: caso real, documento, linha do tempo, conclusão.
- **Mistério em série**: episódio curto, gancho no fim, parte seguinte.
- **Conta que não fecha**: finanças, poder, bastidores, contradições.
- **Psicologia do cotidiano**: comportamento, manipulação, escolhas, sem diagnóstico.
- **História estranha**: objeto, lugar, pessoa, evento, com clima de documentário.

### Identidade

- Paleta escura com um acento (vermelho, âmbar ou verde ácido).
- Voz baixa, ritmo controlado, silêncio antes da revelação.
- Estilo visual: Noir, Terror, Vintage, Documentário, Grafite ou Cyberpunk.
- Personagem recorrente: narrador, investigador, "o arquivo", "o mensageiro".
- Coadjuvantes com papel claro: fonte, vítima, autoridade, testemunha.

### Ética e sustentabilidade

- Não transformar tragédia real em entretenimento vazio.
- Não afirmar crime sem sentença ou fonte.
- Não usar imagem de pessoa real em contexto falso.
- Sinalizar conteúdo sensível e idade quando necessário.
- Ter uma reserva: canal dark pode perder monetização de um vídeo e continuar de pé.

## 7. O que medir toda semana

- CTR da miniatura e do título.
- Retenção média e porcentagem assistida.
- Views por vídeo e por formato.
- Receita por mil views (RPM) e receita por vídeo.
- Custo de produção por vídeo (tempo de placa + tempo humano).
- Lucro por canal e por série.
- Inscritos por vídeo.
- Tempo até o primeiro corte/publicação.

## 8. Próximos passos sugeridos

1. Dashboard de ROI e retenção no canal.
2. Módulo de Cortes com aprovação.
3. Playbook dark com estilos, vozes e regras.
4. Motor de pautas e teste de título/miniatura.
5. Camada de compliance antes da publicação.
