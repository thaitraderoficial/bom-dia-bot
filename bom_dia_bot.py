"""
Panorama Diário (ThaiTraderOficial) - resumo de mercado enviado automaticamente
para o Telegram, gerado com dados buscados em tempo real pela Claude.

Arquitetura: a Claude devolve os dados em JSON (só números e texto puro, nada de
formatação). O PYTHON monta o texto final e alinha as colunas de preço/variação
usando fonte monoespaçada (bloco de código do Telegram) — isso garante alinhamento
perfeito sempre, e também elimina qualquer risco de a IA "narrar o processo",
porque a resposta dela vira só um dado estruturado, sem espaço para comentários.

Variáveis de ambiente necessárias (Secrets no GitHub):
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- ANTHROPIC_API_KEY
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timezone, timedelta

TIMEOUT_TELEGRAM = 20
TIMEOUT_ANTHROPIC = 120

INDISPONIVEL = "Dado indisponível no momento."


PANORAMA_SYSTEM_PROMPT = """\
Você é o responsável por coletar os dados do PANORAMA DIÁRIO da ThaiTraderOficial.
Sua prioridade é precisão, objetividade e atualização em tempo real.

REGRAS OBRIGATÓRIAS
- Busque todos os dados em tempo real antes de responder, usando a ferramenta de busca na web.
- Nunca utilize informações em cache ou de dias anteriores.
- Nunca invente dados. Nunca complete informações por inferência.
- Se algum dado não puder ser confirmado, use exatamente a string "Dado indisponível no momento."
  nos campos "valor" e null no campo "variacao" daquele item.
- Utilize preferencialmente fontes confiáveis como Reuters, Bloomberg, CNBC, Wall Street Journal,
  Financial Times, TradingView, CoinGecko, CoinMarketCap, CME, Investing e fontes oficiais dos
  indicadores econômicos.
- Se existir um dado econômico importante divulgado no dia (Payroll, CPI, PPI, decisão de juros
  etc.), ele deve obrigatoriamente ser a manchete principal, desde que confirmado por pelo menos
  duas fontes confiáveis.
- Se uma notícia não puder ser confirmada por pelo menos duas fontes confiáveis, descarte-a e
  escolha a próxima mais relevante.
- Jamais reutilize notícias de dias anteriores.
- Antes de responder, revise todas as datas, números e horários: confirme que pertencem ao dia
  de hoje. Descarte e busque de novo qualquer dado desatualizado ou não verificável.

