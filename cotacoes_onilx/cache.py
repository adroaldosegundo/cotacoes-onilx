"""
Cache TTL em memoria para coletores.

Os coletores originais (kairos_ion) rodam 1x/dia, entao nunca precisaram
de cache. Consumidores interativos (dashboard aberto varias vezes ao dia)
precisam evitar bater na API a cada refresh — daqui o motivo deste modulo.

Uso:

    from cotacoes_onilx.cache import com_cache

    @com_cache(ttl_segundos=90)
    def coletar():
        ...

Falhas (retorno None) tambem sao cacheadas, com TTL proprio (mais curto
que o de sucesso por padrao). Sem isso, um provedor fora do ar ou
rate-limited (ex.: CoinGecko 429, que ja faz 3 tentativas com backoff)
paga o custo total de retry a cada request enquanto durar a instabilidade
— justamente quando mais pesa numa UI interativa.
"""
import time
from functools import wraps
from typing import Callable, Optional

_CACHE: dict[str, tuple[float, object]] = {}


def com_cache(ttl_segundos: int, ttl_erro_segundos: Optional[int] = None) -> Callable:
    if ttl_erro_segundos is None:
        ttl_erro_segundos = min(ttl_segundos, 30)

    def decorador(func: Callable) -> Callable:
        chave = f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            agora = time.monotonic()
            cacheado = _CACHE.get(chave)
            if cacheado is not None:
                expira_em, valor = cacheado
                if agora < expira_em:
                    return valor

            valor = func(*args, **kwargs)
            ttl = ttl_segundos if valor is not None else ttl_erro_segundos
            _CACHE[chave] = (agora + ttl, valor)
            return valor

        return wrapper

    return decorador


def limpar_cache(chave_parcial: Optional[str] = None) -> None:
    """Util em testes: limpa tudo, ou so entradas cuja chave contem `chave_parcial`."""
    if chave_parcial is None:
        _CACHE.clear()
        return
    for k in [k for k in _CACHE if chave_parcial in k]:
        del _CACHE[k]
