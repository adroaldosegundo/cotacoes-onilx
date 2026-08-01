"""
Coletor Farside Investors: fluxo liquido consolidado de ETFs spot
de BTC e ETH (em milhoes de USD), referente ao ultimo dia util
americano com dado consolidado.

Fonte: farside.co.uk (paginas HTML publicas com tabelas de fluxo).
Sem autenticacao.

VERSAO 4 (2026-05-08): seleção de "último dia consolidado", não "última linha".

Mudanças em relação a v3:
- Ignora a linha do dia em curso quando a coleta acontece antes da
  janela de consolidação da Farside (default: 22h ET = pregão fechado
  às 17h ET + folga de 5h para a Farside agregar os reports).
- Adiciona campos de transparência no retorno (dias_defasagem, status, nota)
  para que o prompt do gerador trate o dado sem ambiguidade.
- Retorno padronizado: nunca retorna None silencioso para um ativo;
  sempre retorna um dict com status="ok" ou status="indisponivel".

Mudanças em relação a v2 (mantidas):
- _flatten_columns desce pelos níveis do MultiIndex pegando o primeiro
  nome significativo. Resolve caso ETH com footnote criando 3º nível.

Dependencias:
    pip install pandas lxml requests
"""
import io
import logging
import time
from datetime import datetime, date, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo

import pandas as pd
import requests

logger = logging.getLogger(__name__)

URL_BTC = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
URL_ETH = "https://farside.co.uk/ethereum-etf-flow-all-data/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

HTTP_TIMEOUT = 20

FORMATOS_DATA = [
    "%d %b %Y",
    "%d-%b-%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
]

# Janela de consolidação: hora ET a partir da qual o dado do dia em curso
# é considerado confiável. Pregão fecha às 17h ET; Farside leva algumas
# horas para agregar reports individuais. 22h ET é margem prudente.
HORA_CONSOLIDACAO_ET = 22

TZ_ET = ZoneInfo("America/New_York")


def _baixar_html(url: str, label: str) -> Optional[str]:
    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(
                f"Farside [{label}]: falha HTTP em {url} "
                f"(tentativa {tentativa}/{max_tentativas}) - {e}"
            )
            if tentativa < max_tentativas:
                time.sleep(10 * tentativa)

    logger.error(f"Farside [{label}]: falha HTTP em {url} apos {max_tentativas} tentativas")
    return None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        novas = []
        for col in df.columns:
            if isinstance(col, tuple):
                escolhido = None
                for nivel in reversed(col):
                    s = str(nivel).strip()
                    if s and not s.startswith("Unnamed:"):
                        escolhido = s
                        break
                novas.append(escolhido if escolhido else str(col[-1]))
            else:
                novas.append(str(col))
        df.columns = novas
    return df


def _parse_datas(serie: pd.Series) -> pd.Series:
    melhor = None
    melhor_validas = -1
    for fmt in FORMATOS_DATA:
        parsed = pd.to_datetime(serie, format=fmt, errors="coerce")
        validas = parsed.notna().sum()
        if validas > melhor_validas:
            melhor = parsed
            melhor_validas = validas
    if melhor_validas == 0:
        melhor = pd.to_datetime(serie, errors="coerce", dayfirst=True)
    return melhor


def _selecionar_tabela_de_datas(
    tabelas: List[pd.DataFrame], label: str
) -> Optional[pd.DataFrame]:
    for idx, df in enumerate(tabelas):
        df_flat = _flatten_columns(df)
        if df_flat.empty or len(df_flat.columns) < 2:
            continue
        primeira_col = df_flat.iloc[:, 0]
        parsed = _parse_datas(primeira_col)
        ratio = parsed.notna().mean() if len(parsed) else 0
        if ratio > 0.5:
            df_flat["_data_parsed"] = parsed
            logger.debug(
                f"Farside [{label}]: tabela #{idx} selecionada "
                f"({ratio:.0%} de datas validas, {len(df_flat)} linhas)"
            )
            return df_flat
    return None


