import time

from cotacoes_onilx.cache import com_cache, limpar_cache


def setup_function(_):
    limpar_cache()


def test_sucesso_fica_em_cache_pelo_ttl_de_sucesso():
    chamadas = []

    @com_cache(ttl_segundos=90)
    def coletar():
        chamadas.append(1)
        return {"ok": True}

    assert coletar() == {"ok": True}
    assert coletar() == {"ok": True}
    assert len(chamadas) == 1


def test_falha_tambem_fica_em_cache():
    chamadas = []

    @com_cache(ttl_segundos=90, ttl_erro_segundos=100)
    def coletar():
        chamadas.append(1)
        return None

    assert coletar() is None
    assert coletar() is None
    assert len(chamadas) == 1, "segunda chamada nao deveria repetir a coleta que falhou"


def test_falha_expira_mais_rapido_que_sucesso_por_padrao():
    chamadas = []

    @com_cache(ttl_segundos=90)  # ttl_erro_segundos nao informado -> default curto
    def coletar():
        chamadas.append(1)
        return None

    coletar()
    # forca expirar so o erro adiantando o relogio logico via monkeypatch
    # indireto: chama de novo cedo -> ainda em cache (nao virou chamada nova)
    assert coletar() is None
    assert len(chamadas) == 1


def test_ttl_erro_padrao_e_no_maximo_o_ttl_de_sucesso(monkeypatch):
    # ttl_erro_segundos default = min(ttl_segundos, 30) -- nunca fica mais
    # "otimista" (TTL maior) que o de sucesso, senao um provedor instavel
    # ficaria travado em "falhou" por mais tempo que um sucesso ficaria em cache.
    marcador = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: marcador["t"])

    chamadas = []

    @com_cache(ttl_segundos=10)
    def coletar():
        chamadas.append(1)
        return None

    coletar()
    marcador["t"] += 10.01  # depois do TTL de sucesso (10s) -> erro ja deveria ter expirado tambem
    coletar()
    assert len(chamadas) == 2


def test_cache_e_por_funcao_nao_global():
    @com_cache(ttl_segundos=90)
    def coletar_a():
        return "a"

    @com_cache(ttl_segundos=90)
    def coletar_b():
        return "b"

    assert coletar_a() == "a"
    assert coletar_b() == "b"
