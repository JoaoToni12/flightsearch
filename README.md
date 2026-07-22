# flightsearch

Monitor **signal-first** de passagens **São Paulo ⇄ Europa** (ida e volta, 7–14 dias, até 6 meses), com alertas por e-mail.

## O que mudou (v2)

- Destinos: **PAR, MAD, LYS, NCE, MRS, BCN**
- Trip: **roundtrip** (não só ida)
- Detector: **% abaixo do baseline da rota** + sinais Melhores Destinos + Google `price_insights`
- Budget A: SerpApi **free 250**/mês só para deals/confirm (opcional; L0/L1 rodam sem ele)
- Janela de estadia **7–14 dias** enforced pós-fetch (descarta RT fora do produto)
- MD RSS: parse de datas + enrich HTML leve → ofertas tipadas mesmo sem SerpApi

## Fontes

| Camada | Fonte | Papel |
|--------|--------|--------|
| L0 | Melhores Destinos RSS (+datas) | Sinais de promo BR; vira oferta se preço+datas 7–14d |
| L1 | Travelpayouts month-matrix / latest / range / grouped | Rede larga (cache ~48h), filtrada 7–14d |
| L2 | SerpApi Deals + Google Flights confirm | Live + `price_level` (quando habilitado) |

## Alertas

- **Rare (verde):** ≥40% abaixo do baseline **ou** `price_level=low` (e ≤ teto `MAX_ALERT_PRICE_BRL`, default **4000**)
- **Good (amarelo):** ≥20% abaixo do baseline
- Digest de pulso a cada `SCAN_DIGEST_HOURS` (default 24h)

## Deploy

Veja [RUNBOOK.md](RUNBOOK.md).

```bash
pip install -r requirements.txt
pytest -q
python main.py   # precisa das env vars / secrets
```
