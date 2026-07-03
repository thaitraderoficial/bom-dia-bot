"""
Panorama Diário (ThaiTraderOficial) - resumo de mercado enviado automaticamente
para o Telegram, gerado com dados buscados em tempo real pela Claude.

Arquitetura: a Claude devolve os dados em JSON (só números e texto puro, nada de
formatação). O PYTHON monta o texto final e alinha as colunas de preço/variação
usando fonte monoespaçada (bloco de código do Telegram) — isso garante alinhamento
perfeito sempre, e também elimina qualquer risco de a IA "narrar o processo".

Para nunca repetir a manchete do dia anterior, o script lê/grava um arquivo
"ultima_manchete.json" dentro do próprio repositório (o workflow do GitHub Actions
faz commit desse arquivo depois de cada execução bem-sucedida).

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
ARQUIVO_ULTIMA_MANCHETE = "ultima_manchete.json"


PANORAMA_SYSTEM_PROMPT = """\
Você é responsável por coletar os dados do PANORAMA DIÁRIO da ThaiTraderOficial.
Seu objetivo é entregar dados para um resumo profissional, limpo, objetivo, confiável e
atualizado em tempo real.

REGRAS OBRIGATÓRIAS
- Busque TODOS os dados em tempo real antes de responder, usando a ferramenta de busca na web.
- Nunca utilize cache ou informações de dias anteriores.
- Nunca invente dados. Nunca complete informações por inferência.
- Caso algum dado não possa ser obtido, use exatamente a string "Dado indisponível no momento."
  no campo "valor" e null no campo "variacao" daquele item específico.
- Utilize preferencialmente fontes confiáveis como Reuters, Bloomberg, CNBC, Wall Street Journal,
  Financial Times, TradingView, CoinGecko, CoinMarketCap, CME, Investing e fontes oficiais dos
  indicadores econômicos.

