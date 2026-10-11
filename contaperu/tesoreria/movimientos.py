"""Un item de operación de tesorería: el dinero moviéndose en una cuenta del contribuyente.

**Es la única entrada de un libro de tesorería**, igual que `comprobantes[]` es la única de una compra o de una
venta (John, 11-oct-2026): *«el ERP como producto final puede recibir una constancia de pago o un estado de cuenta,
pero al motor solo llega como item de operación… solo debe haber una entrada para tesorería»*.

Hasta la 2.0 del estándar había dos bloques, `movimientos[]` y `constancias[]`, y los tres argumentos con que se
justificaron no sobrevivieron a mirarlos:

- «Son hechos de testigos distintos» — **el motor ya tenía la respuesta**: el testigo es el campo `origen`, que el
  comprobante usa desde siempre. Una factura leída de un XML y una leída de una foto son la misma forma con otro
  `origen`; una operación bancaria leída de un extracto y una leída de una constancia, también.
- «Las cardinalidades no cuadran: un cargo paga un lote de detracciones» — **confunde un uno-a-muchos dentro de un
  item con necesitar dos bloques**. Lo resuelve `referencias`, aquí dentro.
- «Los ciclos de vida difieren: una constancia existe semanas antes del extracto» — **eso es del ERP**. Al motor
  llega lo que haya, y un movimiento sin `saldo` y sin `referencia` del banco **ES** un pago cuyo extracto no ha
  llegado.

Y lo dice además la tabla de rasgos, que ya era así: `RASGOS.origen` es **singular** —`venta`→`comprobantes`,
`compra`→`comprobantes`, `tesoreria`→`movimientos`—, así que `constancias[]` era un bloque huérfano que no era el
origen de ningún libro.

**La forma salió de nueve extractos reales de producción**, de agosto de 2026, de tres bancos que abren —BBVA,
Scotiabank y BanBif—. Lo que tienen los tres: la cuenta con su CCI, una moneda, un periodo en la cabecera, y por
línea la fecha de operación, la fecha valor, una descripción, el importe y el saldo corrido.

Lo que **no** comparten, y que esta clase normaliza:

- **El signo.** BBVA trae una sola columna con el importe negativo cuando es un cargo; Scotiabank y BanBif traen
  dos columnas. Aquí el importe es **siempre positivo** y el sentido va aparte, que es la misma regla que ya rige
  en `LineaDiario.debe_haber` y en el par `otros` / `dscto_otros` del comprobante.
- **El ITF.** BBVA lo da **en una columna de la línea** y un total al pie; Scotiabank lo da como **un movimiento
  propio** («IMPUESTO A LOS DÉBITOS»); en el extracto de BanBif no aparece. Aquí cabe de las dos formas: como campo
  cuando el banco lo adjunta, y como un movimiento más cuando el banco lo asienta aparte. **Y nunca se calcula**:
  lo da el banco. Lo que falta para asentarlo es su norma, que es el hito D6.
- **El año.** Las líneas traen día y mes (`03-08`); el año está en la cabecera. Quien lee el archivo lo baja: aquí
  llega ya completo, porque el núcleo no tiene reloj con el que adivinarlo.

Lo que cada banco da y nadie más —el `ORIG` de Scotiabank, el `CAN` y la oficina de BBVA— viaja en
`datos_originales` sin interpretar, igual que en el comprobante.

**Lo que NO está aquí: la cuenta contable de la contrapartida.** La 104 sale de la cuenta bancaria que el
contribuyente declaró —aquí solo se apunta a ella por su `id`— y la otra cara llega en
`imputaciones_de_movimientos`, igual que la cuenta de un gasto. Es la doctrina de `asiento.resolucion.imputado`:
sin imputación no hay cuenta. Y tiene una consecuencia práctica: dos lecturas del mismo movimiento comparten
`clave` y `sin_duplicados` se queda con la primera, así que una cuenta corregida en la segunda se perdería.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import date

from ..errores import ErrorContaperu
from ..modelo import CERO, fecha as _fecha, monto as _monto
from .referencias import Referencia

# Hacia dónde va el dinero, visto desde MI cuenta. Son las dos palabras que los tres bancos usan, con sus sinónimos:
# BBVA titula la columna «CARGO/ABONO», Scotiabank «CARGO | ABONO» y BanBif «Débito | Crédito».
# Lo que imprime el extracto, con las palabras del banco. Son las mismas dos del `CdtDbtInd` de camt.053
# (`CRDT`/`DBIT`) y del subcampo C/D del tag 61 de un MT940: el importe va positivo y el signo lo lleva esto.
CARGO = "cargo"
ABONO = "abono"
SENTIDOS = (CARGO, ABONO)

# Y el EFECTO sobre el efectivo, que es otra cosa y por eso tiene otras palabras. Son las de la NIC 7: «Flujos de
# efectivo son las **entradas y salidas** de efectivo y equivalentes al efectivo» —versión en español del IFRS
# Foundation, la que publica el MEF del Perú—. Se nombran aquí para que nadie escriba la cadena a mano, y
# `tests/test_tesoreria.py` las ancla al catálogo publicado: dos listas que dicen lo mismo en dos sitios acaban
# diciendo cosas distintas.
#
# **Ojo con el cambio de perspectiva, que es la trampa de todo esto.** El banco escribe `abono` porque en SUS
# libros tu depósito es un pasivo que le crece; en los TUYOS esa misma plata entra a un activo. Así que un abono es
# una ENTRADA y va al DEBE, y un cargo es una SALIDA y va al HABER. Quien lo lea al revés invierte el asiento
# entero sin que nada falle.
ENTRADA = "entrada"
SALIDA = "salida"
# El tercero del catálogo se nombra aquí, con los otros dos, por la misma razón: que nadie escriba la cadena a
# mano. Pero **no entra en `EFECTOS_DE_UN_MOVIMIENTO` a propósito**, porque un movimiento solo no puede tenerlo
# (el porqué, en `Movimiento.efecto`). Quien lo produce es `imputaciones.efecto_de`, componiendo el movimiento con
# lo que el ERP declaró. **Hasta la 12.0 no lo producía nadie**: el catálogo publicaba tres efectos y solo dos
# tenían emisor, que es un valor que nadie podía emitir.
TRANSFERENCIA = "transferencia"
EFECTOS_DE_UN_MOVIMIENTO = (ENTRADA, SALIDA)


# De dónde salió el dato. **Lista propia y no la del comprobante** —cuyos valores son `xml`, `pdf_texto`,
# `vision`, `manual` y `sire`—: un `xml` o una propuesta del SIRE no son cosas de un banco, y aceptarlos sería
# inventar, que es lo contrario de «mejor fallar que inventar». Lo que sí se comparte son los dos nombres que
# significan exactamente lo mismo, `pdf_texto` y `vision`, **que son los dos que marcan lectura asistida**.
MANUAL = "manual"        # lo escribió una persona
ARCHIVO = "archivo"      # salió de un archivo estructurado del banco: un CSV, un XLSX, un MT940
API = "api"              # lo dio el banco por su API
PDF_TEXTO = "pdf_texto"  # se extrajo del texto de un PDF
VISION = "vision"        # lo leyó un modelo de una imagen
ORIGENES = (MANUAL, ARCHIVO, API, PDF_TEXTO, VISION)
# Los dos que piden que alguien lo mire. Es lo que alimenta `de_lectura_asistida`, y **la confianza no relaja
# ninguna comprobación**: el cuadre es el mismo, porque la investigación de 2026 encuentra que la confianza que
# reporta un modelo no separa de forma fiable lo correcto de lo incorrecto.
LECTURA_ASISTIDA = (PDF_TEXTO, VISION)

# Lo que dice que esto vino de un EXTRACTO no es una etiqueta: es el `saldo`, que solo un extracto trae. Es la
# lección del `rol` aplicada aquí — lo que se deriva no es un campo.


class MovimientoInvalido(ErrorContaperu, ValueError):
    """Una línea de extracto que no se puede usar. Dice cuál y por qué, y no la arregla."""


@dataclass
class Movimiento:
    """Una línea del estado de cuenta, normalizada."""

    cuenta: str = ""                    # el `id` de la cuenta en `cuentas_bancarias`, no un número suelto
    fecha: date | None = None           # la de la operación
    fecha_valor: date | None = None     # cuándo cuenta para el saldo; los tres bancos la dan y casi siempre coincide
    descripcion: str = ""
    importe: object = CERO              # SIEMPRE positivo: el signo lo dice `sentido`
    sentido: str = ""
    moneda: str = ""
    saldo: object = None                # el saldo corrido DESPUÉS de esta línea; None si el banco no lo da
    referencia: str = ""                # el número que pone el BANCO: `N° OPER` en BBVA, `REFERENCIA` en Scotiabank
    itf: object = None                  # cuando el banco lo adjunta a la línea (BBVA). None no es cero: es «no dice»
    # ── Lo que absorbió de la constancia en la 3.0 del estándar ──────────────────────────────────────────────
    # El número del PAPEL que prueba el pago: el vóucher del Banco de la Nación, el comprobante de una
    # transferencia. **Es un campo aparte de `referencia` porque los dos existen y son distintos**: una detracción
    # pagada desde BBVA tiene su `N° OPER` del banco y su vóucher del BN. Y es el que el hito D1 escribe en el
    # `detraccion.nro_constancia` del comprobante, así que confundirlos rompería ese enlace.
    constancia: str = ""
    # A quién se le pagó o de quién se cobró, **cuando el papel lo dice** —un extracto no lo trae: su descripción
    # es texto libre y leerla es conjetura—. Con **los mismos tres nombres que un comprobante**, no como un
    # `beneficiario{}`: CONCAR llena su anexo auxiliar desde `contraparte_doc` y el tramo 3 de `kit.rol` decide por
    # ese campo, así que el mismo nombre ahorra una traducción y un segundo vocabulario.
    contraparte_tipo_doc: str = ""
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    medio_pago: str = ""                # Tabla 1 del Anexo 3 de la RS 169-2015, el mismo catálogo que el comprobante
    referencias: list = field(default_factory=list)   # qué cancela, cuando el papel lo dice
    origen: str = ""                    # ver ORIGENES
    confianza: object = None            # por debajo de 1 solo tiene sentido en lo que leyó un modelo
    # ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    id_externo: str = ""                # el de quien integra, para reconocerlo cuando vuelva
    datos_originales: dict | None = None

    def __post_init__(self) -> None:
        self.cuenta = str(self.cuenta or "").strip()
        self.descripcion = " ".join(str(self.descripcion or "").split())
        self.sentido = str(self.sentido or "").strip().lower()
        self.moneda = str(self.moneda or "").strip().upper()
        self.referencia = str(self.referencia or "").strip()
        self.constancia = str(self.constancia or "").strip()
        self.contraparte_tipo_doc = str(self.contraparte_tipo_doc or "").strip()
        self.contraparte_doc = str(self.contraparte_doc or "").strip().upper()
        self.contraparte_nombre = " ".join(str(self.contraparte_nombre or "").split())
        self.medio_pago = re.sub(r"[^0-9]", "", str(self.medio_pago or ""))
        self.origen = str(self.origen or "").strip().lower()
        self.referencias = [r if isinstance(r, Referencia) else Referencia(**dict(r)) for r in (self.referencias or [])]
        self.id_externo = str(self.id_externo or "").strip()
        self.fecha = _fecha(self.fecha)
        self.fecha_valor = _fecha(self.fecha_valor) or self.fecha
        self.importe = _monto(self.importe)
        # Los dos opcionales que son importes: **vacío es `None`, no la cadena vacía**, que es lo que significa
        # «el banco no lo dice». Hasta la 12.0 un `""` se quedaba dentro tal cual y `cuadra()` reventaba con un
        # `TypeError` al restarlo — y mandar la clave vacía es lo normal en un ERP que serializa su tabla. Es la
        # forma que `Extracto` ya tenía bien para sus cuatro saldos.
        for campo in ("saldo", "itf"):
            valor = getattr(self, campo)
            setattr(self, campo, _monto(valor) if valor is not None and valor != "" else None)
        if not self.cuenta:
            raise MovimientoInvalido("Un movimiento necesita la cuenta a la que pertenece")
        if self.fecha is None:
            raise MovimientoInvalido(f"Movimiento sin fecha en la cuenta {self.cuenta!r}: el año lo baja de la "
                                     f"cabecera quien lee el archivo, porque el núcleo no tiene reloj")
        if self.sentido not in SENTIDOS:
            raise MovimientoInvalido(f"Sentido inválido en la cuenta {self.cuenta!r}: {self.sentido!r} "
                                     f"({' | '.join(SENTIDOS)})")
        # **Un `origen` desconocido para**, y es un cambio de comportamiento de la 3.0: hasta aquí se pasaba a
        # minúsculas y se aceptaba. El daño era concreto y silencioso — un `origen: "ocr"` dejaba de salir en
        # `de_lectura_asistida`, o sea que **lo que leyó un modelo dejaba de pedir revisión sin que nada lo
        # dijera**. Es el mismo trato que `Comprobante` le da al suyo: mejor fallar que inventar.
        if self.origen and self.origen not in ORIGENES:
            raise MovimientoInvalido(f"Origen inválido en la cuenta {self.cuenta!r}: {self.origen!r} "
                                     f"({' | '.join(ORIGENES)})")
        # **No se puede repartir más de lo que se movió**, y esto sí es un error y no un reporte. Lo que queda sin
        # reclamar se informa y no se cierra (`sin_atribuir`), porque decidir qué es ese resto es del contador; pero
        # reclamar 5 000 de un pago de 4 000 no es un juicio contable, es una suma que no cuadra. Es la puerta
        # equivalente a la cadena de saldos: la que hace verificable lo que leyó un modelo.
        if self.repartido > self.importe:
            raise MovimientoInvalido(
                f"Las referencias del movimiento {self.referencia or self.constancia or self.descripcion!r} "
                f"reclaman {self.repartido} de un pago de {self.importe}: no se puede repartir más de lo que se "
                f"movió. Lo que sobra sí se puede dejar sin reclamar — eso se informa en `sin_atribuir` y no es un "
                f"error.")
        # No hay comprobación de importe negativo, y no es un olvido: `modelo.monto` **ya devuelve el valor
        # absoluto** —«el signo no es parte del dato»—, así que un `-200.00` de una columna con signo llega aquí
        # convertido. Eso es lo que hace falta: el lector mira el signo de la columna para poner `sentido` y pasa
        # el importe tal cual. Un `if importe < 0` aquí sería código que no puede ejecutarse nunca.

    @property
    def efecto(self) -> str:
        """Qué le hace esta línea al efectivo: `entrada` o `salida`, con las palabras de la NIC 7.

        **Derivado y no almacenado**, para que no puedan discrepar: el dato que un lector transcribe del archivo es
        el indicador del banco, y esto es su consecuencia contable. Un abono entra —el efectivo va al debe— y un
        cargo sale —al haber—.

        **Nunca devuelve `transferencia`, y es la decisión que sostiene el modelo.** El catálogo tiene ese tercer
        efecto porque la NIC 7 §9 excluye de los flujos los traspasos entre partidas de efectivo, así que hay que
        poder nombrarlo para dejarlo fuera y no contarlo dos veces. Pero **una línea sola no puede saber que es la
        mitad de un traspaso**: eso es una afirmación sobre un PAR —un cargo en una cuenta y un abono en otra— y el
        extracto no lo dice. Se declara, cuando una constancia lo afirma con una referencia `cuenta_propia`, o se
        propone, cuando `conciliar` empareja las dos patas; y `conciliar` propone y nunca confirma. Derivarlo aquí
        sería dejar que un lector de un extracto afirme algo que no ha visto.

        Es la misma forma que tienen los ERP abiertos, con el nivel bien puesto: Odoo y ERPNext ponen los tres
        valores en el PAGO (`payment_type`: inbound/outbound/transfer, Receive/Pay/Internal Transfer) y el
        indicador de dos valores en la línea del extracto."""
        return SALIDA if self.es_cargo else ENTRADA

    @property
    def es_cargo(self) -> bool:
        return self.sentido == CARGO

    @property
    def repartido(self) -> object:
        """Lo que las referencias dicen cancelar. Una referencia sin importe no suma: vale por el total."""
        return sum((r.importe for r in self.referencias if r.importe not in (None, "")), CERO)

    @property
    def sin_atribuir(self) -> object:
        """Lo que el movimiento cubre y ninguna referencia reclama.

        **No es un error, y por eso no lo levanta nadie.** Un cargo lleva el ITF dentro, y un pago puede cancelar
        algo que el papel no nombra. El motor lo reporta y nunca lo cierra; quién decide qué es ese resto es del
        contador, por la imputación."""
        if not any(r.importe not in (None, "") for r in self.referencias):
            return CERO
        return self.importe - self.repartido

    @property
    def de_lectura_asistida(self) -> bool:
        """Si lo leyó un modelo y por tanto alguien tiene que mirarlo."""
        return self.origen in LECTURA_ASISTIDA

    @property
    def clave(self) -> tuple:
        """La identidad de un movimiento, que es lo que impide duplicar al releer un mes con solape.

        Con la referencia del banco basta y sobra: es suya y no se repite dentro de una cuenta. Sin ella —BanBif no
        la da— se cae a lo que siempre hay: cuenta, fecha, sentido, importe y descripción. **Eso puede colisionar a
        propósito**: dos comisiones idénticas el mismo día son dos movimientos y una sola clave, así que un lector
        sin referencia tiene que desempatar con el orden del archivo. Se dice aquí para que nadie lo descubra
        contando mal."""
        return clave_de(self.cuenta, self.referencia, self.fecha, self.sentido, self.importe, self.descripcion)

    def a_dict(self) -> dict:
        d = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "datos_originales":
                if v:
                    d[f.name] = dict(v)
            elif f.name == "referencias":
                d[f.name] = [r.a_dict() for r in v]
            elif isinstance(v, date):
                d[f.name] = v.isoformat()
            elif v is None:
                d[f.name] = None
            else:
                d[f.name] = str(v) if f.name in ("importe", "saldo", "itf", "confianza") else v
        return d

    @classmethod
    def de_dict(cls, d: dict) -> "Movimiento":
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise MovimientoInvalido(f"Claves que no son de un movimiento: {', '.join(desconocidas)}. "
                                     f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre) for nombre in validas if nombre in d})


def clave_de(cuenta: str, referencia: str, fecha: date | None, sentido: str, importe: object,
             descripcion: str = "") -> tuple:
    """La clave sin construir el objeto, para calcularla desde una fila de una base.

    Es el mismo recurso que `modelo.clave_de` para el comprobante, y por el mismo motivo: quien guarda movimientos
    los deduplica contra lo que ya tiene sin instanciar nada."""
    ref = re.sub(r"\s+", "", str(referencia or ""))
    if ref:
        return (str(cuenta or "").strip(), ref)
    return (str(cuenta or "").strip(), "", fecha, str(sentido or "").lower(), str(importe),
            " ".join(str(descripcion or "").split()).upper())


def sin_duplicados(movimientos: list) -> tuple[list, list]:
    """Separa los que entran de los que ya estaban, por su clave y conservando el orden.

    Devuelve `(nuevos, repetidos)` en vez de filtrar en silencio: releer un mes con solape es lo normal —se baja el
    extracto dos veces— y lo que el que integra necesita saber es **cuántos se descartaron**, no solo cuántos
    quedaron. Es el criterio de salida del hito D2: «una relectura con solape no duplica»."""
    vistas: set[tuple] = set()
    nuevos: list = []
    repetidos: list = []
    for m in movimientos:
        clave = m.clave if isinstance(m, Movimiento) else Movimiento.de_dict(m).clave
        (repetidos if clave in vistas else nuevos).append(m)
        vistas.add(clave)
    return nuevos, repetidos
