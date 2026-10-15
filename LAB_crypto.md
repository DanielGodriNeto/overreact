# Laboratório: atraso, precisão e ganho (início 2026-10-14)

Caderno de laboratório: plano, hipóteses, raciocínio e resultados de cada experimento, em ordem.
Complementa [PLAN_crypto.md](PLAN_crypto.md) (coleta) e [RESEARCH_crypto.md](RESEARCH_crypto.md) (pesquisa).
Nada aqui opera dinheiro; é tudo histórico, simulação ou paper.

## Objetivos

- **O1, atraso:** reduzir o tempo entre a publicação de um anúncio e o momento em que conseguimos agir. Só
  com mudanças gratuitas, e cada ganho medido.
- **O2, precisão e ganho:**
  - pegar os eventos certos (classificador);
  - escolher entradas e saídas que deem ganho líquido;
  - provar isso em histórico com simulação realista e em período fora da amostra.

## Regras do laboratório (valem para todo experimento)

1. **Antes de olhar o resultado** escrevo: hipótese, por quê, dados, métrica e critério de sucesso.
2. **Treino e teste separados no tempo:**
   - **TREINO**, 2024-01-01 a 2025-09-30: período ainda não analisado.
   - **TESTE**, 2025-10-01 até 2 dias atrás. Já foi visto de forma agregada no estudo P4b; ressalva
     registrada.
   - **Validação verdadeira:** os dados ao vivo coletados depois de 2026-10-15.
   - Parâmetros só se escolhem no TREINO.
3. **Execução pessimista:**
   - compra pela **máxima** do candle de 1 s em que a ordem chega, venda pela **mínima**;
   - taxa de 0,10% por lado (taker spot da Binance).
   - Também reporto a versão "no fechamento" para comparar.
4. **Toda variante testada entra na contagem de tentativas.** A significância é corrigida (Bonferroni pelo
   número de tentativas); com amostras pequenas isso é mais honesto que o Sharpe deflacionado.
5. **Só spot comprado:** a pesquisa mostrou que derivativos para brasileiro na Binance são provavelmente
   bloqueados. Estratégias que exigem short ficam registradas, mas não entram na conta de ganho.
6. **Um commit por experimento**, com o resultado aqui no caderno, mesmo quando der negativo.

## Plano

| # | Experimento | Hipótese | Critério de sucesso (fixado antes) |
|---|---|---|---|
| D1 | Consulta concorrente no ouvido | A fila sequencial atrasa a Upbit/OKX em segundos quando outra fonte demora | Atraso de agendamento p95 da Upbit < 0,3 s ao vivo; teste unitário prova que uma fonte lenta não bloqueia as outras |
| G0 | Simulador de execução (`sim.py`) | — (ferramenta) | Testes com caminhos sintéticos: sem look-ahead, preços pessimistas corretos |
| D2 | Intervalo de consulta da Upbit escolhido por simulação | Consultar mais rápido só vale se o ganho líquido simulado com o atraso real for positivo | Baixar de 10 s só se, no TREINO, a média líquida > 0 com limite inferior do IC > 0, e o sinal se mantiver no TESTE. Piso de 2 s, por educação com o servidor |
| G1 | Precisão do classificador | As regras de palavra-chave erram em títulos que nunca vi | Auditoria manual de uma amostra; precisão ≥ 95% em listagem/deslistagem das corretoras; corrigir e medir de novo numa amostra nova |
| G2 | Estender o histórico até 2024-01 | — (dados para o TREINO) | Eventos carregados, checksums ok |
| G3 | Listagem na Upbit, compra no spot da Binance, com regra de saída | Com atraso realista e preço pessimista ainda sobra ganho em algum horizonte | Saída escolhida no TREINO entre ≤ 8 variantes; TESTE com média líquida > 0 e IC inferior > 0 |
| G4 | Rebote após cascata de liquidação (compra spot) | Quedas forçadas por liquidação revertem parcialmente em minutos a horas | Mesmo protocolo; ≥ 30 eventos no TESTE |
| G5 | Funding muito negativo → compra spot | Excesso de vendidos precede alta (short squeeze) | Mesmo protocolo |
| G6 | Filtro de meta-labeling (regressão logística, validação purgada) | Um filtro simples aumenta o acerto sem matar o ganho total | Só onde houver ≥ 100 eventos; acerto +5 pp no TESTE sem reduzir o ganho total |
| D3 | WebSocket de anúncios da Binance | Só vale se anúncios da Binance moverem moedas já listadas no spot | Condicional: estudo histórico primeiro; precisa da sua chave só leitura |

