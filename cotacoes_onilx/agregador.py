"""
Agregador: roda todos os coletores e consolida o resultado.

Equivalente ao coletar_todos_dados() do kairos_ion/Ion.py, mas generico
(nao amarrado ao pipeline de relatorio diario) e com cache por coletor,
para uso interativo (dashboard aberto varias vezes ao dia).
"""
import logging
from datetime import datetime

from .cache import com_cache
from .coletores import binance, coingecko, defillama, farside, fear_greed, macro, mempool

logger = logging.getLogger(__name__)

# TTL por coletor. Cripto muda rapido; macro/on-chain mudam devagar.
_TTL_SEGUNDOS = {
    "coingecko": 90,
    "binance_derivativos": 90,
    "mempool_btc": 300,
    "fear_greed": 1800,
    "defillama": 1800,
    "farside_etf": 1800,
    "macro": 900,
}

_COLETORES = [
    ("coingecko", coingecko),
    ("mempool_btc", mempool),
    ("fear_greed", fear_greed),
    ("defillama", defillama),
    ("farside_etf", farside),
    ("binance_derivativos", binance),
    ("macro", macro),
]

# Aplica cache a cada modulo.coletar uma unica vez, na importacao.
_COLETAR_CACHEADO = {
    nome: com_cache(_TTL_SEGUNDOS[nome])(modulo.coletar)
    for nome, modulo in _COLETORES
}


def coletar_todas() -> dict:
    """
    Executa todos os coletores em sequencia. Falha de um nao quebra os outros.

    Estrutura de retorno identica ao coletar_todos_dados() do kairos_ion:
        {
            "timestamp_coleta": str,
            "dados": {"coingecko": {...} | None, ...},
            "status_coleta": {"coingecko": "ok" | "falhou", ...},
        }
    """
    timestamp = datetime.now().isoformat()
    logger.info(f"Iniciando coleta consolidada em {timestamp}")

    resultado = {
        "timestamp_coleta": timestamp,
        "dados": {},
        "status_coleta": {},
    }

    for nome, _ in _COLETORES:
        logger.info(f">>> Coletando: {nome}")
        try:
            dados = _COLETAR_CACHEADO[nome]()
        except Exception as e:
            logger.error(f"{nome}: excecao nao tratada — {e}", exc_info=True)
            dados = None
        resultado["dados"][nome] = dados
        resultado["status_coleta"][nome] = "ok" if dados is not None else "falhou"

    sucessos = sum(1 for s in resultado["status_coleta"].values() if s == "ok")
    total = len(_COLETORES)
    logger.info(f"Coleta concluida: {sucessos}/{total} fontes com sucesso")
    return resultado


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    print(json.dumps(coletar_todas(), indent=2, ensure_ascii=False, default=str))
