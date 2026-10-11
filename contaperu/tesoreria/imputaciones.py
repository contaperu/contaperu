"""Lo que el ERP decide sobre un movimiento, porque el motor lo necesita y el papel no lo dice.

Es la frase de John del 11-oct-2026: *«las imputaciones sirven para traer datos que el ERP tiene que poner porque
el motor estándar lo necesita»*. Y es la misma doctrina que rige la cuenta de una compra desde la 3.0: **el motor
no elige ninguna cuenta, la recibe**, y si falta lo dice en vez de inventar una (`asiento.resolucion.imputado`:
sin imputación no hay cuenta).

**La 104 no sale de aquí.** Sale de `CuentaBancaria.cuenta_contable` del maestro que el contribuyente declara, que
es donde se decidió que viva (John, 10-oct-2026: «cada cuenta corriente tiene su divisionaria —la de soles no es la
de dólares, y la del Banco de la Nación tampoco—, así que el motor no la deriva ni la supone»). Lo que esto pone es
**la otra cara**.

**Y no se reusa `asiento.Imputacion`**, que es la del comprobante, por tres razones:

1. **El espacio de llaves colisionaría.** `imputaciones` significa «por `id_externo` de comprobante»; un ERP tiene
   secuencias de id independientes para sus facturas y sus movimientos, así que `"fila-12"` puede ser las dos
   cosas. Compartir el espacio obligaría a exigir unicidad **entre bloques**, que es un requisito nuevo sobre quien
   ya produce documentos.
2. **Los campos no son los mismos.** La del comprobante lleva `cuenta_tercero` («la cuenta del total: 42 en
   compras, 12 en ventas»), `detraccion_codigo` y `anulada_por_nota`, que un movimiento no tiene; y su `reparto`
   «divide solo la base — el IGV y el total son del documento», mientras un movimiento no tiene base ni IGV.
   Reusándola, una imputación de movimiento podría llevar `anulada_por_nota` legalmente.
3. **El `allOf` de la raíz tendría que crecer mal**: exige `id_externo` en cada comprobante cuando hay
   imputaciones, así que imputar solo movimientos obligaría a ponérselo a comprobantes que nadie imputa.

**Lo que esto NO es: lo que el pago cancela.** Eso viaja en `movimiento.referencias[]` si el papel lo dice, y
casarlo con un comprobante es el hito D3. Aquí va **la cuenta**, no el documento.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields

from ..errores import ErrorContaperu
from ..modelo import CERO, monto as _monto
from .movimientos import TRANSFERENCIA


class ImputacionInvalida(ErrorContaperu, ValueError):
    """Una imputación de movimiento que no se puede aplicar. Dice cuál y por qué."""


@dataclass
class Parte:
    """Un trozo del movimiento con su propia cuenta: un cargo que paga tres facturas son tres partes."""

    importe: object = None
    cuenta_contable: str = ""
    centro_costo: str = ""
    contraparte_doc: str = ""

    def __post_init__(self) -> None:
        self.cuenta_contable = str(self.cuenta_contable or "").strip()
        self.centro_costo = str(self.centro_costo or "").strip()
        self.contraparte_doc = str(self.contraparte_doc or "").strip().upper()
        # **El importe es obligatorio en una parte**, al revés que en una referencia: una referencia sin importe
        # vale por el total y no hay nada que repartir, pero un reparto sin importes no reparte nada.
        if self.importe is None or self.importe == "":
            raise ImputacionInvalida("Una parte del reparto necesita su importe: sin él no hay nada que repartir")
        self.importe = _monto(self.importe)
        if self.importe <= CERO:
            raise ImputacionInvalida(f"Importe inválido en una parte del reparto: {self.importe}")
        if not self.cuenta_contable:
            raise ImputacionInvalida("Una parte del reparto necesita su cuenta: es para lo que existe")

    def a_dict(self) -> dict:
        d = {"importe": str(self.importe), "cuenta_contable": self.cuenta_contable}
        for clave in ("centro_costo", "contraparte_doc"):
            if getattr(self, clave):
                d[clave] = getattr(self, clave)
        return d


@dataclass
class ImputacionDeMovimiento:
    """La contrapartida de un movimiento. Todo es opcional, pero las tres formas se excluyen."""

    cuenta_contable: str = ""
    centro_costo: str = ""
    contraparte_doc: str = ""
    # El `id` de OTRA cuenta del maestro. **Es la única vía declarada para afirmar una transferencia**: el efecto
    # `transferencia` del catálogo existe porque la NIC 7 §9 excluye de los flujos los traspasos entre partidas de
    # efectivo, y `Movimiento.efecto` nunca lo devuelve porque una línea sola no puede saber que es la mitad de un
    # par. Aquí sí: lo declara quien lo sabe. La otra vía es `conciliar`, que **propone y nunca confirma** (D3).
    cuenta_propia: str = ""
    reparto: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cuenta_contable = str(self.cuenta_contable or "").strip()
        self.centro_costo = str(self.centro_costo or "").strip()
        self.contraparte_doc = str(self.contraparte_doc or "").strip().upper()
        self.cuenta_propia = str(self.cuenta_propia or "").strip()
        self.reparto = [p if isinstance(p, Parte) else Parte(**dict(p)) for p in (self.reparto or [])]
        sueltos = [c for c in ("cuenta_contable", "centro_costo", "contraparte_doc") if getattr(self, c)]
        if self.reparto and sueltos:
            raise ImputacionInvalida(
                f"Una imputación con reparto no lleva además {', '.join(sueltos)} (¿cuál mandaría?): deja solo el "
                f"reparto, y pon en cada parte lo suyo")
        if self.cuenta_propia and (sueltos or self.reparto):
            raise ImputacionInvalida(
                "Una imputación con `cuenta_propia` no lleva nada más: declarar un traspaso ES decir cuál es la "
                "contrapartida, y es otra cuenta de efectivo del maestro")

    @property
    def repartido(self) -> object:
        return sum((p.importe for p in self.reparto), CERO)

    @property
    def es_traspaso(self) -> bool:
        """Si el ERP declaró que esto es la mitad de un traspaso entre cuentas propias."""
        return bool(self.cuenta_propia)

    def exigir_que_sume(self, importe: object, cual: str = "") -> None:
        """El reparto suma el importe del movimiento, **exacto y sin tolerancia**.

        Aquí **bloquea**, y no se reporta como `sin_atribuir`: ese informe existe porque «qué es ese resto lo decide
        el contador por la imputación», y esto ya ES la imputación. Si el reparto no cuadra, lo que hay es una
        decisión a medias y no un dato que falte.

        **El ITF queda fuera** de la suma: son sus dos líneas propias, y esperan su norma (el hito D6)."""
        if not self.reparto:
            return
        if self.repartido != importe:
            raise ImputacionInvalida(
                f"El reparto de {cual or 'un movimiento'} suma {self.repartido} y el movimiento es de {importe}: "
                f"tiene que ser exacto. El ITF no entra en la suma, porque son sus dos líneas propias")

    def a_dict(self) -> dict:
        d: dict = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "reparto":
                if v:
                    d[f.name] = [p.a_dict() for p in v]
            elif v:
                d[f.name] = v
        return d

    @classmethod
    def de(cls, valor) -> "ImputacionDeMovimiento":
        """La imputación ya armada, o su diccionario tal como llega por JSON."""
        if isinstance(valor, cls):
            return valor
        if not isinstance(valor, dict):
            raise ImputacionInvalida("Una imputación de movimiento es un objeto: {cuenta_contable, centro_costo, "
                                     "contraparte_doc, cuenta_propia, reparto}")
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(valor) - set(validas))
        if desconocidas:
            raise ImputacionInvalida(f"Claves que no son de una imputación de movimiento: "
                                     f"{', '.join(desconocidas)}. Las que hay: {', '.join(validas)}")
        return cls(**{nombre: valor.get(nombre) for nombre in validas if nombre in valor})


def efecto_de(movimiento, imputacion=None) -> str:
    """Qué le hace al efectivo este movimiento, **compuesto** con lo que el ERP decidió: los tres del catálogo.

    Es la pieza que faltaba, y por eso entra aquí y no en `Movimiento`. `Movimiento.efecto` nunca devuelve
    `transferencia`, y hace bien: una línea sola no puede saber que es la mitad de un traspaso, porque eso es una
    afirmación sobre un **par** y el extracto no la hace. Pero mientras nadie compusiera las dos cosas, el catálogo
    publicaba tres efectos y solo dos tenían quien los emitiera — un valor que nadie podía producir.

    El tercero **no se deriva: se declara**, con `cuenta_propia`, que es la única vía por la que alguien afirma que
    las dos patas son suyas. La otra forma de saberlo es `conciliar`, emparejando las dos (el hito D3), y ésa
    **propone y nunca confirma**.

    Para qué sirve: la NIC 7 §9 deja fuera de los flujos de efectivo los traspasos entre partidas que ya son
    efectivo, porque son gestión de tesorería y no actividad de la empresa. Un ERP que arme su estado de flujos
    llama a esto para excluirlos y no contar dos veces el mismo dinero."""
    if imputacion is not None and ImputacionDeMovimiento.de(imputacion).es_traspaso:
        return TRANSFERENCIA
    return movimiento.efecto


def leer(imputaciones, movimientos) -> dict:
    """El bloque, por el `id_externo` del movimiento, con lo que no cuadra dicho por su nombre.

    **Una llave que no es de ningún movimiento se rechaza.** Es la misma puerta que `preparacion.con_imputacion`
    pone para los comprobantes y por el mismo motivo: una llave mal escrita dejaría ese movimiento sin su cuenta y
    **sin aviso**, que es la clase de error que no se ve hasta el cierre.

    Se contrasta contra los movimientos **tal como llegaron**, antes de deduplicar: si una relectura descarta el
    movimiento al que apuntaba una llave, la llave no deja de ser correcta."""
    if not imputaciones:
        return {}
    if not isinstance(imputaciones, dict):
        raise ImputacionInvalida("`imputaciones_de_movimientos` es un objeto: {id_externo: {cuenta_contable, …}}")
    leidas = {str(k): ImputacionDeMovimiento.de(v) for k, v in imputaciones.items()}
    ids = {str(getattr(m, "id_externo", "") or "").strip() for m in movimientos or ()}
    huerfanas = sorted(set(leidas) - (ids - {""}))
    if huerfanas:
        raise ImputacionInvalida(
            f"La imputación habla de movimientos que no están (id_externo): {', '.join(huerfanas)}.")
    for m in movimientos or ():
        suya = leidas.get(str(getattr(m, "id_externo", "") or "").strip())
        if suya is not None:
            suya.exigir_que_sume(m.importe, cual=(m.constancia or m.referencia or m.id_externo))
    return leidas