FORMATO DE RESPOSTA (OBRIGATÓRIO)
Responda SOMENTE com um objeto JSON válido, sem nenhum texto antes ou depois, sem bloco de
markdown (nada de ```json), sem comentário, sem explicação — só o JSON puro. Isso é uma chamada
de dados, não uma conversa: nenhum campo deve conter frases sobre o processo de busca ("vou
buscar", "pesquisando", "com base em", "aqui está", "dados coletados", "estou analisando", etc.)
nem raciocínio — só o dado puro.

Use exatamente este formato:

{
  "cripto": [
    {"ticker": "BTC", "valor": "US$ 61.500", "variacao": "+3,19%"},
    {"ticker": "ETH", "valor": "US$ 1.694", "variacao": "-1,42%"},
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
    {"nome": "WTI", "valor": "US$ 68,25", "variacao": "+0,48%"},
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

REGRAS SOBRE OS CAMPOS
- "valor": string só com o número/preço, sem emoji, sem seta, sem cor, sem ponto ou caractere
  sobrando no final (ex: nunca "US$ 1,09." — o certo é "US$ 1,09").
- "variacao": string só com sinal (+ ou -) e "%", sem emoji, sem seta, sem cor. Use null se
  indisponível.
- "manchete_titulo": só o título, sem asteriscos, sem formatação.
- "manchete_paragrafos": lista de strings, cada uma é um parágrafo (o programa separa
  visualmente cada parágrafo com linha em branco). Divida por assunto: o que aconteceu, o
  impacto esperado, e (se houver relação) o reflexo no mercado cripto. Parágrafos curtos
  (1 a 3 frases cada). Se citar uma frase literal de alguém, coloque entre aspas normais no
  texto — o programa aplica o itálico automaticamente.

MANCHETE DO DIA — CRITÉRIO DE ESCOLHA
Escolha APENAS a notícia mais relevante das últimas 24 horas, nesta ordem de prioridade:
1. Payroll, 2. CPI, 3. PPI, 4. Decisão de juros, 5. FOMC, 6. Federal Reserve, 7. BCE, 8. PIB,
9. Outros dados macroeconômicos relevantes, 10. Geopolítica, 11. Fluxo institucional,
12. Mercado de criptomoedas.
O resumo (nos parágrafos) deve conter: o que aconteceu, por que aconteceu, qual o impacto
esperado, como isso afeta os mercados, e como isso pode impactar o mercado cripto (quando
houver relação). Escreva de forma objetiva, sem textos longos, sem copiar matérias, sem opinião.

REGRA FUNDAMENTAL — NUNCA REPETIR A MANCHETE ANTERIOR (SEM EXCEÇÃO)
{contexto_manchete_anterior}
Isso é uma regra absoluta, sem exceção: mesmo que o mesmo assunto continue sendo, na sua
avaliação, o mais relevante do mercado, você NÃO pode escrever sobre ele de novo enquanto ele
for a manchete anterior registrada. Desça na lista de prioridades e escolha a próxima notícia
mais relevante disponível (geopolítica, fluxo institucional, mercado de criptomoedas, ou
qualquer outro fato relevante das últimas 24 horas) — sempre existe algo diferente para
noticiar. Só volte a usar o mesmo assunto da manchete anterior se, e somente se, surgir uma
atualização NOVA e SIGNIFICATIVA sobre ele (ex: um dado que antes era só estimativa e agora
saiu confirmado, uma decisão que antes era esperada e agora foi anunciada) — nunca para repetir
a mesma informação já divulgada.

VALIDAÇÃO FINAL (antes de responder, confirme mentalmente)
- Todos os dados pertencem ao dia atual e estão atualizados.
- Nenhum dado foi inventado ou veio de cache.
- Nenhum campo contém frase sobre o processo de busca.
- A manchete NÃO é igual (nem quase igual) à do panorama anterior informado acima.
Se qualquer validação falhar, descarte e refaça a busca antes de responder.
"""


def montar_prompt_com_contexto(titulo_anterior, data_anterior):
    if titulo_anterior:
        contexto = (
            f'A manchete do panorama anterior (enviado em {data_anterior}) foi: '
            f'"{titulo_anterior}". É PROIBIDO usar esse mesmo assunto como manchete de hoje, '
            "sem exceção, a não ser que exista uma atualização nova e significativa sobre ele "
            "(não apenas repetir a mesma informação com outras palavras). Busque e escolha uma "
            "notícia diferente."
        )
    else:
        contexto = "Não há panorama anterior registrado — escolha livremente a manchete de hoje."
    return PANORAMA_SYSTEM_PROMPT.replace("{contexto_manchete_anterior}", contexto)


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
# Memória da última manchete (evita repetição no dia seguinte)
# ---------------------------------------------------------------------------

def ler_ultima_manchete():
    try:
        with open(ARQUIVO_ULTIMA_MANCHETE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados.get("titulo"), dados.get("data")
    except (FileNotFoundError, json.JSONDecodeError):
        return None, None


def salvar_ultima_manchete(titulo):
    fuso_br = timezone(timedelta(hours=-3))
    hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
    try:
        with open(ARQUIVO_ULTIMA_MANCHETE, "w", encoding="utf-8") as f:
            json.dump({"titulo": titulo, "data": hoje}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Aviso: não foi possível salvar a última manchete:", e)


# ---------------------------------------------------------------------------
# Montagem do texto final (feita 100% em Python, garante alinhamento perfeito)
# ---------------------------------------------------------------------------

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)


def limpar_valor(texto):
    """Remove emoji e qualquer pontuação sobrando no final (ex: 'US$ 1,09.' -> 'US$ 1,09')."""
    if not texto:
        return texto
    texto = EMOJI_PATTERN.sub("", str(texto)).strip()
    texto = re.sub(r"[.:]+$", "", texto).strip()
    return texto


def formatar_tabela(itens, chave_nome):
    if not itens:
        return INDISPONIVEL

    for i in itens:
        i["valor"] = limpar_valor(i.get("valor"))
        i["variacao"] = limpar_valor(i.get("variacao"))
        i[chave_nome] = limpar_valor(i.get(chave_nome))

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
        return INDISPONIVEL, None

    paragrafos_formatados = []
    for p in paragrafos:
        p_com_italico = re.sub(r'"([^"]+)"', r'_"\1"_', p)
        paragrafos_formatados.append(p_com_italico)

    corpo = "\n\n".join(paragrafos_formatados)
    return f"*{titulo}*\n\n{corpo}", titulo


def montar_mensagem(dados):
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)
    data_str = agora.strftime("%d/%m/%Y")
    hora_str = agora.strftime("%H:%M")

    texto_manchete, titulo_manchete = formatar_manchete(dados)

    partes = [
        f"*PANORAMA | {data_str} • {hora_str}*",
        "",
        "₿ *MERCADO CRIPTO*",
        f"```\n{formatar_tabela(dados.get('cripto', []), 'ticker')}\n```",
        "",
        "🌍 *MACRO*",
        f"```\n{formatar_tabela(dados.get('macro', []), 'nome')}\n```",
        "",
        "⚡ *PETRÓLEO E ENERGIA*",
        f"```\n{formatar_tabela(dados.get('energia', []), 'nome')}\n```",
        "",
        "🪙 *METAIS*",
        f"```\n{formatar_tabela(dados.get('metais', []), 'nome')}\n```",
        "",
        "",
        "📰 *MANCHETE DO DIA*",
        texto_manchete,
    ]
    return "\n".join(partes), titulo_manchete


def gerar_panorama():
    """Retorna (mensagem_pronta_para_telegram, titulo_da_manchete_ou_None)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "ERRO: ANTHROPIC_API_KEY não configurada.", None

    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)

    titulo_anterior, data_anterior = ler_ultima_manchete()
    prompt_final = montar_prompt_com_contexto(titulo_anterior, data_anterior)

    try:
        user_content = (
            f"Agora são {agora.strftime('%d/%m/%Y %H:%M')} (horário de Brasília). "
            "Busque os dados de hoje, em tempo real, e responda só com o JSON no formato definido."
        )
        dados = chamar_claude_json(prompt_final, user_content, max_tokens=2000)
        if not dados:
            return "Não foi possível gerar o panorama de hoje (resposta inválida da IA).", None
        return montar_mensagem(dados)
    except Exception as e:
        return f"Não foi possível gerar o panorama de hoje. Erro técnico: {e}", None


# ---------------------------------------------------------------------------
# Envio para o Telegram
# ---------------------------------------------------------------------------

def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_ids_raw:
        print("ERRO: defina as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        sys.exit(1)

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
    mensagem, titulo_manchete = gerar_panorama()
    print(mensagem)  # aparece nos logs do GitHub Actions, útil para debug
    enviar_telegram(mensagem)

    if titulo_manchete:
        salvar_ultima_manchete(titulo_manchete)
