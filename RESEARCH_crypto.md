# Pesquisa: como melhorar o overreact (2026-10-14)

Quatro frentes pesquisadas em paralelo: brechas de mercado e fontes de dados, machine learning e decisão,
IA/LLMs, infraestrutura e lei/imposto no Brasil. As notas de viabilidade e risco são estimativas de julgamento,
não medidas. Itens marcados **(não verificado)** vieram de uma fonte secundária só ou de nenhuma.
Isto é pesquisa de tecnologia, não recomendação de investimento.

## Resumo em 6 linhas

1. **A maior descoberta:** a Binance tem um canal oficial que *empurra* anúncios na hora (WebSocket
   `com_announcement_en`, data em ms). Grátis, mas exige uma chave de API. Troca 5-10 s de polling por ~0,3 s.
2. **A Upbit continua inalcançável:** não existe canal push oficial; o efeito de listagem da Upbit está
   enfraquecendo em 2026 (4pillars), e fontes pagas de terceiros só fazem scraping.
3. **As brechas boas que sobram são lentas** (minutos a dias): rebote após cascata de liquidação, queda depois
   da euforia de listagem (1-14 dias), deslistagem, grandes desbloqueios de token, funding extremo. Latência
   deixa de importar.
4. **Quase todas essas brechas pedem posição vendida (short) em perpétuos.** Brasileiro na Binance Futures é
   provavelmente bloqueado **(não verificado)**. Esse é o gargalo real, não a tecnologia.
5. **IA: nada de LLM tomando decisão.** Nenhum agente de trading com IA mostrou lucro fora da amostra depois de
   custos. LLM serve offline, para rotular notícias e treinar um classificador minúsculo.
6. **ML: o que importa é metodologia, não modelo grande.** Rótulo triple-barrier, regressão logística e
   LightGBM regularizado, validação purgada, Sharpe deflacionado. Modelos de fundação para séries temporais e
   aprendizado por reforço não mostram vantagem em retornos.

## 1. Brechas de mercado e fontes de dados

| Item | Por que vale | Por que não | Viab. | Risco | Veredito |
|---|---|---|---|---|---|
| **WebSocket de anúncios da Binance** | Oficial, grátis, push ~0,3 s; cobre listagem, deslistagem, futuros, Alpha, tag de monitoramento | Precisa de chave de API (só leitura deve bastar, **não verificado**); só cobre a Binance; o pico de listagem pode acabar em <1 s | 80% | 3% | **ADOTAR** |
| Rebote após cascata de liquidação | Já gravamos as liquidações; horizonte de minutos a horas | Nenhum estudo testa o rebote diretamente; "pegar faca caindo" | 65% | 30% | **TESTAR** (o mais barato) |
| Queda pós-listagem (1-14 dias) | The Tie, 1.844 listagens 2023-26: a alta pós-listagem reverte em ~2 semanas | Fonte de fornecedor; precisa de short; risco de squeeze | 60% | 25% | **TESTAR** (dá para fazer com o histórico que já baixamos) |
| Deslistagem (Upbit e Binance) | Nosso dado: Upbit -6% em 5 min, capturável até 10 s | Precisa de short | 65% | 25% | **TESTAR** |
| Desbloqueio grande de tokens | Keyrock, ~16 mil eventos: ~90% com pressão de baixa, começa ~30 dias antes | Calendários bons são pagos (Tokenomist); precisa de short | 55% | 25% | **TESTAR** |
| Funding extremo como sinal | Os extremos ainda carregam informação | Carry puro morreu: Sharpe negativo em 2025 (arXiv 2510.14435) | 60% | 20% | **TESTAR** só o sinal; carry: descartar |
| Hyperliquid | Dados grátis sem chave (livro, liquidações, novas listagens HIP-3) | Mercados novos e rasos; operar exige depósito real | 70% | 20% | **ADOTAR como fonte de dados** |
| Fluxo on-chain / baleias | Efeito em 6-24 h (Magner & Sanhueza 2025) | Transferências internas confundem; Whale Alert é pago | 50% | 15% | Testar depois |
| Prêmio coreano (kimchi) | Útil como termômetro de euforia em altcoins | A arbitragem exige conta em won, KYC coreano e controle de câmbio | 70% sinal / 10% arbitragem | 40% legal | Só como sinal |
| Alertas de terceiros para a Upbit (PKCryptolisting, Tree News) | Promessa de <1 s | Sem preço, endpoint nem método publicados; scraping por baixo | 25% | 10% | Testar com desconfiança, se quiser |
| Polymarket, roadmap da Coinbase | | Sem evidência de retorno; o roadmap da Coinbase depende da API paga do X | 40% | 10% | Descartar por ora |
| Sniping em DEX, memecoins | | Dominado por bots MEV; golpes e honeypots | <5% | 80% | **DESCARTAR** |
| Polling mais rápido na Upbit | | Nossa medição: ~6 s contra uma janela de 1-3 s | 10% | 30% bloqueio | **DESCARTAR** |

## 2. Machine learning e modelos de decisão