Fora do escopo: short/perpétuos, dinheiro real, LLM no caminho rápido, aprendizado por reforço, modelos de
fundação.
Rollback: cada mudança é um commit; o ouvido volta com `git revert` e reiniciando a tarefa.

## Pré-registro rev 2 (depois da crítica independente, antes de qualquer resultado)

Uma crítica externa achou 7 problemas no plano acima. Eles mudam o desenho assim:

1. **Inversão dos períodos.**
   - O período 2025-10 → hoje já foi visto (estudo P4b). Ele vira **EXPLORAÇÃO**: as regras abaixo nasceram
     dele.
   - O período 2024-01 → 2025-09 nunca foi olhado. Ele vira **CONFIRMAÇÃO**: as regras são fixadas aqui,
     agora, e testadas lá uma única vez.
   - Os dados ao vivo depois de 2026-10-15 são a segunda confirmação.
2. **Amostra mínima.**
   - Confirmação exige n ≥ 30 eventos.
   - Com menos, o resultado é **"inconclusivo"**, nunca "sucesso".
   - Todas as listagens da Upbit entram juntas: mercados KRW, BTC e USDT.
   - O intervalo de confiança é bootstrap por notícia, e eventos da mesma moeda dentro de 1 h contam uma vez.
3. **Preenchimento da ordem.**
   - Um candle de 1 s não tem o livro de ofertas; num pico de +12% o preço real de compra é pior que a máxima.
   - Por isso cada resultado sai numa **tabela de latência** (entrar em 1, 2, 3, 5, 10, 15 s), mais um
     **custo extra de slippage**: 0,5% na entrada de eventos de listagem e 0,1% nos demais.
   - Reporto também a **latência de empate**.
   - Resultado histórico = **limite superior**, não promessa.
4. **Antes do D2, medir quando o preço começa a andar em relação ao carimbo da Upbit.**
   - Se o movimento começa antes do carimbo (vazamento) ou o carimbo vem atrasado, consultar mais rápido não
     adianta e o D2 morre.
5. **Significância.**
   - α = 0,05 por experimento, dividido pelo número de variantes declaradas aqui.
   - Bootstrap por notícia ou por dia.
6. **G1.**
   - Reportar precisão **e recall**, com intervalo de Wilson.
   - Amostra estratificada por fonte e idioma, incluindo coreano.
   - A auditoria é feita só no texto, sem ver o que o preço fez.
7. **G4, G5 e G6.**
   - Definições fixadas abaixo.
   - Funding entra com atraso de um intervalo (o valor só é conhecido depois de publicado).
   - G6 só roda com ≥ 300 eventos; senão é cancelado.

### Regras pré-registradas

- **G3, listagem Upbit (regra primária):**
  - compra spot na Binance no atraso L (tabela 1–15 s);
  - saída fixa em **+5 min**; preço pessimista + 0,5% de slippage + 0,2% de taxas.
  - Uma única variante secundária: saída em +60 min. k = 2, então α = 0,025.
- **G4, rebote após cascata:**
  - **Evento:** nos 10 pares do recorder mais os 20 maiores perps da Binance, uma queda de **≥ 4% em 15 min**
    no candle de 1 min, com **open interest caindo ≥ 3%** na mesma janela (métricas de 5 min da Binance).
  - Um evento por moeda a cada 6 h.
  - **Compra** no fechamento do minuto em que a condição fecha, mais 1 min de atraso.
  - **Saída** em +60 min. Secundária: +240 min. k = 2.
- **G5, funding negativo:**
  - **Evento:** funding publicado ≤ −0,05% num par com spot USDT.
  - **Compra** no spot no 1º minuto depois da publicação.
  - **Saída** em +24 h. Secundária: +72 h. k = 2.
- **Base de comparação de G4 e G5:** o mesmo horizonte em horários aleatórios da mesma moeda (placebo).
- **Taxas:** 0,10% por lado, mais o slippage acima.

---

