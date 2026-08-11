"""
Agregador: roda todos os coletores e consolida o resultado.

Equivalente ao coletar_todos_dados() do kairos_ion/Ion.py, mas generico
(nao amarrado ao pipeline de relatorio diario) e com cache por coletor,
para uso interativo (dashboard aberto varias vezes ao dia).

Coletores rodam em paralelo (thread por coletor) -- sao 7 chamadas de
rede independentes, sem dependencia entre si; rodar em sequencia soma os
tempos de todos (medido: ~17s com tudo ok, ate ~45s com CoinGecko
rate-limited fazendo retry), enquanto em paralelo o tempo total fica perto
do coletor mais lento sozinho. Falha de um nao afeta os outros nos dois
modos.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Sequence

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


def _coletar_um(nome: str):
    logger.info(f">>> Coletando: {nome}")
    try:
        return _COLETAR_CACHEADO[nome]()
    except Exception as e:
        logger.error(f"{nome}: excecao nao tratada — {e}", exc_info=True)
        return None


def coletar_todas(apenas: Optional[Sequence[str]] = None) -> dict:
    """
    Executa os coletores em paralelo. Falha de um nao quebra os outros.

    `apenas`: nomes dos coletores a rodar (subconjunto de _COLETORES). Default
    None roda os 7 -- o pipeline diario do Kairos ION usa todos. Consumidores
    interativos que so leem 1-2 fontes (ex.: Carteira OnilX so usa `coingecko`
    e `macro`, nunca mempool/fear_greed/defillama/farside/binance) devem
    restringir aqui: cada coletor a mais e uma chamada de rede que ninguem
    vai ler, pagando latencia (e risco de rate limit) por nada.

    Estrutura de retorno identica ao coletar_todos_dados() do kairos_ion:
        {
            "timestamp_coleta": str,
            "dados": {"coingecko": {...} | None, ...},
            "status_coleta": {"coingecko": "ok" | "falhou", ...},
        }
    (com apenas os coletores pedidos, quando `apenas` e informado)
    """
    coletores = _COLETORES if apenas is None else [
        (nome, modulo) for nome, modulo in _COLETORES if nome in apenas
    ]

    timestamp = datetime.now().isoformat()
    logger.info(f"Iniciando coleta consolidada em {timestamp} ({len(coletores)} fontes)")

    resultado = {
        "timestamp_coleta": timestamp,
        "dados": {},
        "status_coleta": {},
    }

    if not coletores:
        return resultado

    with ThreadPoolExecutor(max_workers=len(coletores)) as executor:
        futuros = {executor.submit(_coletar_um, nome): nome for nome, _ in coletores}
        for futuro in futuros:
            nome = futuros[futuro]
            dados = futuro.result()
            resultado["dados"][nome] = dados
            resultado["status_coleta"][nome] = "ok" if dados is not None else "falhou"

    sucessos = sum(1 for s in resultado["status_coleta"].values() if s == "ok")
    total = len(coletores)
    logger.info(f"Coleta concluida: {sucessos}/{total} fontes com sucesso")
    return resultado


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    print(json.dumps(coletar_todas(), indent=2, ensure_ascii=False, default=str))
