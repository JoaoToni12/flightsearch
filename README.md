# flightsearch

Monitor **signal-first** de passagens **São Paulo ⇄ Europa** (ida e volta, 7–14 dias, até 6 meses), com alertas por e-mail.

## O que mudou (v2)

- Destinos: **PAR, MAD, LYS, NCE, MRS, BCN**
- Trip: **roundtrip** (não só ida)
- Detector: **% abaixo do baseline da rota** + sinais Melhores Destinos + Google `price_insights`
- Budget A (≤ R$20/mês): SerpApi **free 250**/mês só para deals/confirm

## Fontes

| Camada | Fonte | Papel |
|--------|--------|--------|
| L0 | Melhores Destinos RSS | Sinais de promo BR (alta precisão) |
| L1 | Travelpayouts month-matrix / latest / range / grouped | Rede larga (cache ~48h) |
| L2 | SerpApi Deals + Google Flights confirm | Live + `price_level` |

## Alertas

- **Rare (verde):** ≥40% abaixo do baseline **ou** `price_level=low` (e ≤ teto `MAX_ALERT_PRICE_BRL`)
- **Good (amarelo):** ≥25% abaixo do baseline
- Digest de pulso a cada `SCAN_DIGEST_HOURS` (default 24h)

## Deploy

Veja [RUNBOOK.md](RUNBOOK.md).

```bash
pip install -r requirements.txt
pytest -q
python main.py   # precisa das env vars / secrets
```
