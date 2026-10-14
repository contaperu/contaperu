"""La cuenta bancaria del contribuyente: lo que declara quien llama, no una tabla del motor.

**Es un argumento, no estado.** El §6 de la hoja de ruta lo dice sin rodeos: el periodo, el cierre y el plan de
cuentas como tabla viva son del ERP, y lo que puede vivir aquí es su contrato. Así que esto no guarda cuentas: las
recibe, las valida y las devuelve. El molde es el de `imputaciones` y `correlativos`, que ya lo hacen.

**La cuenta contable la pone el contribuyente, cuenta por cuenta.** Cada cuenta corriente tiene su divisionaria —la
de soles no es la de dólares, y la del Banco de la Nación tampoco—, así que el motor no la deriva ni la supone: la
104 del PCGE es un dato de la empresa, igual que la cuenta de un gasto. Fue la decisión de John del 10-oct-2026, y
tiene precedente: la 3.0 retiró un comodín que imputaba a mercaderías en silencio toda compra sin cuenta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from .. import catalogos
from ..errores import ErrorContaperu

# El Código de Cuenta Interbancario: **20 dígitos en cuatro grupos**, 3 + 3 + 12 + 2.
#
# La estructura está verificada contra dos extractos reales de agosto de 2026, que lo imprimen con su separación a
# la vista —BBVA con espacios, Scotiabank con guiones—. **Los números de esos extractos no se escriben aquí**: un CCI
# con su cuenta es la coordenada para mandarle dinero a alguien, y este repositorio es público (regla 6). Con la
# forma inventada: `011 999 000000000001 00`. Los tres primeros dígitos son la empresa del sistema financiero, los
# tres siguientes su oficina, los doce la cuenta y los dos últimos el control.
#
# **Lo que NO está aquí es el catálogo de códigos de banco**, y es a propósito: no se ha conseguido su fuente
# publicada. Escribirlo de memoria —`011` BBVA y `009` Scotiabank son norma publicada y constan además en esos
# extractos, pero el resto habría que adivinarlo— sería una regla sin fuente, que es la primera que no se negocia. Es el dato que el hito D8
# espera. Mientras tanto el banco se declara por su nombre y el código se transporta sin interpretar.
LARGO_CCI = 20
PATRON_CCI = re.compile(r"^[0-9]{20}$")
# Las monedas en que se puede declarar una cuenta, **derivadas del catálogo y no escritas a mano** (John,
# 11-oct-2026: *«la fuente de monedas la trae el JSON ISO de monedas ya definidas en contaperu; la moneda no debe
# ser manual»*, y antes: *«el que debe pesar son las monedas ya definidas en el repositorio»*). Su fuente es el
# Anexo 1 de la RS 112-2021, Tabla 2, que son códigos ISO 4217.
#
# Hasta la 12.0 aquí había un `("PEN", "USD")` escrito a mano, y el problema no era que estuviera mal: era que
# **era más estrecho que el catálogo** —rechazaba una cuenta en euros aunque `EUR` esté publicado— y que dos
# listas que dicen lo mismo en dos sitios acaban diciendo cosas distintas. Añadir una moneda es añadirla al
# catálogo, con su fuente, no cuenta por cuenta.
#
# Y lo que **no** es de aquí: cómo llame cada ERP a una moneda por dentro, o con qué letra la escriba para un
# sistema legacy. Eso es su alias y su configuración (`monedas_codigo`), y en el documento la moneda va en ISO.
#
# Una cuenta es de UNA moneda: no existe la cuenta mixta, y por eso cada extracto declara la suya en la cabecera.
MONEDAS = tuple(sorted(catalogos.MONEDAS))


class CuentaInvalida(ErrorContaperu, ValueError):
    """Una cuenta declarada que no se puede usar: el motor dice cuál y por qué, y no la arregla."""


def normalizar_cci(cci: str) -> str:
    """El CCI sin su separación, que cada banco escribe a su manera.

    BBVA lo imprime con espacios y Scotiabank con guiones; los dos son el mismo número. Quitar lo que no es dígito
    es la única normalización que admite: **no se rellena con ceros a la izquierda**, porque un CCI corto no es un
    CCI al que le falten ceros, es un dato mal copiado."""
    return re.sub(r"[^0-9]", "", str(cci or ""))


def banco_del_cci(cci: str) -> str:
    """Los tres primeros dígitos: la empresa del sistema financiero. Vacío si el CCI no tiene la forma.

    Sirve para decir si dos cuentas son del mismo banco sin preguntarlo, que es lo que una conciliación necesita
    para distinguir un traspaso entre cuentas propias de un pago a un tercero. **No traduce el código a un nombre**:
    para eso haría falta el catálogo que todavía no tiene fuente."""
    limpio = normalizar_cci(cci)
    return limpio[:3] if PATRON_CCI.fullmatch(limpio) else ""


@dataclass
class CuentaBancaria:
    """Una cuenta del contribuyente, tal como la declara quien llama.

    Lo mínimo para que una conciliación tenga contra qué casar: **de quién es la cuenta, en qué moneda, y con qué
    cuenta contable se asienta**. Todo lo demás —el nombre comercial del producto, la oficina, el ejecutivo— es del
    banco y no se modela: viaja en `datos_originales`, que el motor pasa sin interpretar."""

    id: str = ""                    # cómo la nombra el contribuyente; es la llave con la que un movimiento apunta
    banco: str = ""                 # el nombre, tal cual: el código no se traduce porque no hay catálogo con fuente
    numero: str = ""                # el número de cuenta como lo escribe el banco
    cci: str = ""
    moneda: str = ""
    cuenta_contable: str = ""       # la 104x del contribuyente, que el motor NO deriva
    datos_originales: dict | None = None

    def __post_init__(self) -> None:
        self.id = str(self.id or "").strip()
        self.banco = " ".join(str(self.banco or "").split())
        self.numero = str(self.numero or "").strip()
        self.cci = normalizar_cci(self.cci)
        self.moneda = str(self.moneda or "").strip().upper()
        self.cuenta_contable = re.sub(r"[^0-9]", "", str(self.cuenta_contable or ""))
        if not self.id:
            raise CuentaInvalida("Una cuenta bancaria necesita un `id`: es con lo que un movimiento la nombra")
        # **Sin número ni CCI la cuenta VALE**, y hasta la 12.0.1 se rechazaba (11-oct-2026). Lo destapó John
        # integrando, y lo delataba esta misma clase: su docstring dice que lo mínimo es «de quién es la cuenta,
        # en qué moneda, y con qué cuenta contable se asienta», y el código exigía además un identificador.
        #
        # Los dos son ciertos, pero para cosas distintas. Para **registrar** un pago y **asentarlo** basta lo que
        # dice el docstring: la 104 sale de aquí y la contrapartida de la imputación. El número y el CCI hacen
        # falta para **casar** la cuenta con un archivo del banco, que es conciliar — el hito D3, que no existe
        # todavía. Rechazar por adelantado un dato que solo necesita un paso que nadie puede dar aún obligaba a
        # inventarse un número para poder declarar una cuenta.
        #
        # Así que es un aviso y no un rechazo, igual que la cuenta contable que falta: el mismo trato para la
        # misma clase de hueco —lo que impide un paso POSTERIOR se dice, no se para—. `api.validar_cuentas_bancarias`
        # lo emite como `CUENTA_BANCARIA_SIN_IDENTIFICADOR`.
        if self.cci and not PATRON_CCI.fullmatch(self.cci):
            raise CuentaInvalida(f"CCI inválido en la cuenta {self.id!r}: {self.cci!r} "
                                 f"({LARGO_CCI} dígitos; tiene {len(self.cci)})")
        if self.moneda not in MONEDAS:
            raise CuentaInvalida(f"Moneda inválida en la cuenta {self.id!r}: {self.moneda!r} "
                                 f"({' | '.join(MONEDAS)})")

    @property
    def codigo_de_banco(self) -> str:
        """El código del CCI, cuando hay CCI. Vacío no significa «otro banco»: significa que no se declaró."""
        return banco_del_cci(self.cci)

    def a_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "datos_originales"}
        if self.datos_originales:
            d["datos_originales"] = dict(self.datos_originales)
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "CuentaBancaria":
        """Rechaza lo que no reconoce, nombrándolo: un dato que se cuela sin error es un dato que se pierde sin
        aviso, y el lector no puede ser más laxo que lo que se publica."""
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise CuentaInvalida(f"Claves que no son de una cuenta bancaria: {', '.join(desconocidas)}. "
                                 f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})


def leer(cuentas: list | None) -> tuple[CuentaBancaria, ...]:
    """Las cuentas que aporta quien llama, validadas y con sus `id` sin repetir.

    Sin cuentas no pasa nada: es un argumento opcional, y su ausencia no cambia ningún comportamiento. Es la misma
    promesa que hacen `plan_de_cuentas*` y `padron*` cuando entren."""
    leidas = tuple(c if isinstance(c, CuentaBancaria) else CuentaBancaria.de_dict(c) for c in (cuentas or []))
    vistos: dict[str, int] = {}
    for c in leidas:
        vistos[c.id] = vistos.get(c.id, 0) + 1
    repetidos = sorted(k for k, n in vistos.items() if n > 1)
    if repetidos:
        raise CuentaInvalida(f"Hay cuentas bancarias con el mismo `id`: {', '.join(repetidos)}. "
                             f"El `id` es la llave con la que un movimiento las nombra, así que tiene que ser único")
    return leidas


def por_id(cuentas: list | None) -> dict[str, CuentaBancaria]:
    """El maestro indexado por el `id` con el que un movimiento nombra su cuenta.

    Es `leer` más la búsqueda, que es como se usa de verdad: un movimiento dice `cuenta: "bbva-soles"` y lo que
    hace falta es **su cuenta contable**, la 104 con la que se asienta. Vivía escrito a mano dentro de
    `api.revisar_tesoreria` y se publica aquí porque el asiento de tesorería lo necesita en otro sitio: dos copias
    de la misma búsqueda es como se separan.

    Devuelve un diccionario y no una lista por lo mismo que `extractos.por_cuenta`: así se usa, y el rechazo de dos
    `id` iguales cae en `leer`, en la puerta, y no más adentro."""
    return {c.id: c for c in leer(cuentas)}


def sin_cuenta_declarada(movimientos=(), cuentas=()) -> list[dict]:
    """Los movimientos que apuntan a una cuenta que nadie declaró.

    **Se reporta y no se adivina**, que es la misma doctrina que «sin imputación no hay cuenta»: el `id` de una
    cuenta es la llave con la que el dinero se enlaza con su 104, y si no está en el maestro no hay nada que
    deducir — ni el banco, ni la moneda, ni la cuenta contable.

    Hasta la 9.1 esto pasaba en silencio: `Movimiento.cuenta` se normalizaba y nadie la contrastaba con nada, así
    que un `id` mal escrito producía un movimiento perfectamente válido que no se podía casar con ninguna cuenta.
    Es el tipo de error que no se ve hasta el cierre.

    Mira un solo bloque desde la 3.0 del estándar, que fundió las constancias en los movimientos: hasta entonces
    recorría los dos y la `cuenta_origen` de una constancia era el segundo sitio donde preguntar lo mismo.

    Devuelve una lista de `{que, cual, cuenta}` —`que` se conserva para que el aviso se lea igual— y sin cuentas
    declaradas devuelve vacío: es un argumento opcional y su ausencia no inventa un error."""
    declaradas = {c.id for c in leer(list(cuentas) or None)}
    if not declaradas:
        return []
    huerfanos: list[dict] = []
    for m in movimientos or ():
        cuenta = str(getattr(m, "cuenta", None) or (m.get("cuenta") if isinstance(m, dict) else "") or "").strip()
        if cuenta and cuenta not in declaradas:
            ref = str(getattr(m, "referencia", None) or (m.get("referencia") if isinstance(m, dict) else "") or "")
            huerfanos.append({"que": "movimiento", "cual": ref, "cuenta": cuenta})
    return huerfanos
