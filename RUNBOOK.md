# Runbook — Flight Tracker SAO → PAR (grátis)

Monitor de passagens **só ida** (23–27/07/2026) com **até 3 fontes**, alerta por **e-mail** e estado persistente no GitHub.

## Arquitetura (100% free tier)

| Componente | Serviço | Custo |
|------------|---------|-------|
| Fonte 1 | [Travelpayouts](https://www.travelpayouts.com/) Aviasales Data API | Grátis |
| Fonte 2 | [SerpApi](https://serpapi.com/) Google Flights | 250 buscas/mês grátis |
| Fonte 3 | Travelpayouts range + grouped + SerpApi Explore | Grátis (mesmos tokens) |
| E-mail | [Resend](https://resend.com/) ou SMTP (Gmail/Brevo) | Grátis |
| Host | GitHub Actions (repo público) | Grátis |
| Estado | Repository Variable `FLIGHT_TRACKER_STATE` | Grátis |

**Cron:** a cada 1 hora (`0 * * * *` UTC). Campanha típica: **7 dias** (~168 runs).

| Fonte | Frequência | Cache | Setup |
|-------|------------|-------|-------|
| **Travelpayouts dates** | 5 datas/run | ~48h (Aviasales) — **não dá para resetar** no free tier | `TRAVELPAYOUTS_TOKEN` ✓ |
| **Travelpayouts range** | faixa 55–115% da ref. | cache ~48h, slice diferente | mesmo token ✓ |
| **Travelpayouts grouped** | 1 call/mês julho | mínimo por data agrupado | mesmo token ✓ |
| **SerpApi Google Flights** | 1 data/run, `no_cache` | fresco a cada hora | `SERPAPI_KEY` ✓ |
| **SerpApi Travel Explore** | mesma data, a cada 4 runs | ângulo alternativo Google | mesmo `SERPAPI_KEY` ✓ |

### Travelpayouts e cache

A Data API **sempre** serve cache Aviasales (até 48h). Não há reset gratuito. Compensamos com **3 endpoints Travelpayouts** + **2 engines SerpApi** — zero cadastro novo.

## Preço de referência e alvos (dinâmico)

**Como a referência é calculada**

Para cada data monitorada (23–27/07), pegamos o **menor preço encontrado** e tiramos a **média** desses mínimos. Ex.: mínimos R$ 2.448 + R$ 2.500 + R$ 2.448 → ref. **R$ 2.465**. O scan mostra o melhor achado global; a referência é o preço típico na faixa de datas.

| Tier | Regra | Frequência alvo (cron 1h) |
|------|-------|---------------------------|
| **Verde** (compra) | preço **<** `ref × 65% × 1,10` | quando acha oportunidade CAPES |
| **Amarelo** (observação) | **verde ≤ preço < max(faixa estreita, ref×102%)** | mercado típico (~R$ 2.400–2.550) |

Reenvio: amarelo Δ≥R$ 60 ou **realerta a cada 24h** (`YELLOW_RESEND_HOURS`); verde Δ≥R$ 80.

E-mails mostram **horário de saída/chegada** quando a API retorna; ranking prioriza datas 24/25, voos **diretos** e menos escalas.

Variáveis opcionais: `TARGET_DISCOUNT_PCT`, `YELLOW_CEILING_REFERENCE_PCT`, `YELLOW_RESEND_HOURS`, `MAX_STOPS_PREFERENCE`, `HUNT_PRICE_MIN_PCT`, `HUNT_PRICE_MAX_PCT`.

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

## 4. E-mail — segundo destinatário (encaminhamento Gmail)

O jeito mais simples: alertas chegam no **seu** Gmail via Resend; você **encaminha automaticamente** pro Thiago (ou quem for). Zero config no GitHub.

1. Gmail → ⚙️ **Ver todas as configurações** → **Encaminhamento e POP/IMAP**
2. **Adicionar endereço de encaminhamento** → `thiagofm.br@gmail.com`
3. Thiago confirma o link que o Google manda
4. Crie um **filtro** (recomendado — só alertas, não todo o inbox):
   - **Configurações** → **Filtros e endereços bloqueados** → **Criar filtro**
   - Assunto contém: `SAO→PAR` (ou remetente contém `resend.dev`)
   - Ação: **Encaminhar para** `thiagofm.br@gmail.com`
5. Deixe `ALERT_EMAIL_CC` **vazio** no GitHub (só `ALERT_EMAIL` = seu Gmail)

Pronto: Resend continua funcionando; Thiago recebe cópia automática.

### Alternativa: SMTP ou CC no GitHub

Só se não quiser encaminhamento — exige senha de app (Gmail) ou domínio verificado (Resend). Ver seções 4b/4c.

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