## Resultados

### D1: consulta concorrente no ouvido (2026-10-14), SUCESSO

**Raciocínio:** o loop antigo chamava as 9 fontes uma depois da outra, e cada `fetch` bloqueava até 5 s
(timeout), além da sincronização do relógio (~1,4 s). A Upbit podia estar "vencida" e esperando atrás da Bybit.

**Medição do antes** (`scripts/bench_ear.py`, 3 rodadas reais):

| Fonte | Mediana | Máximo |
|---|---|---|
| bybit | 0,38 s | 0,42 s |
| okx | 0,35 s | 0,99 s |
| upbit | 0,34 s | 0,38 s |
| binance_symbols | 0,41 s | 0,88 s |
| relógio (rajada de 5) | 1,41 s | 1,47 s |
| RSS e Coinbase | ≤ 0,12 s | |

O log mostra 2 timeouts de 5 s da Bybit em 3 h.

**Replay do agendamento por 1 h** com as piores durações, atraso p95 entre "devia começar" e "começou":

| Fonte | Sequencial (antigo) | Concorrente (novo) |
|---|---|---|
| upbit | 1,43 s | 0,02 s |
| okx | 1,00 s | 0,01 s |
| bybit | 0,98 s | 0,18 s |

Com um timeout da Bybit no meio, o loop antigo atrasa todo mundo em +5 s.

**Mudança:**
- uma thread por fonte, mais a sincronização do relógio também numa thread;
- SQLite e o estado continuam só na thread principal;
- o tick do loop caiu de 0,2 s para 0,05 s;
- o heartbeat agora grava `late_p95_s` por fonte.

**Teste:** `test_slow_source_does_not_delay_the_others`. Uma fonte travada por 1 s; todas as outras são
consultadas em < 0,3 s.

**Ao vivo, logo após o deploy:** atraso p95 = upbit 0,050 s, okx 0,047 s, bybit 0,048 s. Meta < 0,3 s
batida.

**Rechecagem ao vivo (2026-10-15 00:13, ~8 h depois):**
- p95 entre 0,043 e 0,058 s em todas as 9 fontes (upbit 0,047; okx 0,046; bybit 0,045);
- zero falhas;
- os 2 únicos 429 da Upbit no log caíram durante a minha paginação histórica (mesmo IP), não na operação normal.

O ganho se mantém.

**Ganho:** até ~1,4 s a menos (p95) em condições normais e até ~5 s quando outra fonte trava. Não é o bastante
para a janela de 1–3 s da Upbit, mas é atraso de graça que saiu do caminho.

### G0: simulador de execução (2026-10-14), PRONTO

`overreact/crypto/sim.py`:
- `worst_fill`: o pior preço do segundo em que a ordem chega e do seguinte;
- `trade`: retorno líquido com slippage e taxas;
- `onset`: o primeiro segundo em que o preço anda ≥ X% em relação a antes do anúncio.

Testes em `tests/test_crypto_sim.py`: preço pessimista, sem look-ahead, vazamento antes do carimbo.
45 testes passando.

### Calibração antes do D2: quando o preço anda em relação ao carimbo da Upbit (2026-10-15)

**Raciocínio:** se o preço começasse a subir antes do carimbo (vazamento) ou se o carimbo viesse atrasado,
consultar mais rápido não ajudaria.

**Medição** (`sim.onset`), nas 15 listagens do período de exploração: o primeiro segundo com o preço ≥ 2%
acima do preço de 2 min antes cai **em 0 s (10 casos) ou +1 s (5 casos)**. Nenhuma alta antes do carimbo.
(Os -67/-46 s que aparecem com o limiar de 1% são ruído.)

**Conclusão:** o carimbo da Upbit é preciso e o mercado reage **dentro do próprio segundo da publicação**.
Quem ganha isso tem o anúncio em < 1 s.

**Evidência extra (2026-10-15):** paginar o histórico a 1 página/s, e depois a 3 s/página, levou **HTTP 429**
da Upbit, e o ouvido ao vivo (mesmo IP) levou um 429 junto. Com 10 s/página, o bloqueio vem depois de ~10
páginas. Ou seja: o limite da API é baixo e compartilhado por IP. Consultar a cada 1–2 s seria bloqueado.

