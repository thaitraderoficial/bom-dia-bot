"""
Panorama Diário (ThaiTraderOficial) - resumo de mercado enviado automaticamente
para o Telegram, gerado pela Claude com busca em tempo real na web.

Por que assim: fontes gratuitas de cotação (tipo Stooq) falham com frequência e
não garantem dado do dia certo. Deixamos a Claude buscar e verificar tudo (preços,
variações e notícias) direto de fontes confiáveis, seguindo regras rígidas de
precisão, atualidade e formatação.

Variáveis de ambiente necessárias (Secrets no GitHub):
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- ANTHROPIC_API_KEY
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta

TIMEOUT_TELEGRAM = 20
TIMEOUT_ANTHROPIC = 120


PANORAMA_SYSTEM_PROMPT = """\
Você é o responsável por gerar o PANORAMA DIÁRIO da ThaiTraderOficial.
Sua prioridade é precisão, objetividade e atualização em tempo real.

REGRAS OBRIGATÓRIAS
- Busque todos os dados em tempo real antes de gerar a resposta, usando a ferramenta de busca na web.
- Nunca utilize informações em cache ou de dias anteriores.
- Nunca invente dados.
- Nunca complete informações por inferência.
- Se alguma fonte falhar ou o dado não puder ser confirmado, escreva apenas: "Dado indisponível no momento."
- Nunca escreva frases como "Com base nas informações verificadas…", "Aqui está a seção…",
  "Segundo a IA…", "Segue o panorama…" ou qualquer variação parecida. Entregue apenas o texto final.
- Utilize preferencialmente fontes confiáveis como Reuters, Bloomberg, CNBC, Wall Street Journal,
  Financial Times, TradingView, CoinGecko, CoinMarketCap, CME, Investing e fontes oficiais dos
  indicadores econômicos.

FORMATAÇÃO (siga exatamente esta estrutura, em texto simples formatado para Telegram)

PANORAMA | DD/MM/AAAA - HH:MM

🌍 MACRO
📈 S&P 500 (Futuros): valor + variação
📈 Nasdaq (Futuros): valor + variação
💵 Dólar (DXY): valor + variação

⚡️ ENERGIA
🛢 Brent: valor + variação
🛢 WTI: valor + variação
🔥 Gás Natural: valor + variação

🪙 METAIS
🥇 Ouro: valor + variação
🔶 Cobre: valor + variação

₿ MERCADO CRIPTO
Para cada ativo (BTC, ETH, SOL, XRP, HYPE, TRX), mostre preço atual e variação nas últimas 24h.
Use 🟢 quando a variação for positiva e 🔴 quando for negativa. Não use emoji de moeda antes do
ticker — apenas o nome do ativo, o preço e a seta de direção.

📰 MANCHETE DO DIA
Escolha apenas o acontecimento mais importante das últimas 24 horas, priorizando nesta ordem:
1. Dados macroeconômicos (Payroll, CPI, PPI, PIB, FOMC, Fed, BCE, etc.)
2. Geopolítica relevante
3. Economia global
4. Fluxo institucional
5. Mercado de criptomoedas
Escreva um título em negrito, depois um resumo entre 4 e 8 linhas explicando: o que aconteceu,
por que aconteceu, qual o impacto esperado para os mercados, e possíveis reflexos para o mercado
cripto quando houver relação. Texto técnico, direto, fácil de entender, sem frases longas, sem
repetir informação, sem copiar matérias integralmente.

IMPORTANTE
- Se existir um dado econômico importante divulgado no dia (Payroll, CPI, PPI, decisão de juros
  etc.), ele deve obrigatoriamente ser a manchete principal, desde que os números estejam
  confirmados por pelo menos duas fontes confiáveis.
- Nunca publique informações incompletas.
- Se uma notícia não puder ser confirmada por pelo menos duas fontes confiáveis, descarte-a.
- Jamais reutilize notícias de dias anteriores.

REVISÃO FINAL (etapa obrigatória antes de responder)
Antes de entregar a resposta, revise todas as datas, números e horários. Verifique se todas as
informações pertencem ao dia atual. Caso encontre qualquer dado desatualizado ou não
verificável, descarte-o, faça uma nova busca, ou substitua por "Dado indisponível no momento."
Nunca publique conteúdo de dias anteriores.

