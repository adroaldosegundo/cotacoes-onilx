"""
Coletor macro: indice dolar (DXY) e yield do Treasury americano de 10 anos.

Fonte: Yahoo Finance via biblioteca yfinance.

DXY e Treasury 10y sao os dois indicadores mais relevantes para
contextualizar movimentos de cripto em relacao ao macro tradicional.
DXY mede a forca do dolar contra cesta de moedas; Treasury 10y reflete
o custo de capital de longo prazo na maior economia.

Tickers usados:
- DXY: "DX-Y.NYB"
- Treasury 10y yield: "^TNX"

Atencao ao Treasury 10y:
O ticker ^TNX no Yahoo retorna o yield ja em percentual decimal
(ex: 4.35 representa 4.35%). Confirmar isso na primeira execucao real,
porque historicamente houve casos do valor vir multiplicado por 10.

Dependencias adicionais:
    pip install yfinance
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _coletar_ticker(ticker: str, label: str) -> Optional[dict]:
    """
    Coleta cotacao mais recente e variacao 24h de um ticker.

    Retorna:
        {
            "valor": float,           # cotacao atual
            "valor_anterior": float,  # cotacao do dia anterior
            "var_pct": float,         # variacao percentual
        }
    ou None em caso de falha.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error(
            "Macro: pacote yfinance nao instalado. "
            "Rode: pip install yfinance"
        )
        return None

    try:
        # Pegamos 5 dias de historico para garantir pelo menos 2 dias uteis
        # (cobre fins de semana e feriados americanos).
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
    except Exception as e:
        logger.error(f"Macro [{label}]: falha ao buscar historico - {e}")
        return None

    if hist is None or hist.empty or len(hist) < 2:
        logger.warning(
            f"Macro [{label}]: historico insuficiente "
            f"({len(hist) if hist is not None else 0} linhas)"
        )
        return None

    try:
        atual = float(hist["Close"].iloc[-1])
        anterior = float(hist["Close"].iloc[-2])
        if anterior == 0:
            logger.warning(f"Macro [{label}]: valor anterior zero, var indefinida")
            var_pct = None
        else:
            var_pct = ((atual - anterior) / anterior) * 100
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Macro [{label}]: erro ao processar historico - {e}")
        return None

    return {
        "valor": atual,
        "valor_anterior": anterior,
        "var_pct": var_pct,
    }


def coletar() -> Optional[dict]:
    """
    Coleta DXY (indice dolar) e Treasury 10y.

    Estrutura de retorno:
        {
            "dxy": {
                "valor": 104.50,
                "valor_anterior": 104.20,
                "var_pct": 0.29,
            },
            "treasury_10y": {
                "valor": 4.35,            # yield em percentual
                "valor_anterior": 4.32,
                "var_pct": 0.69,
            },
        }

    Cada chave pode ser None individualmente. Retorna None apenas
    se ambos falharem.
    """
    dxy   = _coletar_ticker("DX-Y.NYB", "DXY")
    t10y  = _coletar_ticker("^TNX", "Treasury10y")
    usdbrl = _coletar_ticker("USDBRL=X", "USD/BRL")

    if dxy is None and t10y is None and usdbrl is None:
        return None

    logger.info(
        f"Macro: DXY={dxy is not None}, Treasury10y={t10y is not None}, USDBRL={usdbrl is not None}"
    )

    return {
        "dxy": dxy,
        "treasury_10y": t10y,
        "usdbrl": usdbrl,
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
