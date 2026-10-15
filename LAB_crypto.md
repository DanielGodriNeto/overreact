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
batida. Reconfiro com mais horas de dados no fim do laboratório.

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