### G1: precisão do classificador (2026-10-15), CORRIGIDO

**Método:**
- Amostra estratificada de 120 títulos (40 por fonte; 14 listagem, 14 deslistagem e 12 "nenhum" previstos).
- Julgados por mim só pelo texto, sem olhar o preço.
- Depois da correção, **amostra nova** de 90 títulos (sem repetir), com as regras novas.

| | Antes (n=120) | Depois (amostra nova, n=90) |
|---|---|---|
| Precisão "listagem" | 40/42 = 95% | 30/30 |
| Precisão "deslistagem" | 40/42 = 95% | 30/30 |
| Listagens perdidas entre os "nenhum" | **10 de 36** (7 Upbit, 3 OKX) | 0 de 30 (Wilson 95%: ≤ 11%) |
| Moeda certa extraída (OKX) | 4 de 12 listagens; 0 de 9 deslistagens com nome | corrigido (ver testes) |

**Erros achados e corrigidos:**
1. Upbit "신규 거래지원 안내" ("novo suporte de negociação") **é listagem**, e o formato novo da Upbit não era
   reconhecido. Isso também quer dizer que **o estudo P4b contou listagens da Upbit a menos**.
2. OKX "will launch X/USDT for spot trading" é listagem.
3. Falsos positivos: "delay of ... listing", "postpone delisting", "Listing of X on Convert" e "예정일 변경"
   (mudança de data) agora dão "nenhum".
4. Moedas perdidas:
   - "MEGA (MegaETH)" (formato da OKX);
   - listas "delist A, B and C" (agora aceito ticker sem marcação em título de corretora);
   - "TRUMP/USDT" (TRUMP estava na lista de palavras ignoradas por causa do presidente; um par explícito agora
     vence).
5. **Regressão pega na segunda amostra:** "(KRW, BTC, USDT 마켓)" fazia BTC virar moeda do evento em 5 de 10
   listagens da Upbit. A lista de mercados agora é removida antes de extrair.

**Ainda não coberto** (raro, registrado):
- tickers de 1 letra (J, W, K);
- prefixos "1000000X" da Bybit;
- a categoria "유의 종목 지정" (aviso de risco da Upbit, possível evento negativo; precisaria de short).

Testes: `test_news_type_g1_audit_cases`, `test_extract_g1_audit_cases`, `test_upbit_market_list_is_not_a_coin`.

### G3 + D2: listagem na Upbit → compra spot na Binance (2026-10-15), REPROVADO / D2 MORTO

**Dados:**
- histórico completo da Upbit (380 avisos desde 2023-09; a paginação esperou 300 s a cada 429);
- regras corrigidas do G1; eventos com par USDT ativo na Binance no momento;
- mesma moeda dentro de 1 h conta uma vez.

**Regra pré-registrada:**
- compra no atraso L com o pior preço dos 2 candles de 1 s + 0,5% de slippage + 0,2% de taxas;
- saída em +5 min (primária) ou +60 min (secundária);
- teste: limite inferior do IC 95% bicaudal > 0 (equivale a unilateral com α = 0,025 = 0,05/k, k = 2).

| CONFIRMAÇÃO 2024-01..2025-09 (n=82, 64 avisos) | líquido médio | IC 95% | acerto |
|---|---|---|---|
| L=1 s → +5 min | −322 bps | [−649, +41] | 24% |
| L=3 s → +5 min | −341 bps | [−639, +28] | 22% |
| L=5 s → +5 min | −349 bps | [−613, −8] | 23% |
| L=1 s → +60 min (secundária) | −361 bps | [−801, +84] | 27% |
| L=15 s → +5 min | −116 bps | [−392, +231] | 28% |
| Consulta a cada 1 s (atraso simulado real) → +5 min | −299 bps | [−621, +68] | 23% |
| Consulta a cada 10 s → +5 min | −292 bps | [−551, +46] | 21% |

Na EXPLORAÇÃO (n = 49), tudo foi negativo e significativo: −580 bps em L = 1 s e −503 bps consultando a cada 10 s.
**Veredito pré-registrado: REPROVADO**, sem nenhuma variante com limite inferior > 0.

**Por que, de forma diagnóstica (exploração, não muda o veredito):**
- Mediana do preço na Binance em relação ao segundo antes do carimbo:
  - +0–2% em +1 s;
  - **+13–16% em +5 s**;
  - pico de ~+23% dentro de 5 min;
  - ainda +11% em +5 min.
