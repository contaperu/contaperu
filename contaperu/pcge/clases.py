"""De qué clase es una cuenta, según el elemento del PCGE.

El Plan Contable General Empresarial clasifica por **elementos**, y el elemento es el primer dígito del código. Eso
es todo lo que hace falta para saber si una cuenta es un activo, un pasivo, patrimonio, un ingreso o un gasto —las
cinco clases que `contaperu/vocabulario.py` publica y que cualquier ERP del mundo entiende sin conocer el PCGE.

**Por qué el primer dígito y no el rol de la línea.** El primer borrador de la 1.0 decía que la clase se deducía del
rol y del libro. No sirve, y se comprueba en un caso diario: una **compra de mercadería** imputada a `201101` sale con
`rol: principal`, y esa línea es un **activo**, no un gasto; lo mismo una compra de activo fijo a `333101`. Deducirla
del rol daría `gasto` en miles de facturas al mes. La cuenta es lo único que sabe qué se compró.

**Por qué esto vive en `pcge/` y no junto a las cinco clases.** Son dos cosas de dos capas distintas: los cinco
valores son universales y los comparten QuickBooks, Xero, Merge y Rutter; «el primer dígito dice el elemento» es el
PCGE, o sea Perú. El día que llegue otra jurisdicción, el vocabulario se queda y solo se cambia el que mapea.

**Los elementos 8 y 0 no tienen clase, y no se fuerzan.** El 8 son los saldos intermediarios de gestión y el 0 las
cuentas de orden: son de cierre y de control, el motor no las emite desde compras ni ventas, y una imputación a ellas
es casi seguro un error. Se dice con su motivo (`asiento.faltas.SinClase`) en vez de inventarle una clase: las cinco
clases siguen siendo cinco, que es justo lo que las hace universales.

Fuente: Plan Contable General Empresarial 2026 (PCGE 2026), Consejo Normativo de Contabilidad, Capítulo II —
clasificación y catálogo de cuentas. Los elementos, con su nombre: 1 activo disponible y exigible · 2 activo
realizable · 3 activo inmovilizado · 4 pasivo · 5 patrimonio neto · 6 gastos por naturaleza · 7 ingresos · 8 saldos
intermediarios de gestión · 9 contabilidad analítica de explotación (costos por función) · 0 cuentas de orden.
"""
from __future__ import annotations

# elemento del PCGE → clase. El 9 es `gasto` porque muchas empresas imputan el gasto por su destino y no por su
# naturaleza, y esa línea es un gasto igual. El 8 y el 0 no están: no tienen clase.
ELEMENTOS: dict[str, str] = {
    "1": "activo", "2": "activo", "3": "activo",
    "4": "pasivo",
    "5": "patrimonio",
    "6": "gasto", "9": "gasto",
    "7": "ingreso",
}

FUENTE = ("Plan Contable General Empresarial 2026 (PCGE 2026), Consejo Normativo de Contabilidad. "
          "Capítulo II — Clasificación y catálogo de cuentas: el primer dígito del código es el elemento.")


def elemento(cuenta: str) -> str:
    """El elemento del PCGE de esta cuenta: su primer dígito, o vacío si no empieza por uno."""
    primero = str(cuenta or "").strip()[:1]
    return primero if primero.isdigit() else ""


def clase_de(cuenta: str) -> str:
    """La clase contable de esta cuenta, o **vacío** si su elemento no tiene ninguna (8 y 0) o no es un dígito.

    Quien la use tiene que decidir qué hace con el vacío; el motor lo cuenta como falta y no genera el asiento.
    """
    return ELEMENTOS.get(elemento(cuenta), "")
