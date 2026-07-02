# Bom Dia Bot ☀️

Envia automaticamente todo dia de manhã, para o seu Telegram, um resumo com:
- Preço do Bitcoin (USD/BRL) e variação nas últimas 24h
- Cotação do S&P 500
- Cotação do Petróleo (WTI)
- Manchetes de notícias de cripto e economia

Roda de graça no **GitHub Actions**, sem precisar de servidor.

## 1. Como testar localmente (opcional)

```bash
pip install requests
export TELEGRAM_BOT_TOKEN="seu_token_aqui"
export TELEGRAM_CHAT_ID="seu_chat_id_aqui"
python bom_dia_bot.py
```

Se aparecer "Mensagem enviada com sucesso!" e a mensagem chegar no Telegram, está funcionando.

## 2. Como descobrir o CHAT_ID (se ainda não tiver)

- Se for enviar para um **grupo**: adicione o bot ao grupo, mande qualquer mensagem no grupo,
  depois acesse `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` no navegador e procure
  o campo `"chat":{"id": ...}`. Para grupos, o ID geralmente é negativo (ex: -1001234567890).
- Se for enviar para um **canal**: adicione o bot como administrador do canal e use
  `@nome_do_canal` como CHAT_ID (se o canal for público), ou o ID numérico (se for privado).
- Se for enviar para você mesmo (chat privado): mande uma mensagem para o bot e siga o
  mesmo processo do `getUpdates` acima.

## 3. Subindo para o GitHub

1. Crie um repositório novo no GitHub (pode ser privado).
2. Suba estes arquivos para ele (mantendo a pasta `.github/workflows/`):
   - `bom_dia_bot.py`
   - `.github/workflows/bom_dia.yml`
   - este `README.md`
3. No repositório, vá em **Settings → Secrets and variables → Actions → New repository secret**
   e crie dois secrets:
   - `TELEGRAM_BOT_TOKEN` → o token do seu bot (do @BotFather)
   - `TELEGRAM_CHAT_ID` → o ID do grupo/canal/chat

## 4. Testando o workflow

Vá na aba **Actions** do repositório, clique em **Bom Dia Bot** e depois em
**Run workflow** para disparar manualmente e conferir se a mensagem chega certinho.

## 5. Ajustando o horário

O horário está configurado em `.github/workflows/bom_dia.yml`, na linha do `cron`:

```yaml
- cron: "0 10 * * 1-5"
```

Esse cron roda **10:00 UTC = 07:00 em Brasília**, de segunda a sexta (`1-5`).
Para rodar também no fim de semana, troque `1-5` por `*`.
Para mudar o horário, ajuste a hora em UTC (lembrando que Brasília = UTC-3).

> Obs: o GitHub Actions pode atrasar alguns minutos em horários de pico — é normal,
> não é possível garantir o disparo no segundo exato.

## 6. Personalizando o conteúdo

Todo o texto e as fontes de dados estão em `bom_dia_bot.py`, nas funções:
- `get_bitcoin()` — Bitcoin (CoinGecko)
- `get_sp500()` / `get_oil()` — cotações via Stooq
- `get_news_section()` — manchetes via RSS

Pode adicionar mais ativos do Stooq (ex: dólar `usdbrl`, Nasdaq `^ndq`, ouro `xauusd`)
chamando `get_stooq_quote("simbolo", "🔖 *Nome*")` e incluindo o resultado em
`montar_mensagem()`.

## Limitações a ter em mente

- Todas as fontes usadas são gratuitas e sem chave de API — por isso podem ter
  pequenos atrasos ou instabilidade ocasional. Se algum dado falhar, o bot ainda
  envia o restante da mensagem normalmente (com um aviso no lugar do dado que falhou).
- Isso é uma leitura informativa automatizada, não uma recomendação de investimento.