FORMATO DE RESPOSTA (OBRIGATÓRIO)
Responda SOMENTE com um objeto JSON válido, sem nenhum texto antes ou depois, sem bloco de
markdown (nada de ```json), sem comentário, sem explicação — só o JSON puro, pronto para ser
processado por um programa. Isso é uma chamada de dados, não uma conversa: nenhum campo do JSON
deve conter frases sobre o processo de busca, comentários, ou qualquer coisa além do dado puro
em si.

Use exatamente este formato:

{
  "cripto": [
    {"ticker": "BTC", "valor": "US$ 61.500", "variacao": "+3,19%"},
    {"ticker": "ETH", "valor": "US$ 1.694", "variacao": "+6,00%"},
    {"ticker": "SOL", "valor": "US$ 80,71", "variacao": "+4,49%"},
    {"ticker": "XRP", "valor": "US$ 1,09", "variacao": "+3,88%"},
    {"ticker": "HYPE", "valor": "US$ 65,30", "variacao": "+2,49%"},
    {"ticker": "TRX", "valor": "US$ 0,318", "variacao": "+0,28%"}
  ],
  "macro": [
    {"nome": "S&P 500 (Futuros)", "valor": "7.508 pts", "variacao": "+0,12%"},
    {"nome": "Nasdaq (Futuros)", "valor": "26.175 pts", "variacao": "-0,15%"},
    {"nome": "Dólar (DXY)", "valor": "100,74", "variacao": "-0,65%"}
  ],
  "energia": [
    {"nome": "Brent", "valor": "US$ 70,90", "variacao": "-2,00%"},
    {"nome": "WTI", "valor": "US$ 68,25", "variacao": "-0,48%"},
    {"nome": "Gás Natural", "valor": "US$ 3,18", "variacao": "-1,29%"}
  ],
  "metais": [
    {"nome": "Ouro", "valor": "US$ 4.110,29", "variacao": "+1,96%"},
    {"nome": "Cobre", "valor": "US$ 6,11", "variacao": "-1,33%"}
  ],
  "manchete_titulo": "Fed sinaliza pausa nos cortes de juros após dado de inflação acima do esperado",
  "manchete_paragrafos": [
    "O CPI de junho veio em 3,2% ao ano, acima da projeção de 3,0%. Isso reduz a probabilidade de um novo corte de juros na próxima reunião do FOMC.",
    "Com juros mais altos por mais tempo, o dólar tende a se fortalecer no curto prazo, pressionando ativos de risco globalmente.",
    "No mercado cripto, o movimento costuma gerar aversão a risco de curto prazo, com pressão vendedora em BTC e altcoins até a poeira baixar."
  ]
}

Regras sobre os campos:
- "valor": string só com o número/preço, sem emoji, sem seta, sem cor.
- "variacao": string com sinal (+ ou -) e "%", sem emoji, sem cor. Use null se indisponível.
- Se um dado estiver indisponível, use "valor": "Dado indisponível no momento." e "variacao": null
  para aquele item específico — não descarte o item da lista, mantenha o ticker/nome.
- "manchete_titulo": só o título, sem asteriscos, sem formatação.
- "manchete_paragrafos": uma lista de strings, cada string é UM parágrafo (o programa vai
  separar visualmente cada parágrafo com uma linha em branco). Divida por assunto: um parágrafo
  para o que aconteceu, outro para o impacto esperado, e se houver relação, um terceiro sobre o
  reflexo no mercado cripto. Cada parágrafo deve ser curto (1 a 3 frases).
- Se quiser citar uma frase literal de alguém (ex: um dirigente do Fed), inclua a citação dentro
  do parágrafo entre aspas normais — o programa vai aplicar o itálico automaticamente.
- Escolha a manchete priorizando nesta ordem: 1) dados macroeconômicos (Payroll, CPI, PPI, PIB,
  FOMC, Fed, BCE), 2) geopolítica relevante, 3) economia global, 4) fluxo institucional,
  5) mercado de criptomoedas.
"""


def chamar_claude_json(system_prompt, user_content, max_tokens):
    """Chama a API da Claude esperando um JSON puro como resposta."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }

    r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_ANTHROPIC)
    r.raise_for_status()
    data = r.json()

    blocos = data.get("content", [])

    # Pega só os blocos de texto que vêm DEPOIS da última busca na web
    # (ignora qualquer coisa que a Claude tenha escrito entre uma busca e outra).
    ultimo_indice_ferramenta = -1
    for i, bloco in enumerate(blocos):
        if bloco.get("type") in ("tool_use", "server_tool_use", "web_search_tool_result"):
            ultimo_indice_ferramenta = i

    blocos_finais = blocos[ultimo_indice_ferramenta + 1:]
    textos = [bloco["text"] for bloco in blocos_finais if bloco.get("type") == "text"]
    texto_resultado = "\n".join(textos).strip()

    if not texto_resultado:
        todos_textos = [bloco["text"] for bloco in blocos if bloco.get("type") == "text"]
        texto_resultado = "\n".join(todos_textos).strip()

    # Proteção extra: pega só o trecho entre a primeira "{" e a última "}",
    # caso sobre algum texto solto antes/depois do JSON.
    inicio = texto_resultado.find("{")
    fim = texto_resultado.rfind("}")
    if inicio == -1 or fim == -1:
        return None
    texto_json = texto_resultado[inicio:fim + 1]

    try:
        return json.loads(texto_json)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Montagem do texto final (feita 100% em Python, garante alinhamento perfeito)
# ---------------------------------------------------------------------------

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # símbolos, pictogramas, emojis diversos (inclui 🟢🔴)
    "\U00002600-\U000027BF"  # símbolos diversos e dingbats
    "\U0001F1E6-\U0001F1FF"  # bandeiras
    "\U00002190-\U000021FF"  # setas
    "\U00002B00-\U00002BFF"  # setas/símbolos extras
    "\uFE0F"                  # seletor de variação de emoji
    "]+",
    flags=re.UNICODE,
)


def remover_emojis(texto):
    if not texto:
        return texto
    return EMOJI_PATTERN.sub("", str(texto)).strip()


def formatar_tabela(itens, chave_nome):
    """Monta uma tabela alinhada (fonte monoespaçada) a partir de uma lista de
    dicts com chave_nome / "valor" / "variacao". Remove qualquer emoji que a IA
    tenha colocado por engano nos valores, garantindo que nunca apareça bolinha
    colorida nem nenhum outro símbolo."""
    if not itens:
        return INDISPONIVEL

    for i in itens:
        i["valor"] = remover_emojis(i.get("valor"))
        i["variacao"] = remover_emojis(i.get("variacao"))

    largura_nome = max(len(str(i.get(chave_nome, ""))) for i in itens)
    largura_valor = max(len(str(i.get("valor") or INDISPONIVEL)) for i in itens)

    linhas = []
    for i in itens:
        nome = str(i.get(chave_nome, "")).ljust(largura_nome)
        valor = i.get("valor") or INDISPONIVEL
        variacao = i.get("variacao")

        if not variacao or valor == INDISPONIVEL:
            linhas.append(f"{nome}  {valor}")
        else:
            valor_padded = str(valor).ljust(largura_valor)
            linhas.append(f"{nome}  {valor_padded}  {variacao}")

    return "\n".join(linhas)


def formatar_manchete(dados):
    titulo = dados.get("manchete_titulo") or ""
    paragrafos = dados.get("manchete_paragrafos") or []

    if not titulo or not paragrafos:
        return INDISPONIVEL

    # Aplica itálico em qualquer trecho entre aspas (citação literal)
    paragrafos_formatados = []
    for p in paragrafos:
        p_com_italico = re.sub(r'"([^"]+)"', r'_"\1"_', p)
        paragrafos_formatados.append(p_com_italico)

    corpo = "\n\n".join(paragrafos_formatados)
    return f"*{titulo}*\n\n{corpo}"


def montar_mensagem(dados):
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)
    data_hora = agora.strftime("%d/%m/%Y - %H:%M")

    partes = [
        f"*PANORAMA | {data_hora}*",
        "",
        "*₿ MERCADO CRIPTO*",
        f"```\n{formatar_tabela(dados.get('cripto', []), 'ticker')}\n```",
        "",
        "*🌍 MACRO*",
        f"```\n{formatar_tabela(dados.get('macro', []), 'nome')}\n```",
        "",
        "*⚡ ENERGIA*",
        f"```\n{formatar_tabela(dados.get('energia', []), 'nome')}\n```",
        "",
        "*🪙 METAIS*",
        f"```\n{formatar_tabela(dados.get('metais', []), 'nome')}\n```",
        "",
        "",
        "*📰 MANCHETE DO DIA*",
        formatar_manchete(dados),
    ]
    return "\n".join(partes)


def get_panorama():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "ERRO: ANTHROPIC_API_KEY não configurada."

    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)

    try:
        user_content = (
            f"Agora são {agora.strftime('%d/%m/%Y %H:%M')} (horário de Brasília). "
            "Busque os dados de hoje, em tempo real, e responda só com o JSON no formato definido."
        )
        dados = chamar_claude_json(PANORAMA_SYSTEM_PROMPT, user_content, max_tokens=2000)
        if not dados:
            return "Não foi possível gerar o panorama de hoje (resposta inválida da IA)."
        return montar_mensagem(dados)
    except Exception as e:
        return f"Não foi possível gerar o panorama de hoje. Erro técnico: {e}"


# ---------------------------------------------------------------------------
# Envio para o Telegram
# ---------------------------------------------------------------------------

def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_ids_raw:
        print("ERRO: defina as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        sys.exit(1)

    # Suporta um ou mais destinos, separados por vírgula. Cada destino pode ser:
    # - um canal/grupo normal: "@canalthaitrader" ou "-1001234567890"
    # - um TÓPICO dentro de um grupo com fórum ativado: "-1001234567890:45"
    #   (o número depois dos dois-pontos é o message_thread_id do tópico)
    # Exemplo combinando os dois: "@canalthaitrader,-1001234567890:45"
    destinos_raw = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    algum_sucesso = False
    for destino in destinos_raw:
        if ":" in destino:
            chat_id, thread_id = destino.split(":", 1)
            chat_id = chat_id.strip()
            thread_id = thread_id.strip()
        else:
            chat_id = destino
            thread_id = None

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if thread_id:
            payload["message_thread_id"] = thread_id

        r = requests.post(url, data=payload, timeout=TIMEOUT_TELEGRAM)
        if not r.ok:
            print(f"Falha ao enviar para {destino}:", r.text)
        else:
            print(f"Mensagem enviada com sucesso para {destino}!")
            algum_sucesso = True

    if not algum_sucesso:
        sys.exit(1)


if __name__ == "__main__":
    mensagem = get_panorama()
    print(mensagem)  # aparece nos logs do GitHub Actions, útil para debug
    enviar_telegram(mensagem)
