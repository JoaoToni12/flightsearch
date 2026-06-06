# Runbook — Flight Tracker SAO → PAR (grátis)

Monitor de passagens **só ida** (23–27/07/2026) com **duas fontes gratuitas**, alerta por **e-mail** e estado persistente no GitHub.

## Arquitetura (100% free tier)

| Componente | Serviço | Custo |
|------------|---------|-------|
| Fonte 1 | [Travelpayouts](https://www.travelpayouts.com/) Aviasales Data API | Grátis |
| Fonte 2 | [SerpApi](https://serpapi.com/) Google Flights | 250 buscas/mês grátis |
| E-mail | [Resend](https://resend.com/) ou SMTP (Gmail/Brevo) | Grátis |
| Host | GitHub Actions (repo público) | Grátis |
| Estado | Repository Variable `FLIGHT_TRACKER_STATE` | Grátis |

**Cron:** a cada 2 horas (`0 */2 * * *` UTC).

- Travelpayouts consulta **todas as 5 datas** a cada run.
- SerpApi consulta **1 data por run** (round-robin) → ~180 buscas/mês, dentro do free tier.

## Preço de referência e alvos (dinâmico)

**Por que a referência pode ser maior que o menor preço do scan?**

Com duas fontes, a referência CAPES usa o **maior mínimo por fonte** (ex.: Travelpayouts R$ 2.448 vs SerpApi/Google R$ 3.495 → ref. **R$ 3.495**). O scan mostra o melhor achado; a referência é o baseline conservador para não emitir cedo demais.

| Tier | Regra | Frequência alvo (cron 2h) |
|------|-------|---------------------------|
| **Verde** (compra) | preço **<** `ref × 65%` (−35%) | ~1 alerta a cada 2–3 dias |
| **Amarelo** (observação) | faixa **verde ≤ preço < verde×1,06** (+6%) | ~2 alertas/dia no máximo |

Reenvio exige quebra mínima: amarelo Δ≥R$ 60, verde Δ≥R$ 80 vs último alerta do tier.

Variáveis opcionais: `TARGET_DISCOUNT_PCT`, `YELLOW_BAND_ABOVE_GREEN_PCT`, `YELLOW_MIN_BREAK_BRL`, `GREEN_MIN_BREAK_BRL`.

## 1. Criar repositório público

```bash
git init
git add .
git commit -m "feat: flight tracker SAO-PAR multi-source"
git remote add origin https://github.com/SEU_USUARIO/flightsearch.git
git push -u origin main
```

Nunca commite tokens. Tudo sensível vai em **Secrets** e **Variables**.

## 2. Travelpayouts (obrigatório para free tier)

1. Cadastre-se em https://www.travelpayouts.com/
2. Perfil → **API token** → copie o token
3. GitHub → Settings → Secrets → **New repository secret**
   - Nome: `TRAVELPAYOUTS_TOKEN`
   - Valor: seu token

## 3. SerpApi (recomendado — Google Flights)

1. Cadastre-se em https://serpapi.com/ (250 buscas/mês grátis)
2. Dashboard → API Key
3. Secret: `SERPAPI_KEY`

## 4. E-mail — opção A: Resend (mais simples)

1. https://resend.com/ → conta grátis (3.000 e-mails/mês)
2. Secret: `RESEND_API_KEY`
3. Para testes sem domínio próprio, use:
   - Variable `EMAIL_FROM` = `onboarding@resend.dev`
   - Só envia para o e-mail da conta Resend
4. Com domínio verificado: `EMAIL_FROM` = `alertas@seudominio.com`

## 4. E-mail — opção B: SMTP (Gmail / Brevo)

**Gmail** (app password):

| Secret | Exemplo |
|--------|---------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `seu@gmail.com` |
| `SMTP_PASSWORD` | senha de app Google |
| Variable `EMAIL_FROM` | `seu@gmail.com` |

**Brevo** (300 e-mails/dia grátis): use SMTP da Brevo com os mesmos secrets.

## 5. Variáveis do repositório (não sensíveis)

Settings → Secrets and variables → Actions → **Variables**:

| Nome | Valor sugerido |
|------|----------------|
| `ALERT_EMAIL` | seu@email.com |
| `EMAIL_FROM` | onboarding@resend.dev (ou seu remetente) |
| `TARGET_DISCOUNT_PCT` | `35` (30–40 conforme preferência) |
| `MARKET_REFERENCE_SEED_BRL` | `4200` |
| `FLIGHT_TRACKER_STATE` | *(deixe vazio na 1ª vez)* |

## 6. PAT para gravar estado (anti-spam)

O `GITHUB_TOKEN` padrão **não grava** Repository Variables.

1. GitHub → Settings → Developer settings → **Fine-grained PAT**
2. Permissões no repo: **Actions: Read and write** (Variables)
3. Secret: `GH_PAT`

## 7. Testar manualmente

Actions → **Flight Tracker SAO→PAR** → **Run workflow**.

Logs esperados:

```
Scan: R$ X | Ref: R$ Y | Alvo (-35%): R$ Z | Fontes: ['travelpayouts', 'serpapi_google_flights']
```

## 8. Segurança (repo público)

- Secrets **nunca** aparecem em logs se você não der `print` neles.
- `FLIGHT_TRACKER_STATE` contém apenas preços e metadados de voo — sem PII.
- Não commite `.env` (já está no `.gitignore`).

## 9. Ajustes opcionais

| Variable | Efeito |
|----------|--------|
| `TARGET_DISCOUNT_PCT` | `30` = alerta mais fácil; `40` = mais exigente |
| `REFERENCE_RECALIBRATE_DAYS` | Padrão `7` |
| `SERPAPI_ENABLED` | `false` desliga Google Flights |
| `FLIGHT_DEPARTURE_DATES` | Lista CSV de datas |

## 10. Limitações conhecidas

- **Travelpayouts** usa cache (até 48h) — pode atrasar promo relâmpago; SerpApi compensa.
- **SerpApi free** não suporta 5 datas a cada 2h — por isso o round-robin.
- Links Aviasales são afiliados; Google Flights / Skyscanner são gerados como alternativa CAPES-friendly.

## Troubleshooting

| Problema | Solução |
|----------|---------|
| `Nenhuma oferta encontrada` | Confira `TRAVELPAYOUTS_TOKEN` |
| E-mail não chega | Resend: só envia para e-mail da conta no sandbox |
| Estado não persiste | Confira `GH_PAT` com permissão Variables write |
| SerpApi 401 | `SERPAPI_KEY` inválida ou cota esgotada |
