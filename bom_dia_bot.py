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
import re
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
- Utilize preferencialmente fontes confiáveis como Reuters, Bloomberg, CNBC, Wall Street Journal,
  Financial Times, TradingView, CoinGecko, CoinMarketCap, CME, Investing e fontes oficiais dos
  indicadores econômicos.

REGRAS DE APRESENTAÇÃO (OBRIGATÓRIAS — LEIA COM MÁXIMA ATENÇÃO)
Sua resposta será copiada e colada, palavra por palavra, direto para um canal público com
milhares de leitores. Qualquer frase que não seja um dado de mercado ou o texto da manchete
quebra a credibilidade do canal. Isso vale para QUALQUER parte da resposta: início, meio ou fim.
- Exiba apenas a resposta final. Nunca mostre o processo de busca, nunca comente sobre as fontes
  que usou, nunca resuma o que fez, nunca narre o que está fazendo.
- PROIBIDO usar, em qualquer parte da resposta, frases como:
  "Vou buscar…", "Estou pesquisando…", "Agora vou consultar…", "Com todos os dados coletados…",
  "Após verificar…", "Pesquisando fontes…", "Segue abaixo…", "Aqui está…", "Segue o panorama…",
  "Dados verificados em múltiplas fontes confiáveis…", "Com base nas informações verificadas…",
  "Todos os dados foram confirmados…", "Segundo a IA…", ou qualquer frase que mencione o ato de
  verificar, buscar, confirmar, pesquisar ou coletar informação — mesmo de forma indireta.
- Nunca explique como chegou às informações. Nunca exponha seu raciocínio interno. Nunca faça um
  comentário de abertura ou de fechamento sobre o processo (ex: "esses foram os dados de hoje").
- A resposta deve começar diretamente pelo título "*PANORAMA | DD/MM/AAAA - HH:MM*" e terminar
  diretamente no último caractere do resumo da manchete — sem nenhuma linha de abertura ou
  fechamento além disso.
- Antes de responder, releia mentalmente o texto que você vai entregar e remova qualquer frase
  que descreva o que você fez, mesmo que pareça inofensiva.

FORMATAÇÃO (siga exatamente esta estrutura — é a formatação Markdown do Telegram)
- O título do topo vai em negrito: *PANORAMA | DD/MM/AAAA - HH:MM*
- Os títulos de cada seção vão em negrito: *₿ MERCADO CRIPTO*, *🌍 MACRO*, *⚡ ENERGIA*,
  *🪙 METAIS*, *📰 MANCHETE DO DIA*.
- Use emojis apenas nesses títulos de seção, nunca em cada ativo individual. Para cada ativo,
  indique só a direção com 🟢 (alta) ou 🔴 (queda) depois da variação percentual.
- Entre a maioria das seções, deixe UMA linha em branco. Mas entre a seção de METAIS e a seção
  de MANCHETE DO DIA, deixe DUAS linhas em branco — a manchete é uma notícia, não um dado de
  cotação, e merece uma separação visual maior do resto.
- A ordem das seções é sempre: MERCADO CRIPTO primeiro, depois MACRO, ENERGIA, METAIS e por
  último MANCHETE DO DIA.

SEÇÃO MERCADO CRIPTO
Para cada ativo (BTC, ETH, SOL, XRP, HYPE, TRX), mostre preço atual e variação nas últimas 24h,
com 🟢 ou 🔴 conforme a direção.

SEÇÃO MANCHETE DO DIA
Escolha apenas o acontecimento mais importante das últimas 24 horas, priorizando nesta ordem:
1. Dados macroeconômicos (Payroll, CPI, PPI, PIB, FOMC, Fed, BCE, etc.)
2. Geopolítica relevante
3. Economia global
4. Fluxo institucional
5. Mercado de criptomoedas
Escreva um título em negrito (com asteriscos), depois um resumo entre 4 e 8 linhas.
- NUNCA escreva o resumo como um bloco de texto corrido. Divida em parágrafos curtos (1 a 3
  linhas cada), com uma linha em branco entre eles, toda vez que o assunto mudar dentro do
  resumo — por exemplo: um parágrafo sobre o que aconteceu, linha em branco, outro parágrafo
  sobre o impacto esperado (ex: no dólar, nos juros), linha em branco, e se houver relação, um
  último parágrafo curto sobre o reflexo no mercado cripto.
- Se for citar uma frase literal de alguém (ex: um dirigente do Fed, um comunicado oficial),
  coloque a citação em itálico, usando um único sublinhado de cada lado, assim: _"texto citado
  aqui"_. Use isso só quando houver uma citação real e relevante — não force citações.
- Texto técnico, direto, fácil de entender, frases curtas, sem repetir informação, sem copiar
  matérias integralmente.

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
Nunca publique conteúdo de dias anteriores. Revise também se não sobrou nenhuma frase sobre o
processo de busca (releia as REGRAS DE APRESENTAÇÃO acima antes de finalizar).

