"""Cuánto de un pago cancela un documento: el puente entre los tres libros (enmienda 0031).

Hasta la 12.3 `libro.tipo` valía `compra`, `venta` o `tesoreria` y lo único que los unía era
`movimiento.referencias`, que va en una sola dirección y cuyo importe es opcional. Con eso no se puede contestar
si una factura está por cobrar o cobrada.

**Lo que esto es, y lo que no.** `referencias` dice lo que AFIRMA el papel; una aplicación dice lo que alguien
DECIDIÓ aplicar, y por cuánto. Es el mismo corte que el estándar ya hizo entre `movimiento` —el hecho— y
`imputaciones_de_movimientos` —la decisión del ERP—: **`aplicaciones` es a `referencias` lo que
`imputaciones_de_movimientos` es a `movimiento`.** Las dos conviven y ninguna sustituye a la otra.

**Tres reglas, de los ocho sistemas que `REFERENCIAS.md` comparó el 12-oct-2026:**

1. Es un registro aparte con su importe, **N a N**. Tres pagos para una factura son tres aplicaciones, y **el
   tercero no es especial**: nadie necesita saber cuál la cierra.
2. Nombra documentos, no libros ni meses. Funciona entre periodos porque `Comprobante.clave` no lleva el periodo.
3. **El saldo se deriva de la suma y no se guarda en ninguna parte.** Aquí no se suma nada: este módulo lee el
   contrato y lo valida.

**Y `origen` es lo que convierte la doctrina en regla.** `declarado` lo afirma el papel, `manual` lo decidió una
persona, `propuesto` lo propuso una conciliación y nadie lo ha confirmado — y una `propuesto` **no cuenta para
ningún saldo**, que es «`conciliar` propone y nunca confirma» hecho algo que un test puede poner en rojo.

Lo que nombra una aplicación **no tiene que estar en el documento**: una factura de enero pagada en marzo viaja en
otro mes. Por eso la presencia se **avisa** y no se exige (`sin_documento_declarado`), con el mismo trato que
`CUENTA_BANCARIA_SIN_IDENTIFICADOR`: lo que impide un paso posterior se dice, no se para.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .errores import ErrorContaperu
from .modelo import CERO, clave_de, fecha as _fecha, monto as _monto
# Las claves de `comprobante` y de `tributo` se toman de donde ya estaban en vez de volver a escribirlas: son la
# misma forma de nombrar lo mismo, y dos listas separadas se habrían separado.
from .tesoreria.referencias import CLAVES_POR_CLASE as _CLAVES_DE_REFERENCIA

# De dónde sale una aplicación.
DECLARADO = "declarado"    # lo afirma el papel: una constancia de detracción nombra su comprobante
MANUAL = "manual"          # lo decidió una persona
PROPUESTO = "propuesto"    # lo propuso una conciliación, y nadie lo ha confirmado
ORIGENES = (DECLARADO, MANUAL, PROPUESTO)
# Las que cuentan para un saldo. `propuesto` queda fuera, y eso es el contrato: una conjetura no mueve un saldo.
CONFIRMADAS = (DECLARADO, MANUAL)

# Qué puede ser cada extremo.
COMPROBANTE = "comprobante"
MOVIMIENTO = "movimiento"
TRIBUTO = "tributo"
CLASES = (COMPROBANTE, MOVIMIENTO, TRIBUTO)

# Y en qué extremo cabe cada una. `libre` y `cuenta_propia` —que sí son clases de `referencia_de_pago`— no caben en
# ninguno: una aplicación existe para reducir un saldo, y solo un documento o un tributo tiene saldo.
CLASES_QUE_PAGAN = (MOVIMIENTO, COMPROBANTE)
CLASES_QUE_SE_CANCELAN = (COMPROBANTE, TRIBUTO)

CLAVES_POR_CLASE = {
    COMPROBANTE: _CLAVES_DE_REFERENCIA[COMPROBANTE],
    MOVIMIENTO: ("id_externo",),      # la misma llave con la que al movimiento le llega su imputación
    TRIBUTO: _CLAVES_DE_REFERENCIA[TRIBUTO],
}


class AplicacionInvalida(ErrorContaperu, ValueError):
    """Una aplicación que no se puede usar. Dice cuál y por qué, y no la arregla."""


@dataclass
class Extremo:
    """Uno de los dos lados de una aplicación: qué documento es.

    Se nombra igual que en `referencia_de_pago`, y a propósito: quien ya sabe decir qué cancela un pago no tiene
    que aprender otra forma para decir qué se aplicó."""

    clase: str = ""
    datos: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.clase = str(self.clase or "").strip().lower()
        if self.clase not in CLASES:
            raise AplicacionInvalida(f"Clase inválida en un extremo: {self.clase!r} ({' | '.join(CLASES)})")
        self.datos = {str(k): ("" if v is None else str(v)).strip() for k, v in dict(self.datos or {}).items()}
        admitidas = CLAVES_POR_CLASE[self.clase]
        sobran = sorted(set(self.datos) - set(admitidas))
        if sobran:
            raise AplicacionInvalida(f"Un extremo de clase {self.clase!r} no lleva {', '.join(sobran)}. "
                                     f"Lleva: {', '.join(admitidas)}")
        if not any(self.datos.values()):
            raise AplicacionInvalida(f"Un extremo de clase {self.clase!r} sin ningún dato no nombra nada")

    @property
    def clave(self) -> tuple:
        """La identidad comparable de lo que nombra, con su clase delante para que dos clases nunca colisionen.

        La de un comprobante la calcula `modelo.clave_de`, la misma función que usa `Comprobante.clave`: si no
        fuese la misma, un comprobante y la aplicación que lo nombra no se reconocerían por un cero a la izquierda.
        """
        if self.clase == COMPROBANTE:
            return (COMPROBANTE, clave_de(self.datos.get("tipo_cp", ""), self.datos.get("serie", ""),
                                          self.datos.get("numero", ""), self.datos.get("contraparte_doc", "")))
        if self.clase == MOVIMIENTO:
            return (MOVIMIENTO, self.datos.get("id_externo", ""))
        return (TRIBUTO, self.datos.get("codigo", ""), self.datos.get("periodo", ""))

    def a_dict(self) -> dict:
        return {"clase": self.clase, "datos": dict(self.datos)}

    @classmethod
    def de(cls, valor) -> "Extremo":
        if isinstance(valor, Extremo):
            return valor
        if not isinstance(valor, dict):
            raise AplicacionInvalida("Un extremo de una aplicación tiene que ser un objeto con su clase y sus datos")
        sobran = sorted(set(valor) - {"clase", "datos"})
        if sobran:
            raise AplicacionInvalida(f"Un extremo no lleva {', '.join(sobran)}. Lleva: clase, datos")
        return cls(clase=valor.get("clase", ""), datos=valor.get("datos") or {})


@dataclass
class Aplicacion:
    """Cuánto de `de` cancela `a`.

    Los seis campos son obligatorios, y cada uno por su razón. `moneda` va aquí **aunque esté en los documentos**
    porque una aplicación puede nombrar un comprobante de otro mes que no viaja en este documento: tiene que
    bastarse. Y `fecha` porque sin ella no se puede situar en el tiempo, y todo origen real la tiene — la del pago,
    la de la nota, el día en que alguien lo decidió.

    El importe es positivo, como todo importe del estándar: **la dirección la dicen los nombres de los dos extremos
    y no el signo.**"""

    de: Extremo | dict | None = None
    a: Extremo | dict | None = None
    importe: object = None
    moneda: str = ""
    fecha: date | None = None
    origen: str = ""

    def __post_init__(self) -> None:
        for lado, admitidas in (("de", CLASES_QUE_PAGAN), ("a", CLASES_QUE_SE_CANCELAN)):
            valor = getattr(self, lado)
            if valor is None:
                raise AplicacionInvalida(f"Una aplicación necesita su `{lado}`: sin los dos lados no cancela nada")
            extremo = Extremo.de(valor)
            if extremo.clase not in admitidas:
                raise AplicacionInvalida(
                    f"Un {extremo.clase!r} no cabe en `{lado}` de una aplicación ({' | '.join(admitidas)}). "
                    f"Un movimiento paga y no se cancela; un tributo se cancela y no paga")
            setattr(self, lado, extremo)
        self.importe = _monto(self.importe)
        if self.importe <= CERO:
            raise AplicacionInvalida(f"Una aplicación de {self.importe} no aplica nada")
        self.moneda = str(self.moneda or "").strip().upper()
        if len(self.moneda) != 3 or not self.moneda.isalpha():
            raise AplicacionInvalida(
                f"Moneda inválida en una aplicación: {self.moneda!r}. Son tres letras (ISO 4217), y se comprueba "
                "la forma y no el catálogo, igual que en un movimiento: el catálogo es de SUNAT y puede crecer")
        self.fecha = _fecha(self.fecha)
        if self.fecha is None:
            raise AplicacionInvalida("Una aplicación sin fecha no se puede situar en el tiempo, y todo origen "
                                     "real la tiene: la del pago, la de la nota, o el día en que se decidió")
        self.origen = str(self.origen or "").strip().lower()
        if self.origen not in ORIGENES:
            raise AplicacionInvalida(f"Origen inválido en una aplicación: {self.origen!r} ({' | '.join(ORIGENES)}). "
                                     "Decirlo es lo que separa un hecho de una conjetura")

    @property
    def cuenta_para_el_saldo(self) -> bool:
        """Si esta aplicación mueve un saldo. Una `propuesto` no, y ahí vive «propone y nunca confirma»."""
        return self.origen in CONFIRMADAS

    def a_dict(self) -> dict:
        return {"de": self.de.a_dict(), "a": self.a.a_dict(), "importe": str(self.importe),
                "moneda": self.moneda, "fecha": self.fecha.isoformat(), "origen": self.origen}

    @classmethod
    def de_dict(cls, d: dict) -> "Aplicacion":
        """Rechaza una clave que no es de una aplicación, nombrándolas todas.

        La misma regla que `Comprobante.de_dict` y `Movimiento.de_dict`: el lector no puede ser más laxo que el
        esquema publicado, que ya rechaza por su `additionalProperties: false`."""
        if not isinstance(d, dict):
            raise AplicacionInvalida("Una aplicación tiene que ser un objeto")
        campos = ("de", "a", "importe", "moneda", "fecha", "origen")
        sobran = sorted(set(d) - set(campos))
        if sobran:
            raise AplicacionInvalida(f"Claves que no son de una aplicación: {', '.join(sobran)}. "
                                     f"Lleva: {', '.join(campos)}")
        return cls(**{k: d.get(k) for k in campos})


def leer(crudas) -> tuple[Aplicacion, ...]:
    """El bloque `aplicaciones` del documento, tipado. Una lista ausente son cero aplicaciones y no un error."""
    if crudas is None:
        return ()
    if not isinstance(crudas, (list, tuple)):
        raise AplicacionInvalida("`aplicaciones` tiene que ser una lista")
    return tuple(a if isinstance(a, Aplicacion) else Aplicacion.de_dict(a) for a in crudas)


def sin_documento_declarado(aplicaciones=(), comprobantes=(), movimientos=()) -> list[dict]:
    """Las aplicaciones que nombran algo que no viaja en este documento, **para avisar y no para parar**.

    No es un error y no puede serlo: una factura de enero pagada en marzo se nombra desde el documento de marzo, y
    el comprobante está en el de enero. Lo que esto caza es la otra mitad —una llave mal escrita, un número con un
    cero de más— que si no se dijera dejaría ese documento sin su pago y sin aviso.

    Devuelve `{que, cual, clase}` por cada extremo que no se encuentra, con el mismo trato que
    `tesoreria.sin_cuenta_declarada`."""
    presentes = {(COMPROBANTE, c.clave) for c in comprobantes}
    presentes |= {(MOVIMIENTO, str(getattr(m, "id_externo", "") or "")) for m in movimientos}
    sueltas = []
    for aplicacion in aplicaciones:
        for lado in ("de", "a"):
            extremo = getattr(aplicacion, lado)
            if extremo.clase == TRIBUTO:
                continue          # un tributo no es un documento de este libro: no hay dónde buscarlo
            if extremo.clave not in presentes:
                sueltas.append({"que": lado, "cual": " ".join(v for v in extremo.datos.values() if v),
                                "clase": extremo.clase})
    return sueltas
