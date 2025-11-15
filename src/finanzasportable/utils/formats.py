from decimal import Decimal, InvalidOperation
import re

def parse_amount(s: str) -> float:
    """
    Acepta: "5.000,00" | "1,234.56" | "-1.200,50" | "$ 1.234,56" | "5000"
    Regresa float con signo correcto.
    """
    if s is None: raise ValueError("Monto vacío")
    s = str(s).strip()
    if not s: raise ValueError("Monto vacío")
    s = s.replace("$", "").replace("ARS", "").replace("USD", "").strip()
    # Detectar notación:
    if re.search(r",\d{2}$", s) and "." in s:
        # Formato ES: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",")==1 and s.count(".")==0:
        # Formato ES sin miles: 1234,56
        s = s.replace(",", ".")
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Monto inválido: {s}")

def money(x: float, currency: str = "ARS") -> str:
    sign = "-" if (x is not None and x < 0) else ""
    v = abs(x or 0.0)
    return f"{sign}{currency} {v:,.2f}".replace(",", "_").replace(".", ",").replace("_",".")