def _parse_valor_fluxo(raw) -> Optional[float]:
    s = str(raw).strip().replace(",", "")
    s = s.replace("(", "-").replace(")", "")
    if s in ("-", "", "nan", "NaN", "None"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def _identificar_coluna_total(df: pd.DataFrame, label: str) -> str:
    if "Total" in df.columns:
        return "Total"
    candidatas = [c for c in df.columns if "total" in str(c).lower()]
    if candidatas:
        return candidatas[0]
    cols_num = [c for c in df.columns if c != "_data_parsed"]
    fallback = cols_num[-1]
    logger.warning(
        f"Farside [{label}]: coluna 'Total' nao encontrada, "
        f"usando fallback '{fallback}'"
    )
    return fallback


def _hoje_em_et() -> date:
    """Data corrente no calendário americano (fuso ET)."""
    return datetime.now(TZ_ET).date()


def _consolidacao_em_andamento() -> bool:
    """
    True se o horário atual em ET for ANTES da janela de consolidação.
    Nesse caso, a linha do "hoje ET" deve ser ignorada (dado em formação).
    """
    return datetime.now(TZ_ET).hour < HORA_CONSOLIDACAO_ET


def _selecionar_linha_consolidada(
    df: pd.DataFrame, label: str
) -> Optional[pd.Series]:
    """
    Da tabela ordenada por data desc, escolhe a primeira linha cuja data
    NÃO seja "hoje em ET" se ainda estivermos antes da janela de consolidação.

    Se já estivermos pós-consolidação, aceita a linha de hoje normalmente.
    """
    df = df[df["_data_parsed"].notna()].copy()
    df = df.sort_values("_data_parsed", ascending=False)

    if df.empty:
        logger.warning(f"Farside [{label}]: dataframe vazio apos filtro de data")
        return None

    if _consolidacao_em_andamento():
        hoje_et = _hoje_em_et()
        df_filtrado = df[df["_data_parsed"].dt.date < hoje_et]
        if df_filtrado.empty:
            logger.warning(
                f"Farside [{label}]: todas as linhas são >= hoje ET ({hoje_et}). "
                "Sem dado consolidado disponível."
            )
            return None
        return df_filtrado.iloc[0]

    return df.iloc[0]


def _construir_nota(data_ref: date, dias_defasagem: int) -> str:
    data_fmt = data_ref.strftime("%d/%m/%Y")
    if dias_defasagem == 0:
        return f"Fluxo do pregão de {data_fmt} (último pregão consolidado)."
    if dias_defasagem == 1:
        return (
            f"Fluxo do pregão de {data_fmt} (último pregão consolidado, "
            "ainda dentro da janela esperada para coleta matinal no Brasil)."
        )
    return (
        f"Fluxo do pregão de {data_fmt}, último dia útil com dado consolidado "
        f"pela Farside (defasagem de {dias_defasagem} dias em relação à coleta — "
        "pode indicar feriado, fim de semana prolongado ou atraso na fonte)."
    )


def _extrair_ultimo_fluxo(url: str, label: str) -> dict:
    """
    Retorna sempre um dict, com status='ok' ou status='indisponivel'.
    """
    html = _baixar_html(url, label)
    if html is None:
        return _resposta_indisponivel(
            "Falha de conexão com a Farside. Sem dados de fluxo nesta leitura."
        )

    try:
        tabelas = pd.read_html(io.StringIO(html))
    except (ValueError, Exception) as e:
        logger.error(f"Farside [{label}]: erro ao processar HTML - {e}")
        return _resposta_indisponivel(
            "HTML da Farside não pôde ser processado nesta leitura."
        )

    if not tabelas:
        return _resposta_indisponivel(
            "Página da Farside retornou sem tabelas reconhecíveis."
        )

    df = _selecionar_tabela_de_datas(tabelas, label)
    if df is None:
        return _resposta_indisponivel(
            "Nenhuma tabela com coluna de datas encontrada na Farside."
        )

    linha = _selecionar_linha_consolidada(df, label)
    if linha is None:
        return _resposta_indisponivel(
            "A Farside não publicou ainda nenhum pregão consolidado disponível "
            "para esta leitura."
        )

    coluna_total = _identificar_coluna_total(df, label)
    fluxo = _parse_valor_fluxo(linha[coluna_total])
    if fluxo is None:
        logger.error(
            f"Farside [{label}]: parsing do valor falhou em "
            f"{linha['_data_parsed']} ('{linha[coluna_total]}')"
        )
        return _resposta_indisponivel(
            "Valor de fluxo no formato inesperado, parsing falhou."
        )

    data_ref: date = linha["_data_parsed"].date()
    hoje_et = _hoje_em_et()
    dias_defasagem = (hoje_et - data_ref).days
    nota = _construir_nota(data_ref, dias_defasagem)

    logger.info(
        f"Farside [{label}]: fluxo={fluxo:.1f}M USD, "
        f"ref={data_ref.isoformat()}, defasagem={dias_defasagem}d"
    )

    return {
        "data_referencia": data_ref.isoformat(),
        "fluxo_liquido_milhoes_usd": fluxo,
        "dias_defasagem": dias_defasagem,
        "status": "ok",
        "nota": nota,
    }


def _resposta_indisponivel(motivo: str) -> dict:
    """Resposta padronizada para falha — preserva contrato com o prompt."""
    return {
        "data_referencia": None,
        "fluxo_liquido_milhoes_usd": None,
        "dias_defasagem": None,
        "status": "indisponivel",
        "nota": motivo,
    }


def coletar() -> dict:
    """
    Coleta ETF flows consolidados de BTC e ETH no ultimo dia util americano.

    Retorno (sempre dict, nunca None):
        {
            "btc": {"data_referencia": ..., "fluxo_liquido_milhoes_usd": ...,
                    "dias_defasagem": ..., "status": "ok"|"indisponivel",
                    "nota": "..."},
            "eth": {idem},
        }

    O orquestrador deve registrar status="ok" se ao menos um ativo retornou
    com sucesso. O prompt do gerador sabe tratar status="indisponivel".
    """
    btc = _extrair_ultimo_fluxo(URL_BTC, "BTC")
    eth = _extrair_ultimo_fluxo(URL_ETH, "ETH")

    logger.info(
        f"Farside: BTC status={btc['status']}, ETH status={eth['status']}"
    )
    return {"btc": btc, "eth": eth}


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