- O dinheiro existe, mas está **todo no primeiro segundo**. Quem compra depois paga o pico, e o preço devolve
  parte nos minutos seguintes (sobrerreação clássica).
- Para checar se o prejuízo vinha só do modelo pessimista, calculei o **teto otimista**: compra no fechamento
  do candle, zero slippage, só as taxas.

| Teto otimista (+5 min) | CONFIRMAÇÃO | EXPLORAÇÃO |
|---|---|---|
| L=1 s | +648 bps [+233, +1229], **mediana +4** | −57 [−242, +134] |
| L=2 s | +242 [−71, +651], mediana −15 | −166 [−379, +32] |
| L=3 s | +121 [−174, +510], mediana −86 | −229 [−432, −33] |
| L=5 s | +112 [−158, +491], mediana −153 | −192 [−399, +16] |

- O verdadeiro fica entre o piso pessimista e o teto otimista.
- O único teto positivo (L = 1 s, confirmação) vem de poucos casos gigantes; a mediana é ~0.
- **Exige estar dentro de 1 s da publicação.** Nosso mínimo realista é ~1,5–3 s: cache de 0–1 s da Cloudflare
  + 0,35 s de fetch + 0,27 s até a corretora, mais a espera até a próxima consulta.

**Conclusões:**
1. **G3 reprovado.** Comprar spot na Binance depois da listagem na Upbit não dá lucro com latência de
   segundos. Nem no cenário otimista.
2. **D2 morto.** Consultar mais rápido não ajuda:
   - a curva do teto cai de L = 1 para L = 2 s;
   - a Upbit dá 429 perto de 1 req/s;
   - o movimento começa no próprio segundo do carimbo (calibração acima).
   Ganhar aqui exigiria um feed sub-segundo (WebSocket/colocalização), que a Upbit não oferece de graça.
3. **Refinamento com aggTrades (livro tick a tick) descartado.** Ele só estreitaria o intervalo entre piso e
   teto, e o teto já não passa nas latências que conseguimos.
4. **Hipótese nova, só exploração e NÃO testável no nosso cenário:** a reversão de +5 s para +5 min (cerca de
   −3 a −5%) seria um short, e short/derivativos estão provavelmente vetados para o usuário no Brasil. Fica
   registrada e não é perseguida.

### G4: rebote depois de cascata de liquidação (2026-10-15), APROVADO NA SECUNDÁRIA (com ressalvas)

**Hipótese:**
- uma queda forte com o open interest caindo ao mesmo tempo = liquidações forçadas, não informação nova;
- vendedor forçado vende abaixo do valor justo e o preço tende a voltar (sobrerreação);
- não depende de velocidade de notícia: a entrada é 1 min depois, então o atraso de segundos não importa.

**Dados:**
- 30 moedas: 10 do recorder + 20 maiores perps de hoje com spot USDT e listadas antes de 2024;
- candles de 1 min do spot; OI de 5 min das métricas diárias, só snapshots com carimbo ≤ t;
- custos de 0,1% de taxa + 0,1% de slippage por lado;
- IC bootstrap por **dia**, porque cascatas atingem várias moedas juntas.

| CONFIRMAÇÃO 2024-01..2025-09 (n=293, 91 dias) | líquido médio | IC 95% | mediana | acerto | placebo |
|---|---|---|---|---|---|
| **Primária:** entra +1 min, sai +60 min | +16 bps | [−82, +113] | +37 | 55% | −40 |
| **Secundária:** entra +1 min, sai +240 min | **+136 bps** | **[+28, +229]** | +99 | 63% | −41 |
| Sensibilidade: entra +5 min, sai +240 min | +154 | [+36, +255] | | 63% | |
| Sensibilidade: entra +15 min, sai +240 min | +106 | [−28, +239] | | 58% | |

- O placebo (mesma moeda, mesmo horizonte, horário aleatório) dá −40 bps, que é exatamente o custo. Ou seja,
  bruto ≈ 0 fora das cascatas.
- Na EXPLORAÇÃO (2025-10.., n = 169): +60 min = +307 bps [+85, +557]; +240 min = +355 [+51, +726].

