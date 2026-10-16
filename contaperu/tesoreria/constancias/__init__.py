"""El primer lector de tesorería: una constancia de pago, convertida en los movimientos que el motor ya asienta.

`tesoreria/` tenía el contrato entero desde la 11.x —`Movimiento`, `Extracto`, la deduplicación, el cuadre— y
**ni un solo lector**, a propósito: «cada parser entra con su archivo delante y su fixture anonimizado». Éste
entra con los suyos, que son constancias reales de un contribuyente peruano de 2026 de dos bancos.

## Recibe texto, nunca un PDF

Es la misma frontera que `comprobantes/sire_txt.py` tiene con el TXT del SIRE, y la razón es la de siempre: el
núcleo no toca disco, no sale a la red y no abre formatos binarios (`tests/test_frontera.py`). Sacar el texto del
PDF es de quien integra —con una librería o con un modelo—; estructurarlo, cuadrarlo y darle forma de libro es de
aquí. Y hay un dato que conviene saber antes de elegir cómo sacarlo: de los 80 PDF reales que fundaron el lector,
**22 no dan texto legible con una librería estándar** —sus fuentes vienen sin tabla ToUnicode, así que lo que sale
son glifos `/0 /1 /2`—. Ésos piden OCR o un modelo, y por eso `Movimiento.origen` ya distinguía `pdf_texto` de
`vision` antes de que existiera este lector.

## Cinco formatos, que son cinco papeles

| `formato` | Banco | Qué devuelve |
|---|---|---|
| `bcp_terceros` | BCP | un cargo |
| `bcp_cce` | BCP | el cargo **y su comisión CCE** aparte |
| `bcp_documentos` | BCP (Telecrédito) | un cargo con **la tabla de documentos que cancela** |
| `bbva_operacion` | BBVA | un cargo |
| `bbva_masivos` | BBVA | el cargo de la planilla, **sus comisiones** y **N abonos** como referencias |

Por eso `leer` devuelve **una lista** y no un movimiento: de un solo papel salen hasta tres movimientos de la
misma cuenta, y eso no es un detalle del BBVA — es la enmienda 0028 («un cargo del banco es su propio
movimiento») escrita por el banco en tres renglones.

## El maestro de cuentas no es opcional

`Movimiento.cuenta` es el `id` con que el contribuyente llama a su cuenta, no un número; el motor lo exige y hace
bien. Así que `leer` pide las `cuentas_bancarias` declaradas y resuelve el número del papel contra ellas. Si la
cuenta del papel no está declarada, se niega diciendo el número: es lo único que hace falta para añadirla.

## Lo que este lector NO hace, y está pendiente de un archivo y no de código

- **Leer un extracto** (D2). Una constancia dice lo que el contribuyente ordenó; un extracto, lo que el banco
  hizo, con su saldo corrido y su ITF cuantificado. Son dos papeles y éste es el primero.
- **Casar el pago con los comprobantes** (D3). Lo que el pago cancela ya viaja —en `referencias`, y el
  `bcp_documentos` lo trae declarado por el banco—, pero **proponerlo** cuando el papel no lo dice es
  conciliación, y su método se fija con el extracto delante.
- **Cuantificar el ITF.** El CCE lo declara «Afecta» y no lo cifra. Se asienta con el importe que da el banco y
  nunca con una tasa (John, 13-oct-2026), así que ese movimiento llega por el extracto.
"""
from __future__ import annotations

from . import bbva, bcp
from .comun import ConstanciaIlegible

#: Qué formato es cada papel, y con qué se reconoce. La seña es el encabezado que el banco escribe y que ningún
#: otro de los cinco escribe — no una heurística: o está o no está. Y `leer` exige que case **exactamente uno**,
#: porque si casaran dos la tabla estaría mal y elegir sería adivinar.
FORMATOS = {
    "bcp_documentos": ("Pago de letras y facturas", bcp.documentos),
    "bcp_cce": ("Transferencia a otros bancos locales", bcp.cce),
    "bcp_terceros": ("Transferencia a cuentas de terceros", bcp.terceros),
    "bbva_masivos": ("Consulta de la Orden", bbva.masivos),
    "bbva_operacion": ("Su operación ha sido realizada", bbva.operacion),
}


def reconocer(texto: str) -> str:
    """De qué formato es el texto, o cadena vacía si no es de ninguno de los cinco.

    Devolver vacío en vez de levantar es a propósito: quien integra pasa un montón de PDF y necesita apartar los
    que no son constancias —o los que salieron en glifos— sin que eso sea un error."""
    casan = [nombre for nombre, (sena, _) in FORMATOS.items() if sena.lower() in (texto or "").lower()]
    return casan[0] if len(casan) == 1 else ""


def leer(texto: str, cuentas=()) -> list:
    """Los movimientos de una constancia: de uno a tres, según lo que el papel diga.

    `cuentas` son las `CuentaBancaria` que el contribuyente declara, y hace falta porque un movimiento apunta a
    una cuenta del maestro y no a un número suelto.

    Se niega —`ConstanciaIlegible`— cuando el texto no es de ningún formato conocido, cuando le falta algo que su
    formato promete, o cuando **los importes no cuadran** entre sí. Lo último es lo que convierte «leí un PDF» en
    «lo leí bien», y es la razón de que un pago mal leído no llegue nunca al libro a medias."""
    formato = reconocer(texto)
    if not formato:
        casan = [n for n, (sena, _) in FORMATOS.items() if sena.lower() in (texto or "").lower()]
        if casan:
            raise ConstanciaIlegible(f"el texto casa con {len(casan)} formatos a la vez ({', '.join(casan)}): "
                                     f"la tabla de señas está mal y no se va a adivinar cuál es")
        raise ConstanciaIlegible(f"el texto no es de ninguno de los formatos que se saben leer: "
                                 f"{', '.join(FORMATOS)}")
    return FORMATOS[formato][1](texto, cuentas)


__all__ = ["FORMATOS", "ConstanciaIlegible", "bbva", "bcp", "leer", "reconocer"]