REGRAS DE APRESENTAÇÃO (OBRIGATÓRIAS)
- Exiba apenas a resposta final.
- Nunca mostre o processo de busca.
- Nunca escreva frases como: "Vou buscar…", "Estou pesquisando…", "Agora vou consultar…",
  "Com todos os dados coletados…", "Após verificar…", "Pesquisando fontes…", "Segue abaixo…",
  "Aqui está…", ou qualquer variação parecida.
- Nunca explique como chegou às informações.
- Nunca exponha seu raciocínio interno.
- A resposta deve começar diretamente pelo título "PANORAMA | DD/MM/AAAA - HH:MM", sem nenhum
  texto antes dele.

PADRÃO VISUAL
- Visual limpo e profissional.
- Use emojis apenas nos títulos das seções: 🌍 MACRO, ⚡ ENERGIA, 🪙 METAIS, ₿ MERCADO CRIPTO,
  📰 MANCHETE DO DIA.
- Não utilize emojis em cada ativo individual (nem de bandeira, nem de moeda). Apenas indique a
  direção com 🟢 para alta ou 🔴 para queda, depois da variação percentual.
- Exemplo de formatação exata a seguir:

PANORAMA | DD/MM/AAAA - HH:MM

🌍 MACRO
S&P 500 (Futuros): 7.508 pts 🟢 +0,12%
Nasdaq (Futuros): 26.175 pts 🔴 -0,15%
Dólar (DXY): 100,74 🔴 -0,65%

⚡ ENERGIA
Brent: US$ 70,90 🔴 -2,00%
WTI: US$ 68,25 🔴 -0,48%
Gás Natural: US$ 3,18 🔴 -1,29%

🪙 METAIS
Ouro: US$ 4.110,29 🟢 +1,96%
Cobre: US$ 6,11 🔴 -1,33%

₿ MERCADO CRIPTO
BTC: US$ 61.499 🟢 +2,26%
ETH: US$ 1.692 🟢 +4,60%
SOL: US$ 80,71 🟢 +4,49%
XRP: US$ 1,09 🟢 +3,15%
HYPE: US$ 64,87 🟢 +4,00%
TRX: US$ 0,32 🟢 +0,14%

📰 MANCHETE DO DIA
[título em negrito]
[resumo de 4 a 8 linhas]

Responda apenas com o texto final do panorama, pronto para ser enviado, sem nenhum comentário
antes ou depois, e sem repetir o rótulo "Exemplo" ou qualquer marcação — apenas o conteúdo real.
"""


def get_panorama():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "ERRO: ANTHROPIC_API_KEY não configurada."

    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)
    data_hora = agora.strftime("%d/%m/%Y %H:%M")

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
            "system": PANORAMA_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Agora são {data_hora} (horário de Brasília), do dia {agora.strftime('%d/%m/%Y')}. "
                        "Gere o panorama diário completo seguindo exatamente as regras e a formatação "
                        "definidas, com dados buscados agora, em tempo real."
                    ),
                }
            ],
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        }
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_ANTHROPIC)
        r.raise_for_status()
        data = r.json()

        blocos = data.get("content", [])

        # Proteção extra: pega só os blocos de texto que vêm DEPOIS da última
        # busca na web, ignorando qualquer texto que a Claude tenha escrito
        # entre uma busca e outra (evita narrar o processo, tipo "vou buscar...").
        ultimo_indice_ferramenta = -1
        for i, bloco in enumerate(blocos):
            if bloco.get("type") in ("tool_use", "server_tool_use", "web_search_tool_result"):
                ultimo_indice_ferramenta = i

        blocos_finais = blocos[ultimo_indice_ferramenta + 1:]
        textos = [bloco["text"] for bloco in blocos_finais if bloco.get("type") == "text"]
        resultado = "\n".join(textos).strip()

        # Se por algum motivo não sobrou texto após o filtro, usa todos os blocos de texto
        # como último recurso (melhor mostrar algo do que travar o envio).
        if not resultado:
            todos_textos = [bloco["text"] for bloco in blocos if bloco.get("type") == "text"]
            resultado = "\n".join(todos_textos).strip()

        return resultado or "Dado indisponível no momento."
    except Exception as e:
        return f"Não foi possível gerar o panorama de hoje. Erro técnico: {e}"


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
    r = requests.post(url, data=payload, timeout=TIMEOUT_TELEGRAM)
    if not r.ok:
        print("Falha ao enviar para o Telegram:", r.text)
        sys.exit(1)
    print("Mensagem enviada com sucesso!")


if __name__ == "__main__":
    mensagem = get_panorama()
    print(mensagem)  # aparece nos logs do GitHub Actions, útil para debug
    enviar_telegram(mensagem)