**Veredito pré-registrado:**
- primária **REPROVADA**;
- secundária **APROVADA** (limite inferior > 0 com α = 0,025).

**Robustez da secundária (+240 min), checada depois e declarada como tal:**

| Recorte | n | líquido | IC 95% |
|---|---|---|---|
| Só as 10 moedas do recorder (lista fixada antes, sem viés de sobrevivência) | 94 | +173 | [+50, +299] |
| Só as 20 extras (escolhidas pelo volume de hoje) | 199 | +118 | [+13, +213] |
| 2024 | 232 | +125 | [−4, +229] |
| 2025-01..09 | 61 | +177 | [+37, +358] |
| Sem o melhor dia | 271 | +111 | [+10, +198] |
| Sem os 3 melhores dias | 225 | +82 | [−19, +187] |
| Sem os 5 melhores dias | 200 | +49 | [−49, +159] |

**Carteira** (capital dividido igualmente entre as moedas que disparam no dia; limite superior, porque supõe
100% do capital alocado):

| | Dias com trade | média/dia | dias positivos | total | pior queda (maxDD) | pior dia |
|---|---|---|---|---|---|---|
| CONF +240 min | 91 em 21 meses | +108 bps | 64% | +166% | −15,8% | −8,3% |
| EXPL +240 min | 76 em 12 meses | +81 bps | 61% | +86% | −23,8% | −12,4% |

**Leitura honesta:**
1. É o **primeiro sinal que passa num teste pré-registrado em dados nunca vistos**. Também se mantém na lista
   fixa de moedas (o que descarta viés de sobrevivência) e nos dois anos.
2. **É concentrado.** Tirando os 3 melhores dias, o IC passa a cruzar zero. O ganho vem das grandes
   capitulações do mercado (ex.: 2024-01-03, 2024-03-05). Na prática é "comprar o pânico".
3. **Margem para custo:** o médio aguenta ~0,7% a mais de slippage por lado; o limite inferior do IC só aguenta
   ~0,14%. Numa cascata o spread abre, e esse é o risco real de execução. Um backtest com 1 min não vê isso.
4. A janela de +60 min não funciona: o rebote precisa de horas.
5. Diferente do G3: **não depende de latência**. Segundos de atraso não mudam nada (entrar em +5 min foi até
   melhor).

**Próximo passo:** confirmação ao vivo. Rodar um detector em **paper** (preço spot e OI públicos da Binance a
cada minuto) que registra cada sinal e o resultado em +240 min. Pelo pré-registro, os dados depois de
2026-10-15 são a segunda confirmação. Com ~4 dias de sinal por mês, ter n ≥ 30 dias leva ~6–8 meses.
Nada de dinheiro real antes disso.

**Confirmação ao vivo, como rodar** (regras e universo congelados em 2026-10-15,
`overreact/crypto/lab_universe.txt`):
```
python -m overreact.crypto.lab cascade --since 2026-10-15
```
- Rodar todo começo de mês, depois que o data.binance.vision publica o arquivo mensal de 1 min.
- É **o mesmo código do backtest** aplicado só aos dias novos, então não existe um detector "ao vivo"
  diferente do que foi testado.
- Sai em `data/lab_cascade_live.csv` com o rótulo `LIVE`.
- Critério: o mesmo da secundária (+240 min, limite inferior do IC > 0), avaliado só quando houver ≥ 30 dias
  com sinal.

**Revisão independente do código do lab (2026-10-15):**

Sem viés de antecipação. A revisão conferiu:
- a janela de 15 min, só com candles fechados;
- o OI, só com snapshot ≤ t;
- a entrada no fechamento do candle de t+60;
- os preenchimentos do `sim`;
- as threads do ouvido;
- a verificação dos downloads.

Achado médio, **corrigido**: o `--since` dependia do arquivo mensal, que só sai quando o mês fecha. Sem o fallback,
o mês corrente sumia em silêncio. Agora ele usa os arquivos diários de 1 min e avisa no log.

Ressalvas baixas, registradas e não corrigidas:
- depois de um buraco nos dados, "15 min antes" pode ser um candle mais antigo (as 30 moedas são líquidas, então
  é raro);
- o placebo não exclui janelas de evento (contaminação leve, que puxa o placebo *a favor* do evento; ou seja,
  conservador);
