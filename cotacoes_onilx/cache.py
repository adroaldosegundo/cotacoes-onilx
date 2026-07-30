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
"""
import time
from functools import wraps
from typing import Callable, Optional

_CACHE: dict[str, tuple[float, object]] = {}


def com_cache(ttl_segundos: int) -> Callable:
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
            if valor is not None:
                _CACHE[chave] = (agora + ttl_segundos, valor)
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
