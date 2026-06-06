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

**Como a referência é calculada**

Para cada data monitorada (23–27/07), pegamos o **menor preço encontrado** e tiramos a **média** desses mínimos. Ex.: mínimos R$ 2.448 + R$ 2.500 + R$ 2.448 → ref. **R$ 2.465**. O scan mostra o melhor achado global; a referência é o preço típico na faixa de datas.

| Tier | Regra | Frequência alvo (cron 2h) |
|------|-------|---------------------------|
| **Verde** (compra) | preço **<** `ref × 65% × 1,10` | ~1 alerta a cada 2–3 dias |
| **Amarelo** (observação) | faixa **verde ≤ preço < verde×1,06×1,10** | ~2 alertas/dia no máximo |

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

## 4. E-mail — dois destinatários (solução mais rápida)

O Resend com `onboarding@resend.dev` **só envia para o e-mail da conta**. Para o Thiago (ou qualquer CC) receber também, use **Gmail SMTP** (~5 min):

1. Google → Conta → Segurança → **Senhas de app** (exige 2FA)
2. Gere uma senha para “Mail” / “GitHub Actions”
3. GitHub → Settings → Secrets → Actions:

| Secret | Valor |
|--------|-------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | seu@gmail.com |
| `SMTP_PASSWORD` | senha de app (16 caracteres) |

4. Variable `EMAIL_FROM` = mesmo `SMTP_USER`
5. Variable `ALERT_EMAIL_CC` = `thiagofm.br@gmail.com` (já no workflow)

Com SMTP configurado, o tracker **prioriza SMTP automaticamente** quando há mais de um destinatário. Pode manter `RESEND_API_KEY` para testes solo.

## 4b. E-mail — opção A: Resend (um destinatário)

1. https://resend.com/ → conta grátis (3.000 e-mails/mês)
2. Secret: `RESEND_API_KEY`
3. `onboarding@resend.dev` → só o e-mail da conta Resend
4. Domínio verificado no Resend → vários destinatários sem SMTP

## 4c. E-mail — opção B: Brevo SMTP

300 e-mails/dia grátis — mesmos secrets `SMTP_*` com host `smtp-relay.brevo.com`.

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