| Item | Por que vale | Por que não | Viab. | Risco | Veredito |
|---|---|---|---|---|---|
| Rótulo triple-barrier + meta-labeling | O rótulo segue a regra real de saída; funciona com poucos dados | As larguras das barreiras viram tentativas a contar | 95% | 25% | **ADOTAR** |
| Regressão logística (base) + LightGBM regularizado | Roda em CPU em segundos; difícil de sobreajustar | LightGBM sobreajusta com <500 eventos se não for travado | 98% | 40% | **ADOTAR** |
| Validação purgada / CPCV (skfolio) | Impede vazamento entre eventos sobrepostos | Com poucos eventos fica ruidoso | 90% | 20% | **ADOTAR** |
| Sharpe deflacionado + PBO (código próprio, ~50 linhas) | Corrige a "sorte" de testar muitas ideias; exige um log de tentativas | Precisa de honestidade no log | 95% | 15% | **ADOTAR** |
| Kelly fracionado (0,1-0,25x) + alvo de volatilidade + limite de perda diária | Dimensiona a posição sem quebrar a banca | Kelly cheio com vantagem estimada é perigoso | 95% | 20% | **ADOTAR** (na fase de paper) |
| Gate conformal / limiar de probabilidade | "Não operar" quando o modelo está incerto | Séries temporais quebram a premissa | 85% | 40% | Testar (versão simples) |
| CatBoost, TabPFN v2 | Bons em dados pequenos | Redundantes com o LightGBM | 80-90% | 40% | Testar como comparação |
| TabPFN-2.5/2.6 | | Licença proíbe uso comercial e "decisão comercial interna" | 0% ao vivo | 60% | **DESCARTAR** para ao vivo |
| Modelos de fundação de séries temporais (Chronos-2, TimesFM, Moirai, TiRex, Toto) | Rodam em CPU | Dois estudos (2025, 2026): sem alfa significativo em retornos | 80% | 70% | **DESCARTAR** (no máximo um teste de sanidade) |
| Kronos (modelo de candles) | O único treinado em candles, incluindo cripto | Resultado autodeclarado; um teste independente em BTC 5 min empatou com passeio aleatório | 70% | 75% | Só como benchmark |
| Aprendizado por reforço (FinRL) | | Os próprios autores citam overfitting; precisa de >100 mil decisões; sem replicação independente | 60% | 85% | **DESCARTAR** |
| Aprendizado online (river), HMM de regime | | Poucos eventos; hmmlearn/ruptures sem wheel para Python 3.14 | 50-90% | 50% | Depois; por ora, z-score de volatilidade/funding |

**Hardware:** a GPU não é necessária para nada disso; tudo roda em CPU. ROCm no Windows está em preview e só
suporta Python ≤3.13; DirectML está abandonado. A RX 7600 só serve para LLM local via Vulkan (abaixo).

## 3. IA e LLMs

| Item | Por que vale | Por que não | Viab. | Risco | Veredito |
|---|---|---|---|---|---|
| Destilação: LLM rotula offline e vira um classificador minúsculo (model2vec + logística, ou fastText) | Fica em <1 ms na CPU, com custo zero; lida com coreano | Ruído nos rótulos; precisão em coreano não medida | 90% | 15% | **ADOTAR quando** as regras de palavra-chave errarem de forma medida |
| LLM local Qwen3.5-4B / Gemma 4 E4B (llama.cpp Vulkan) | Cabe nos 8 GB; ~60 tok/s medidos num 7B (estimativa 80-100 para 4B) | Ollama no AMD/Windows **não verificado**; Vulkan é o caminho seguro | 85% | 10% | **TESTAR** (rotular, traduzir coreano, explicar eventos) |
| APIs grátis (Gemini Flash, Mistral, OpenRouter) | Rotular texto público | Limites mudam; o plano grátis treina com seus dados (ok para texto público) | 90% | 20% | Adotar só para rotulagem pontual |
| FinBERT / CryptoBERT | | Só inglês e só sentimento, não o tipo de evento | 80% | 40% | **DESCARTAR** |
| Agentes de trading com LLM (TradingAgents, ai-hedge-fund, FinRobot, FinGPT) | Ideias de prompt | Só backtest ou simulação; nenhuma evidência fora da amostra após custos | 50% | 60% | **DESCARTAR** |
| Alpha Arena (competição de IAs operando) | | S1: 4 de 6 modelos perderam; S1.5: vencedor +12%; n=1 por modelo, ruído puro | | | Entretenimento, não evidência |
| Servidores MCP de corretora (OKX oficial, ccxt) | Facilita consultas | Injeção de prompt vinda de notícia num agente com chave de trade = risco de perda | 70% | 60% | **DESCARTAR** para trade |

Estudos: StockBench (2510.02209) mostra que a maioria dos agentes não bate o "comprar e segurar";
LiveTradeBench (2511.03628), que ranking de chatbot não prevê trading. Há também risco de memorização: o LLM
"lembra" o que aconteceu depois da notícia.

## 4. Infraestrutura

