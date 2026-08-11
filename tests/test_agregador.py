import time

from cotacoes_onilx import agregador


def _fake_lenta(segundos, retorno):
    def coletar():
        time.sleep(segundos)
        return retorno
    return coletar


def _fake_que_explode():
    def coletar():
        raise RuntimeError("provedor caiu")
    return coletar


def test_coletores_rodam_em_paralelo_nao_em_sequencia(monkeypatch):
    # Cada "coletor" dorme 0.3s. Em sequencia, 7 coletores = ~2.1s.
    # Em paralelo, o tempo total fica perto de 0.3s (o mais lento sozinho).
    fake = {nome: _fake_lenta(0.3, {"nome": nome}) for nome, _ in agregador._COLETORES}
    monkeypatch.setattr(agregador, "_COLETAR_CACHEADO", fake)

    inicio = time.perf_counter()
    resultado = agregador.coletar_todas()
    duracao = time.perf_counter() - inicio

    assert duracao < 1.0, f"coleta levou {duracao:.2f}s -- esperado <1s rodando em paralelo"
    assert all(s == "ok" for s in resultado["status_coleta"].values())
    assert len(resultado["dados"]) == len(agregador._COLETORES)


def test_falha_de_um_coletor_nao_afeta_os_outros(monkeypatch):
    fake = {nome: _fake_lenta(0.05, {"nome": nome}) for nome, _ in agregador._COLETORES}
    primeiro_nome = agregador._COLETORES[0][0]
    fake[primeiro_nome] = _fake_que_explode()
    monkeypatch.setattr(agregador, "_COLETAR_CACHEADO", fake)

    resultado = agregador.coletar_todas()

    assert resultado["status_coleta"][primeiro_nome] == "falhou"
    assert resultado["dados"][primeiro_nome] is None
    outros = [n for n, _ in agregador._COLETORES if n != primeiro_nome]
    assert all(resultado["status_coleta"][n] == "ok" for n in outros)


def test_estrutura_de_retorno_identica_a_versao_sequencial(monkeypatch):
    fake = {nome: _fake_lenta(0, {"nome": nome}) for nome, _ in agregador._COLETORES}
    monkeypatch.setattr(agregador, "_COLETAR_CACHEADO", fake)

    resultado = agregador.coletar_todas()

    assert set(resultado.keys()) == {"timestamp_coleta", "dados", "status_coleta"}
    assert set(resultado["dados"].keys()) == {n for n, _ in agregador._COLETORES}
    assert set(resultado["status_coleta"].keys()) == {n for n, _ in agregador._COLETORES}


def test_apenas_roda_so_os_coletores_pedidos(monkeypatch):
    # Carteira OnilX so usa coingecko/macro -- os outros 5 nunca deveriam
    # ser chamados quando `apenas` restringe a esse subconjunto (cada
    # coletor a mais e uma chamada de rede sem consumidor, so latencia).
    chamados = []

    def fake_coletor(nome):
        def coletar():
            chamados.append(nome)
            return {"nome": nome}
        return coletar

    fake = {nome: fake_coletor(nome) for nome, _ in agregador._COLETORES}
    monkeypatch.setattr(agregador, "_COLETAR_CACHEADO", fake)

    resultado = agregador.coletar_todas(apenas=["coingecko", "macro"])

    assert sorted(chamados) == ["coingecko", "macro"]
    assert set(resultado["dados"].keys()) == {"coingecko", "macro"}
    assert set(resultado["status_coleta"].keys()) == {"coingecko", "macro"}


def test_apenas_default_none_continua_rodando_todos(monkeypatch):
    # Comportamento do Kairos ION (pipeline diario, precisa das 7 fontes)
    # nao pode mudar -- default sem `apenas` roda tudo, como sempre rodou.
    chamados = []

    def fake_coletor(nome):
        def coletar():
            chamados.append(nome)
            return {"nome": nome}
        return coletar

    fake = {nome: fake_coletor(nome) for nome, _ in agregador._COLETORES}
    monkeypatch.setattr(agregador, "_COLETAR_CACHEADO", fake)

    agregador.coletar_todas()

    assert sorted(chamados) == sorted(n for n, _ in agregador._COLETORES)
