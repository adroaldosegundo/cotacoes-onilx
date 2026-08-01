"""
Coletor Fear & Greed Index: indice de sentimento do mercado cripto.

Fonte: alternative.me (API publica, sem autenticacao).

O indice varia de 0 a 100:
    0-24:  Extreme Fear
    25-49: Fear
    50-54: Neutral
    55-74: Greed
    75-100: Extreme Greed

Coletamos o valor atual e calculamos a variacao em relacao a 7 dias atras
para mostrar a tendencia de sentimento.

Documentacao: https://alternative.me/crypto/fear-and-greed-index/
"""
import logging
import time
from typing import Optional

import requests

from ..config import HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://api.alternative.me/fng/"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def coletar() -> Optional[dict]:
    """
    Coleta valor atual do Fear & Greed Index e variacao 7d.

    Estrutura de retorno:
        {
            "valor_atual": int,            # 0-100
            "classificacao": str,          # "Fear", "Greed", etc.
            "valor_7d_atras": int,
            "variacao_7d": int,            # diferenca em pontos (atual - 7d)
            "data_referencia": str,        # YYYY-MM-DD
        }
    """
    max_tentativas = 3
    dados = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            # Pegamos 8 dias para garantir que o oitavo seja exatamente 7 dias atras
            resp = requests.get(
                BASE_URL,
                params={"limit": 8},
                headers=HEADERS,
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            dados = resp.json()
            break
        except (requests.RequestException, ValueError) as e:
            logger.warning(
                f"Fear & Greed: falha "
                f"(tentativa {tentativa}/{max_tentativas}) - {e}"
            )
            if tentativa < max_tentativas:
                time.sleep(10 * tentativa)

    if dados is None:
        logger.error(f"Fear & Greed: falha apos {max_tentativas} tentativas")
        return None

    serie = dados.get("data", [])
    if not serie:
        logger.error("Fear & Greed: serie vazia na resposta")
        return None

    try:
        # API retorna do mais recente para o mais antigo
        atual = serie[0]
        valor_atual = int(atual.get("value", 0))
        classificacao = atual.get("value_classification", "Unknown")

        # Timestamp em segundos Unix; convertemos para data
        from datetime import datetime, timezone
        timestamp = int(atual.get("timestamp", 0))
        data_referencia = datetime.fromtimestamp(
            timestamp, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        # Valor de 7 dias atras: indice 7 da lista (se houver)
        valor_7d_atras = None
        variacao_7d = None
        if len(serie) >= 8:
            valor_7d_atras = int(serie[7].get("value", 0))
            variacao_7d = valor_atual - valor_7d_atras
        elif len(serie) >= 2:
            # Fallback: usa o mais antigo disponivel
            valor_7d_atras = int(serie[-1].get("value", 0))
            variacao_7d = valor_atual - valor_7d_atras

        logger.info(
            f"Fear & Greed: {valor_atual} ({classificacao}), "
            f"variacao 7d: {variacao_7d}"
        )

        return {
            "valor_atual": valor_atual,
            "classificacao": classificacao,
            "valor_7d_atras": valor_7d_atras,
            "variacao_7d": variacao_7d,
            "data_referencia": data_referencia,
        }

    except (KeyError, ValueError, IndexError, TypeError) as e:
        logger.error(f"Fear & Greed: erro ao processar resposta - {e}")
        return None


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