- no G3, a saída é medida a partir de t0 e não de t0+L (diferença ≤ 15 s em 5 min, sem efeito no veredito).

### G5: funding muito negativo → compra spot (2026-10-15), REPROVADO

**Hipótese:** funding ≤ −0,05% = excesso de vendidos, e daí viria um short squeeze.

**Regra pré-registrada:**
- compra spot no 1º minuto depois da publicação do funding;
- saída em +24 h (primária) ou +72 h (secundária);
- sem trades sobrepostos (72 h de intervalo);
- mesmas 30 moedas e mesmos custos do G4.

| CONFIRMAÇÃO (n=152, 129 dias) | líquido | IC 95% | acerto | placebo |
|---|---|---|---|---|
| +1 min → +24 h | −31 bps | [−141, +78] | 44% | −61 |
| +1 min → +72 h | −77 bps | [−200, +46] | 49% | −39 |

Na EXPLORAÇÃO (n = 179): −70 bps em +24 h e +56 bps em +72 h, ambos com IC cruzando zero e indistinguíveis do placebo.
**Sem efeito.** O funding negativo extremo não prevê alta no spot nessas moedas: o "squeeze" não aparece na média.

### G6: filtro de meta-labeling, CANCELADO pela regra

- O pré-registro exige ≥ 300 eventos.
- O único sinal aprovado (G4) tem 293 eventos (91 dias independentes) na confirmação.
- Um filtro treinado nisso teria ~90 observações efetivas, o que é sobreajuste garantido.
- Volta a ser considerado quando a confirmação ao vivo do G4 somar os dados novos.

### D3: WebSocket de anúncios da Binance, ADIADO (não vale pedir a chave agora)

- O G3 mostrou que, num anúncio de listagem, **o preço anda no mesmo segundo e quem chega em ≥ 2 s paga o
  pico**.
- Um WebSocket da Binance entrega o anúncio sub-segundo, mas **para todo mundo ao mesmo tempo**, inclusive
  para bots colocalizados em Tóquio.
- Daqui o RTT até a Binance é ~0,27 s, então chegaríamos depois deles.
- O prior mais forte do laboratório diz que não sobra nada.
- Fica adiado até aparecer evidência de um tipo de anúncio da Binance com reação **lenta** (minutos).
  Nesse caso a latência não importaria e a chave nem seria necessária.

---

## Resumo do laboratório (2026-10-15)

| # | Resultado | O que significa |
|---|---|---|
| D1 | **SUCESSO** | Atraso de agendamento p95: 1,43 s (até 5 s) → **0,05 s**, de graça, confirmado ao vivo por horas |
| G0 | PRONTO | Simulador pessimista testado |
| G1 | **CORRIGIDO** | O classificador perdia ~28% das listagens; agora 60/60 e 30/30 numa amostra nova |
| G2 | PRONTO | Histórico da Upbit desde 2023-09 (380 avisos) |
| D2 | **MORTO** | O movimento acontece no 1º segundo; consultar mais rápido não paga, e a Upbit dá 429 perto de 1 req/s |
| G3 | **REPROVADO** | Comprar na Binance depois da listagem na Upbit perde ~3% (n = 82); nem o teto otimista passa com ≥ 2 s |
| G4 | **APROVADO (secundária)** | Comprar 1 min depois de uma cascata de liquidação e vender em +4 h: **+1,36%/trade**, IC [+0,28, +2,29], n = 293. Concentrado em grandes capitulações |
| G5 | REPROVADO | Funding negativo não prevê alta |
| G6 | CANCELADO | Eventos insuficientes |
| D3 | ADIADO | O prior do G3 diz que velocidade de notícia não é o nosso jogo |

**A conclusão principal:**
- **O caminho de "chegar primeiro na notícia" está fechado para nós.** Quem ganha está a < 1 s.
- **O único ganho testado vem de "comprar o pânico forçado" (G4).** Ele não depende de latência e funciona com
  candles de 1 min e dados públicos gratuitos.
- O próximo passo é a **confirmação ao vivo do G4** (mensal, com `--since 2026-10-15`), até somar ≥ 30 dias com
  sinal. Só depois disso faz sentido pensar em paper trading com ordens reais na testnet.
