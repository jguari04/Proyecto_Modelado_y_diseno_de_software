from finanzasportable.services.db import db_path_general
from finanzasportable.services.transactions import listar_transacciones
from finanzasportable.services.balances import listar_saldos_por_cuenta, total_saldo

def test_services_smoke():
    db = db_path_general()
    tx = listar_transacciones(db)
    bal = listar_saldos_por_cuenta(db)
    tot = total_saldo(db)
    assert isinstance(tx, list)
    assert isinstance(bal, list)
    assert isinstance(tot, float)
