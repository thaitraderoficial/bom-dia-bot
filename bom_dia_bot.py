"""
Bom Dia Ninjas - resumo macro diário enviado automaticamente para o Telegram.

Fontes de dados:
- Cripto: CoinGecko (gratuito, sem chave)
- Futuros, câmbio, energia e metais: Stooq (gratuito, sem chave)
- Curadoria e resumo de notícias macro: API da Anthropic (Claude), usando busca na web

Variáveis de ambiente necessárias (Secrets no GitHub):
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- ANTHROPIC_API_KEY
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta

TIMEOUT = 20


# ---------------------------------------------------------------------------
# Cripto (CoinGecko)
# ---------------------------------------------------------------------------

CRYPTO_IDS = {
    "bitcoin": ("🟠", "BTC"),
    "ethereum": ("🔵", "ETH"),
    "solana": ("🟣", "SOL"),
    "ripple": ("⚫", "XRP"),
    "hyperliquid": ("🟢", "HYPE"),
    "tron": ("🔴", "TRX"),
}


def get_crypto():
    try:
        ids = ",".join(CRYPTO_IDS.keys())
        url = (
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        )
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()

        linhas = []
        for coin_id, (emoji, ticker) in CRYPTO_IDS.items():
            if coin_id not in data:
                linhas.append(f"{emoji} {ticker}: dado indisponível")
                continue
            preco = data[coin_id]["usd"]
            variacao = data[coin_id].get("usd_24h_change", 0)
            seta = "🔺" if variacao >= 0 else "🔻"
            linhas.append(
                f"{emoji} {ticker}: US$ {preco:,.2f}  {seta} {variacao:+.2f}% (24h)"
            )
        return "\n".join(linhas)
    except Exception as e:
        return f"Não foi possível obter os dados de cripto ({e})"


# ---------------------------------------------------------------------------
# Stooq (futuros, câmbio, energia, metais)
# ---------------------------------------------------------------------------

def get_stooq_quote(symbol):
    """Retorna (close, variacao_pct) ou None se falhar."""
    try:
        url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) < 2:
            return None
        header = lines[0].split(",")
        values = lines[1].split(",")
        row = dict(zip(header, values))
        close = float(row["Close"])
        open_ = float(row["Open"])
        if close == 0 or row["Close"] in ("N/D", ""):
            return None
        variacao = ((close - open_) / open_ * 100) if open_ else 0
        return close, variacao
    except Exception:
        return None


def format_linha(emoji, nome, symbol, casas=2, prefixo=""):
    resultado = get_stooq_quote(symbol)
    if resultado is None:
        return f"{emoji} {nome}: Mercado fechado ou dado indisponível"
    close, variacao = resultado
    seta = "🔺" if variacao >= 0 else "🔻"
    return f"{emoji} {nome}: {prefixo}{close:,.{casas}f}  {seta} {variacao:+.2f}%"


def get_macro_section():
    linhas = [
        format_linha("📈", "S&P 500 (Futuros)", "es.f"),
        format_linha("📈", "Nasdaq (Futuros)", "nq.f"),
        format_linha("💵", "Índice do Dólar (DXY)", "dx.f"),
    ]
    return "\n".join(linhas)


def get_energia_section():
    linhas = [
        format_linha("🛢", "Brent", "cb.f"),
        format_linha("🛢", "WTI", "cl.f"),
        format_linha("🔥", "Gás Natural", "ng.f"),
    ]
    return "\n".join(linhas)


def get_metais_section():
    linhas = [
        format_linha("🥇", "Ouro", "gc.f"),
        format_linha("🔶", "Cobre", "hg.f"),
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Notícias (curadoria via Claude, com busca na web)
# ---------------------------------------------------------------------------

NEWS_SYSTEM_PROMPT = """\
Você gera a seção "MANCHETE DO DIA" de um resumo macro diário para Telegram, em português do Brasil.

Pesquise as notícias econômicas mais importantes das últimas horas. Priorize apenas
acontecimentos que realmente possam impactar os mercados, como: Federal Reserve, FOMC,
Payroll, CPI, PCE, PPI, PIB, ISM, PMIs, pedidos de auxílio-desemprego, leilões do Tesouro
americano, Banco Central Europeu, Banco do Japão, Banco Popular da China, inflação na
Europa/Japão/China, geopolítica, petróleo, tarifas, guerra comercial, ETFs de Bitcoin e
Ethereum, fluxo institucional, regulações relevantes.

Regras obrigatórias:
- Escreva sempre em português do Brasil.
- Nunca invente dados.
- Utilize apenas informações verificadas, obtidas pela busca na web.
- Não faça análises pessoais nem gere opiniões — apenas apresente dados objetivos.
- Se houver uma notícia relevante, escreva um resumo de no máximo 3 linhas explicando
  por que ela pode impactar o mercado.
- Se não houver nenhuma notícia relevante nas últimas horas, responda EXATAMENTE:
  "Até o momento, não há notícias macroeconômicas relevantes capazes de alterar
  significativamente o sentimento dos mercados."
- Responda APENAS com o texto da seção, sem título, sem introdução, sem comentários extras.
- Use no máximo 1 emoji no texto todo, se fizer sentido.
"""


def get_news_section():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Não foi possível gerar a seção de notícias (ANTHROPIC_API_KEY não configurada)."

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 500,
            "system": NEWS_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": "Gere a seção de manchete do dia com base nas notícias mais recentes.",
                }
            ],
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()

        textos = [bloco["text"] for bloco in data.get("content", []) if bloco.get("type") == "text"]
        resultado = "\n".join(textos).strip()
        return resultado or "Não foi possível gerar a seção de notícias."
    except Exception as e:
        return f"Não foi possível gerar a seção de notícias ({e})."


# ---------------------------------------------------------------------------
# Montagem da mensagem
# ---------------------------------------------------------------------------

def montar_mensagem():
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br).strftime("%d/%m/%Y")

    partes = [
        "🥷 *BOM DIA, NINJAS!*",
        f"Confira como os mercados iniciam o dia — {agora}",
        "",
        "🌍 *MACRO*",
        get_macro_section(),
        "",
        "⚡ *ENERGIA*",
        get_energia_section(),
        "",
        "🪙 *METAIS*",
        get_metais_section(),
        "",
        "₿ *MERCADO CRIPTO*",
        get_crypto(),
        "",
        "📰 *MANCHETE DO DIA*",
        get_news_section(),
    ]
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Envio para o Telegram
# ---------------------------------------------------------------------------

def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("ERRO: defina as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=TIMEOUT)
    if not r.ok:
        print("Falha ao enviar para o Telegram:", r.text)
        sys.exit(1)
    print("Mensagem enviada com sucesso!")


if __name__ == "__main__":
    mensagem = montar_mensagem()
    print(mensagem)  # aparece nos logs do GitHub Actions, útil para debug
    enviar_telegram(mensagem)
