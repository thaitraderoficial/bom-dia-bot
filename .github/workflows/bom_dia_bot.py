"""
Bom Dia Bot - resumo diário de mercado (petróleo, S&P 500, Bitcoin e notícias)
enviado automaticamente para o Telegram.

Fontes usadas (todas gratuitas, sem necessidade de chave de API):
- Bitcoin: CoinGecko
- S&P 500 e Petróleo (WTI): Stooq
- Notícias: RSS do CoinDesk (cripto) e RSS de economia do Investing.com

Variáveis de ambiente necessárias (configuradas como Secrets no GitHub):
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

TIMEOUT = 15


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

def get_bitcoin():
    """Retorna preço do BTC em USD e BRL + variação 24h."""
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin&vs_currencies=usd,brl&include_24hr_change=true"
        )
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()["bitcoin"]
        usd = data["usd"]
        brl = data["brl"]
        change = data["usd_24h_change"]
        seta = "🟢" if change >= 0 else "🔴"
        return (
            f"₿ *Bitcoin*: US$ {usd:,.0f} (R$ {brl:,.0f}) "
            f"{seta} {change:+.2f}% (24h)"
        )
    except Exception as e:
        return f"₿ *Bitcoin*: não foi possível obter os dados ({e})"


def get_stooq_quote(symbol, label):
    """Busca cotação simples de um símbolo no Stooq (CSV)."""
    try:
        url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) < 2:
            raise ValueError("resposta vazia do Stooq")
        header = lines[0].split(",")
        values = lines[1].split(",")
        row = dict(zip(header, values))
        close = float(row["Close"])
        open_ = float(row["Open"])
        change = ((close - open_) / open_ * 100) if open_ else 0
        seta = "🟢" if change >= 0 else "🔴"
        return f"{label}: {close:,.2f} {seta} {change:+.2f}% (dia)"
    except Exception as e:
        return f"{label}: não foi possível obter os dados ({e})"


def get_sp500():
    return get_stooq_quote("^spx", "📈 *S&P 500*")


def get_oil():
    return get_stooq_quote("cl.f", "🛢️ *Petróleo (WTI)*")


def get_rss_headlines(url, max_items=3):
    """Pega os títulos mais recentes de um feed RSS."""
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        titles = [item.findtext("title") for item in root.iter("item")]
        titles = [t.strip() for t in titles if t][:max_items]
        return titles
    except Exception:
        return []


def get_news_section():
    cripto = get_rss_headlines("https://www.coindesk.com/arc/outboundfeeds/rss/", 3)
    economia = get_rss_headlines("https://www.investing.com/rss/news_25.rss", 3)

    linhas = []
    if cripto:
        linhas.append("🪙 *Cripto:*")
        linhas += [f"• {t}" for t in cripto]
    if economia:
        linhas.append("\n🌍 *Economia:*")
        linhas += [f"• {t}" for t in economia]

    if not linhas:
        return "📰 Não foi possível carregar as notícias hoje."
    return "📰 *Manchetes de hoje*\n" + "\n".join(linhas)


# ---------------------------------------------------------------------------
# Montagem da mensagem
# ---------------------------------------------------------------------------

def montar_mensagem():
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")

    partes = [
        f"☀️ *Bom dia! Resumo de mercado - {agora} (Brasília)*",
        "",
        get_bitcoin(),
        get_sp500(),
        get_oil(),
        "",
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