EXEMPLO DE FORMATAÇÃO EXATA A SEGUIR (não copie os números, são só ilustrativos):

*PANORAMA | DD/MM/AAAA - HH:MM*

*₿ MERCADO CRIPTO*
BTC: US$ 61.499 🟢 +2,26%
ETH: US$ 1.692 🟢 +4,60%
SOL: US$ 80,71 🟢 +4,49%
XRP: US$ 1,09 🟢 +3,15%
HYPE: US$ 64,87 🟢 +4,00%
TRX: US$ 0,32 🟢 +0,14%

*🌍 MACRO*
S&P 500 (Futuros): 7.508 pts 🟢 +0,12%
Nasdaq (Futuros): 26.175 pts 🔴 -0,15%
Dólar (DXY): 100,74 🔴 -0,65%

*⚡ ENERGIA*
Brent: US$ 70,90 🔴 -2,00%
WTI: US$ 68,25 🔴 -0,48%
Gás Natural: US$ 3,18 🔴 -1,29%

*🪙 METAIS*
Ouro: US$ 4.110,29 🟢 +1,96%
Cobre: US$ 6,11 🔴 -1,33%


*📰 MANCHETE DO DIA*
*Fed sinaliza pausa nos cortes de juros após dado de inflação acima do esperado*

O CPI de junho veio em 3,2% ao ano, acima da projeção de 3,0%. Isso reduz a probabilidade de
um novo corte de juros na próxima reunião do FOMC.

Em comunicado, um dos dirigentes do Fed afirmou que _"ainda é cedo para declarar vitória contra
a inflação"_.

Com juros mais altos por mais tempo, o dólar tende a se fortalecer no curto prazo, pressionando
ativos de risco globalmente.

No mercado cripto, o movimento costuma gerar aversão a risco de curto prazo, com pressão vendedora
em BTC e altcoins até a poeira baixar.

Responda apenas com o texto final do panorama, pronto para ser enviado, sem nenhum comentário
antes ou depois, e sem repetir o rótulo "Exemplo" ou qualquer marcação — apenas o conteúdo real.
"""


def chamar_claude(system_prompt, user_content, max_tokens, usar_busca_web=True):
    """Chama a API da Claude e devolve só o texto final (sem narrar o processo de busca)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

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
    }
    if usar_busca_web:
        payload["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

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

    if not resultado:
        todos_textos = [bloco["text"] for bloco in blocos if bloco.get("type") == "text"]
        resultado = "\n".join(todos_textos).strip()

    return resultado


def limpar_resposta(texto):
    """Proteção final, no código (não depende da Claude obedecer o prompt):
    - Corta tudo que vier ANTES do título real "PANORAMA | data", identificado pelo
      padrão "PANORAMA" seguido de "|" — não corta em qualquer menção solta da
      palavra "panorama" (ex: dentro de uma frase de narração tipo "aqui está o
      panorama completo"), só no título formatado de verdade.
    - Remove parágrafos curtos que pareçam comentário sobre o processo de busca,
      mesmo que apareçam no meio ou no fim do texto.
    """
    if not texto:
        return texto

    match_titulo = re.search(r"\*?PANORAMA\s*\|", texto, re.IGNORECASE)
    if match_titulo:
        texto = texto[match_titulo.start():]

    frases_proibidas = [
        "busquei", "coletei", "puxei", "verifiquei", "pesquisei", "consultei",
        "com todos os dados", "todas as informações necessárias",
        "informações verificadas", "segue o panorama", "segue abaixo",
        "aqui está", "aqui estão", "dados coletados", "dados verificados",
        "espero que", "qualquer dúvida", "fico à disposição", "segundo a ia",
        "com base nas informações", "com base em", "várias fontes",
        "diversas fontes", "múltiplas fontes", "panorama completo",
    ]

    paragrafos = texto.split("\n\n")
    limpos = []
    for i, p in enumerate(paragrafos):
        p_normalizado = p.strip().lower()
        eh_curto = len(p_normalizado) < 200
        # Nunca descarta o primeiro parágrafo (é o título real, já garantido acima)
        tem_frase_proibida = any(f in p_normalizado for f in frases_proibidas)
        if i > 0 and eh_curto and tem_frase_proibida:
            continue  # descarta esse parágrafo de narração
        limpos.append(p)

    return "\n\n".join(limpos).strip()


def get_panorama():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "ERRO: ANTHROPIC_API_KEY não configurada."

    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)
    data_hora = agora.strftime("%d/%m/%Y %H:%M")

    try:
        user_content = (
            f"Agora são {data_hora} (horário de Brasília), do dia {agora.strftime('%d/%m/%Y')}. "
            "Gere o panorama diário completo seguindo exatamente as regras e a formatação "
            "definidas, com dados buscados agora, em tempo real."
        )
        resultado = chamar_claude(PANORAMA_SYSTEM_PROMPT, user_content, max_tokens=2000)
        resultado = limpar_resposta(resultado)
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
