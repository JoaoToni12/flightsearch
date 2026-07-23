# Runbook — Flight Tracker SAO ⇄ EU (budget A)

Caçador de oportunidades **ida e volta** São Paulo → Europa (França / Madri / próximos), horizonte **6 meses**, stay **7–14 dias**.

## Arquitetura (≤ R$20/mês)

| Camada | Serviço | Custo |
|--------|---------|-------|
| L0 sinais | Melhores Destinos RSS | Grátis |
| L1 rede | Travelpayouts Data API | Grátis |
| L2 live | SerpApi (250/mês free) | Grátis |
| E-mail | Resend ou SMTP | Grátis |
| Host | GitHub Actions | Grátis |
| Estado | Variable `FLIGHT_TRACKER_STATE` | Grátis |

**Não usar** Amadeus Self-Service (descontinuado). **Não** Telegram Bot em canais MD/PI (exige admin).

### SerpApi ration (~8 calls/dia)

1. Até `SERPAPI_DEALS_PER_DAY` (default 2) → `google_flights_deals`
2. Confirmar candidatos MD RSS
3. Confirmar top outliers Travelpayouts com GF RT + `price_insights`

Governor em `serpapi_budget.py` persiste contadores no state.

## Secrets

| Nome | Obrigatório |
|------|-------------|
| `TRAVELPAYOUTS_TOKEN` | sim (L1) |
| `SERPAPI_KEY` | sim (L2) |
| `RESEND_API_KEY` ou `SMTP_*` | sim (e-mail) |
| `ALERT_EMAIL` | sim |
| `GH_PAT` | sim (persistir state; scope `variables`) |

## Variables sugeridas

| Nome | Default |
|------|---------|
| `DESTINATION_CITIES` | `PAR,MAD,LYS,NCE,MRS,BCN` |
| `ORIGIN_AIRPORTS` | `GRU,VCP` |
| `HORIZON_MONTHS` | `6` |
| `TRIP_LENGTH_MIN` / `MAX` | `7` / `14` |
| `RARE_DISCOUNT_PCT` | `40` |
| `GOOD_DISCOUNT_PCT` | `20` |
| `MAX_ALERT_PRICE_BRL` | `4000` |
| `SERPAPI_MONTHLY_BUDGET` | `250` |
| `SERPAPI_DAILY_SOFT_CAP` | `8` |
| `SERPAPI_PAUSED_UNTIL` | vazio (`YYYY-MM-DD` pausa o L2 até a data; auto-resume) |
| `MD_RSS_ENABLED` | `true` |
| `MD_RSS_MAX_AGE_DAYS` | `21` (posts MD mais velhos são ignorados na origem) |

## Schedule

- Workflow `tracker.yml`: cron `5,25,45 * * * *` UTC (3 janelas/hora — o scheduler do GitHub pula runs; múltiplas entradas elevam a cobertura efetiva) + `workflow_dispatch`
- `cancel-in-progress: true`
- Dispatcher sleep-58m **removido**
- Complemento opcional: cron-job.org disparando `workflow_dispatch` (se usar, o GH_PAT armazenado lá precisa ser atualizado a cada rotação do PAT — foi assim que o dispatcher morreu em 2026-07-22)

### cron-job.org

`POST https://api.github.com/repos/OWNER/REPO/actions/workflows/tracker.yml/dispatches`

Header: `Authorization: Bearer <GH_PAT>`, body `{"ref":"main"}`.

## Local

```bash
export TRAVELPAYOUTS_TOKEN=...
export SERPAPI_KEY=...
export ALERT_EMAIL=voce@email.com
export RESEND_API_KEY=...
python main.py
```

## Troubleshooting

- **Sem alertas:** baselines ainda curtos (primeiros dias); ou preços > `MAX_ALERT_PRICE_BRL`
- **SerpApi silencioso:** cota do mês esgotada (ver logs `SerpApi budget`) ou `SERPAPI_PAUSED_UNTIL` vigente
- **MD sem candidatos EU:** feed sem promo França/Espanha naquele ciclo (normal)
- **State grande:** `seen_md_guids` capped em 200; baselines por rota só medianas + séries curtas
- **Run vermelho com exit 2:** o trabalho completou mas o state NÃO persistiu — GH_PAT expirado ou sem scope de Actions Variables. Após 24h de staleness, um ops-alert chega por e-mail (1x/dia). Fix: novo fine-grained PAT com Variables read/write no secret `GH_PAT`. **Não deixar acumular**: sem persistência, digests repetem e a cota SerpApi é re-gasta a cada run (incidente de 425 falhas em 2026-07-06→22)
- **Alerta RARE suspeito de post MD antigo:** não deve mais ocorrer — itens com `pubDate` > `MD_RSS_MAX_AGE_DAYS` são descartados e a janela de viagem exige partida futura