| Item | Por que vale | Por que não | Viab. | Risco | Veredito |
|---|---|---|---|---|---|
| Manter o código próprio | Já funciona e é sob medida para eventos | | 95% | 10% | **ADOTAR** |
| Motor de paper próprio sobre o WS ao vivo, com fills pessimistas (cruza o spread, soma latência) | Mais realista que qualquer testnet | Risco de ficar otimista se mal calibrado | 90% | 25% | **ADOTAR** (próxima fase) |
| Testnet da Binance | Testa o encanamento das ordens | Livro próprio, fills irreais | 90% | 20% | Só para encanamento |
| ccxt (o Pro agora é grátis) | Uma API para várias corretoras | Camada extra; o WS da Binance já funciona | 90% | 10% | Adotar quando houver 2ª corretora |
| DuckDB + Parquet para análise | Consultas rápidas sobre muitos dias | Wheel para 3.14 não verificada; SQLite ainda dá conta | 95% | 5% | Quando as consultas ficarem lentas |
| Tardis.dev (grátis no dia 1 de cada mês) | Checar realismo com livro tick a tick | Só 1 dia por mês | 90% | 5% | Checagem pontual |
| nautilus_trader, freqtrade, hummingbot, hftbacktest | Maduros | Feitos para outro problema (market making, candles); curva alta | 40-80% | 30-40% | **DESCARTAR** por ora |
| VM grátis Oracle em Tóquio/Seul | 8 ms até a Binance a partir de Tóquio | Região fixada no cadastro; recupera VM ociosa (CPU <20% por 7 dias); falta capacidade com frequência; Upbit em si continua sem push | 50% | 35% | Só se o paper mostrar vantagem (você já disse "sem servidor em Tóquio") |

## 5. Lei e imposto (Brasil, pessoa física; confirmar com contador antes de dinheiro real)

- **Paper trading:** sem imposto e sem exposição legal.
- **Ganho em corretora estrangeira:** Lei 14.754/2023, 15% sobre o ganho anual, pago no ajuste. **Não há
  isenção de R$35 mil/mês.** A MP 1303 (17,5%) caducou em 2025-10-08; as regras antigas valem.
- **DeCripto (IN RFB 2.291/2025):** substituiu a IN 1888 em 2026-07-01. Se você operar >R$35 mil/mês sem
  intermediário brasileiro, declara todo mês.
- **IOF:** stablecoin cruzando a fronteira agora é tratada como câmbio (BCB, desde 2026-02-02). Um IOF de 3,5%
  foi noticiado, mas a vigência é **(não verificada)**.
- **Derivativos:** a Binance diz que não oferece derivativos a brasileiros (ordem da CVM; processo reaberto).
  **Planeje só spot.** Isso trava as estratégias de short (seção 1).
- **BCB 519-521/2025:** prazo de adequação das corretoras reportado como 2026-10-30 (uma fonte só); pode mudar
  o acesso de brasileiros a corretoras estrangeiras.

## Caminho proposto (aguardando sua aprovação)

| # | O quê | Esforço | Precisa de você |
|---|---|---|---|
| 1 | Ouvido de anúncios via WebSocket da Binance | ~1 dia | **Sim:** criar uma chave **só leitura** (sem trade e sem saque, com IP restrito) e colocá-la no `.env` |
| 2 | Estudos históricos das brechas lentas com dados que já temos: queda pós-listagem 1-14 d, deslistagem, rebote após liquidação, funding extremo | ~2 dias | Não |
| 3 | Decidir a venda a descoberto: ou só estratégias de compra no spot, ou pesquisar uma corretora de perpétuos legal para brasileiro | pesquisa curta | **Sim:** decisão de risco legal |
| 4 | Pipeline de aprendizado (triple-barrier, logística/LightGBM, validação purgada, Sharpe deflacionado, log de tentativas) | ~3 dias | Não; começa quando houver eventos suficientes |
| 5 | Motor de paper com fills pessimistas e Kelly fracionado | ~3 dias | Não |
| 6 | Classificador destilado e LLM local para rotular | ~2 dias | Não; só se as regras errarem de forma medida |

Fontes completas, por item, nos arquivos de pesquisa (os links principais estão acima no texto):
Binance announcements https://developers.binance.com/en/docs/products/announcements/announcement ;
carry arXiv 2510.14435 ; listagens https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026 ;
Upbit https://research.4pillars.io/en/data/content/the-dying-upbit-listing-pump ;
modelos de fundação arXiv 2511.18578, 2606.27100 ; Kronos arXiv 2508.02739 ;
TabPFN https://docs.priorlabs.ai/models ; agentes arXiv 2510.02209, 2511.03628, 2512.23847 ;
llama.cpp Vulkan https://github.com/ggml-org/llama.cpp/discussions/10879 ; ccxt MCP https://docs.ccxt.com/docs/mcp ;
Oracle Free Tier https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm ;
DeCripto https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2025/novembro/rfb-atualiza-regulamentacao-de-criptoativos-para-adapta-la-ao-padrao-internacional-carf-da-ocde-2013-in-rfb-no-2-291-de-14-de-novembro-de-2025 ;
CVM/Binance https://www.infomoney.com.br/onde-investir/cvm-volta-atras-e-reabre-processo-contra-binance-por-suposta-oferta-irregular-no-brasil/
