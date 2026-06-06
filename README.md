# flightsearch

Monitor automático de passagens **São Paulo → França** (só ida, 23–27/07/2026) com alertas por **e-mail**.

## Fontes de preço

1. **Travelpayouts / Aviasales** — grátis, alta cota
2. **SerpApi / Google Flights** — 250 buscas/mês grátis (1 data por execução)

## Regra de alerta

- Preço **≥ 30–40% abaixo** da referência de mercado (padrão 35%), **ou**
- Preço **menor que o último alerta** enviado (anti-spam inteligente)

## Deploy

Veja [RUNBOOK.md](RUNBOOK.md) para configurar secrets, variables e GitHub Actions.

```bash
pip install -r requirements.txt
python main.py   # local (precisa das env vars)
```
