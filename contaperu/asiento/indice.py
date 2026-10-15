"""El índice del asiento: qué líneas son de qué comprobante, con la cabecera de hechos de cada uno (1.0).

Las líneas del comprobante llevan la contabilidad y nada más, y así la huella solo cambia si cambia un asiento. Pero un sistema
contable escribe cada fila con hechos del COMPROBANTE que ninguna línea guarda: la glosa de la cabecera, la tasa del IGV
calculada desde su base y su IGV —y no desde la tasa de la línea, que ya viene redondeada—, el documento de la
contraparte, el `id_externo` con el que la aplicación lo reconoce. El índice los lleva al lado de las líneas, fuera de
ellas y fuera de la huella:

    lineas, rangos, indice = asiento.lineas_e_indice_del_libro(libro, comprobantes, config, correlativos)
    for entrada in indice:
        filas = proyectar(entrada.cabecera, entrada.lineas(lineas))

Lo recibe el driver de asientos que lo acepta (`desde_lineas(..., *, indice=())`, `drivers.contrato.acepta_indice`),
y es de donde sale lo que la respuesta dice de cada comprobante. Todo va en texto, como en el estándar: un importe es
su `Decimal` escrito, sin redondear nada.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from ..modelo import Libro, clave_de, identidad_de
from ..tesoreria import clave_de as clave_de_movimiento
from .huella import huella
from .lineas import LineaDiario


# Las seis claves de la detracción que declara el estándar (`$defs/detraccion`, `additionalProperties: false`).
# Por eso la cabecera FILTRA en vez de copiar el bloque (`motor._detraccion_del_estandar`): si no, el documento que
# produce un driver fallaría su propio esquema en cuanto el bloque llevara algo de más, y puede llevarlo porque un
# `Comprobante` no vigila las claves de ese dict. Lo que SÍ pasa el filtro, además de estas siete, son las anotaciones
# del motor con guion bajo —`_tasa_tabla`, la tasa del Catálogo 54 con la que se calculó el monto—: el bloque las
# admite desde la 4.0 (enmienda 0019), y hasta la 3.10 se llamaba `tasa_tabla` y se quedaba en esta frontera.
# `estado` era la séptima y salió en la 2.0: su propia descripción decía que quien lee el documento NO se fía de
# él, y el motor no lo escribía nunca. El estado se deduce de la constancia y de su fecha, que son los dos datos que
# no se pueden inventar (`tributos.detracciones.estado_de`).
DETRACCION_DEL_ESTANDAR = ("codigo", "porcentaje", "monto", "cuenta", "nro_constancia", "fecha_constancia")


@dataclass(frozen=True)
class Cabecera:
    """Los hechos de un comprobante que un driver necesita al escribir sus filas y que no son de ninguna línea.

    **La regla, desde la 1.4.0: aquí está TODO hecho contable o tributario del comprobante, y ningún dato del
    proceso que lo produjo.** Lo hace cumplir `tests/test_cabecera.py`, que la compara contra el esquema del
    estándar: si el estándar gana un campo, o entra aquí o entra en la lista de los que no son hechos.

    Nació con trece campos, los que CONCAR necesitaba, y eso bastó mientras el único driver de asientos escribía
    contabilidad pura. STARSOFT rompió el supuesto: su plantilla mezcla el asiento con el registro tributario en la
    misma fila, así que pide el destino del IGV, el valor no gravado y los datos de la DUA. Un driver de REGISTRO
    (SIRE, CONTASIS) siempre los tuvo, porque recibe el comprobante entero; uno de ASIENTOS no, y se caían aquí.

    Fuera quedan los siete del proceso —`origen`, `confianza`, `archivo_nombre`, `datos_originales`, `estado`,
    `excluida`, `observaciones`—: dicen de dónde salió el dato y qué opina la validación, no qué pasó. Un driver
    que mirara `confianza` estaría decidiendo contabilidad con la certeza de un modelo de lenguaje.

    Todo en texto, como en el estándar: un importe es su `Decimal` escrito, sin redondear nada.
    """

    # Identificación
    tipo_cp: str = ""
    serie: str = ""
    numero: str = ""
    numero_final: str = ""           # solo rangos: boletas consolidadas del día
    fecha_emision: str = ""
    fecha_vencimiento: str = ""
    condicion_pago: str = ""         # CUÁNDO se paga: contado | credito
    # Las cuotas de una factura al crédito, con su fecha y su importe, ya en texto (enmienda 0030). Están aquí
    # porque la cabecera lleva TODOS los hechos: sin ellas, el documento que escribe un driver del estándar no
    # podría volver a entrar al motor con lo que el papel declaraba, que es la lección de la 3.9.
    cuotas: list = field(default_factory=list)
    monto_pendiente: str = ""        # el monto neto pendiente; vacío = el documento no lo dice, y no es cero
    medio_pago: str = ""             # CON QUÉ se paga: el código de SUNAT (`catalogos.MEDIOS_PAGO`)
    id_externo: str = ""
    # Contraparte
    contraparte_tipo_doc: str = ""   # tipo de documento de identidad: 6 RUC, 1 DNI, 4 CE, 7 pasaporte
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    concepto: str = ""               # lo que dice el comprobante que se compró o se vendió, tal cual
    # Importes
    moneda: str = ""
    tipo_cambio: str = ""
    base_gravada: str = "0"
    igv: str = "0"
    dscto_base: str = "0"            # qué parte de la base informa el SIRE como descuento; no resta al total
    dscto_igv: str = "0"
    exonerado: str = "0"
    inafecto: str = "0"
    exportacion: str = "0"
    isc: str = "0"
    base_ivap: str = "0"
    ivap: str = "0"
    icbper: str = "0"
    otros: str = "0"
    dscto_otros: str = "0"           # la parte de `otros` que el registro informa en negativo (resta del total)
    total: str = "0"
    retencion: str = "0"             # la de renta de 4ta que MUESTRA el recibo por honorarios
    # Solo compras
    destino_igv: str = "DG"          # DG gravadas | DGNG mixtas | DNG no gravadas
    valor_no_gravado: str = "0"      # YA RESUELTO: si el comprobante no lo trae, exonerado + inafecto
    anio_dua: str = ""
    cod_dep_aduanera: str = ""
    clasif_bienes: str = ""
    id_contrato: str = ""
    # Solo notas: por qué se emitió (el Catálogo 09 si es de crédito y el 10 si es de débito). Está aquí y no en el
    # bloque `referencia` de la línea porque no describe el comprobante MODIFICADO, sino la nota misma.
    tipo_nota: str = ""
    # Y CUÁL modifica: el comprobante al que apunta la nota. Viaja también en el bloque `referencia` de cada línea;
    # aquí está porque es un hecho del comprobante y la cabecera lleva todos, y porque quien escribe el documento del
    # estándar lo necesita sin tener que recomponerlo de una línea (`referencia.serie_numero` va unido por el guion).
    ref_tipo_cp: str = ""
    ref_serie: str = ""
    ref_numero: str = ""
    ref_fecha: str = ""
    # La detracción del comprobante: las claves del estándar (`DETRACCION_DEL_ESTANDAR`) y las anotaciones `_` del
    # motor, que el bloque admite desde la 4.0. Incluye la `cuenta` del Banco de la Nación, que ninguna línea lleva.
    detraccion: dict = field(default_factory=dict)

    @property
    def glosa(self) -> str:
        """Lo que se escribe en la columna de descripción: el concepto del comprobante y, si viene vacío, el nombre
        de la contraparte, en mayúsculas y sin cortar (el corte es de cada driver).

        Es una PROPIEDAD y no un campo desde la 3.9, por dos razones. No es un hecho del comprobante —es un derivado
        del `concepto`, que sí lo es— y el estándar no la declara, así que mientras fue campo era lo único que
        impedía que `a_dict()` fuese un comprobante del estándar. Y siendo derivada no puede discrepar de su fuente,
        que es lo que pasaba al construir una cabecera a mano con una glosa cualquiera.

        La misma regla que `asiento.glosa_de`, sobre los datos que la cabecera ya tiene."""
        return ((self.concepto or "").strip() or (self.contraparte_nombre or "").strip()).upper()

    def a_dict(self) -> dict:
        """Todos los campos, más la `glosa` derivada, que es la que un driver escribe en su columna.

        Lleva lo vacío a propósito: `tests/test_driver_diario_json.py` fija que un driver reciba la lista completa de
        hechos aunque este comprobante no traiga alguno. Para escribir un comprobante del estándar, `como_comprobante`.
        """
        return {**asdict(self), "glosa": self.glosa}

    def como_entrada(self) -> dict:
        """Lo mismo que `como_comprobante`, por el nombre que no dice cuál de las dos cabeceras es (ver
        `CabeceraDeMovimiento.como_entrada`)."""
        return self.como_comprobante()

    def como_comprobante(self) -> dict:
        """Esta cabecera como un `comprobante` del estándar, listo para el bloque `comprobantes` de un documento.

        Dos diferencias con `a_dict()`, y las dos son lo que hace que el resultado valide: **fuera la `glosa`**, que
        el estándar no declara porque es un derivado del concepto, y **fuera lo vacío**, porque una cadena vacía no
        pasa el `pattern` de `moneda` ni el `enum` de `contraparte_tipo_doc` — el estándar distingue «no lo sé» de
        «es esto», y lo primero se dice omitiendo la clave.

        La lista vacía entra en lo vacío por lo mismo: un comprobante al contado no declara cuotas, y escribir
        `"cuotas": []` diría «no tiene ninguna» donde lo cierto es «el documento no habla de eso».

        `tests/test_cabecera.py` lo comprueba contra el esquema publicado, campo a campo."""
        return {k: v for k, v in asdict(self).items() if v not in ("", None, {}, [])}


    @property
    def clave(self) -> tuple[str, str, str, str]:
        """La misma identidad de duplicados que `Comprobante.clave`, calculada con la misma función.

        La tiene para que `modelo.identidad_de` —que solo lee `.clave`— sirva igual para un comprobante y para la
        cabecera de su tramo. Sin esto, quien tiene el índice y no los comprobantes —un driver— tendría que
        rehacer la normalización del número y del documento, que es de donde salen los duplicados."""
        return clave_de(self.tipo_cp, self.serie, self.numero, self.contraparte_doc)


@dataclass(frozen=True)
class ComprobanteDelAsiento:
    """Un comprobante dentro del asiento del libro: su posición entre los que salieron, su sub-diario y su correlativo,
    el tramo de líneas que le toca (`desde` incluido, `hasta` excluido) y su cabecera."""

    posicion: int
    sub_diario: str
    correlativo: str
    desde: int
    hasta: int
    cabecera: Cabecera

    def lineas(self, todas: Sequence[LineaDiario]) -> list[LineaDiario]:
        """Las líneas de este comprobante dentro de las del libro."""
        return list(todas[self.desde:self.hasta])

    def a_dict(self) -> dict:
        return {"posicion": self.posicion, "sub_diario": self.sub_diario, "correlativo": self.correlativo,
                "lineas": [self.desde, self.hasta], "cabecera": self.cabecera.a_dict()}

    def identidad(self, libro: Libro) -> dict:
        """Con qué se reconoce este tramo si el documento vuelve a aparecer.

        La pregunta la contesta la ENTRADA y no `exportacion_de`, que es lo que permite que la misma función sirva
        para un comprobante y para un movimiento: cada uno sabe cómo se nombra, y el de arriba no tiene que saberlo.
        """
        return identidad_de(libro, self.cabecera)


@dataclass(frozen=True)
class CabeceraDeMovimiento:
    """Los hechos de un movimiento que un driver necesita al lado de sus líneas, y que ninguna línea guarda.

    Gemela de `Cabecera` y **no una reutilización**: aquélla está anclada campo a campo contra el `$defs/comprobante`
    del estándar, así que meter un movimiento dentro haría que `como_comprobante()` escribiera un comprobante que no
    existe. Aquí la promesa es la misma con el otro papel: todo hecho del movimiento, ningún dato del proceso —fuera
    quedan `origen`, `confianza`, `datos_originales` y las `referencias`, que son lo que el papel dice que cancela y
    no lo que se asentó—.

    Todo en texto, como en el estándar."""

    cuenta: str = ""                 # el `id` de la cuenta en el maestro, que es como un movimiento la nombra
    cuenta_contable: str = ""        # y la 104 con la que se asentó, que sale del maestro y no del movimiento
    fecha: str = ""
    fecha_valor: str = ""
    descripcion: str = ""            # el texto del banco, no la glosa del libro
    importe: str = "0"
    sentido: str = ""                # cargo | abono, lo que dice el papel
    efecto: str = ""                 # entrada | salida | transferencia, ya compuesto con su imputación
    moneda: str = ""
    referencia: str = ""             # el número que dio el banco
    constancia: str = ""             # el número del papel que lo prueba
    contraparte_tipo_doc: str = ""
    contraparte_doc: str = ""
    contraparte_nombre: str = ""
    medio_pago: str = ""
    itf: str = ""                    # vacío no es cero: es «el banco no lo dice»
    id_externo: str = ""

    def a_dict(self) -> dict:
        """Todos los campos, también los vacíos: un driver recibe la lista completa de hechos para saber que existen.
        Para escribir un movimiento del estándar, `como_movimiento`."""
        return asdict(self)

    def como_movimiento(self) -> dict:
        """Esta cabecera como un `movimiento` del estándar, listo para el bloque `movimientos` de un documento.

        Espejo de `Cabecera.como_comprobante`, y con sus dos mismas diferencias: **fuera lo vacío**, porque el
        estándar distingue «no lo sé» de «es esto» y lo primero se dice omitiendo la clave; y **fuera lo que el
        estándar no declara**, que aquí es `cuenta_contable` —la 104 sale del maestro de cuentas, no del
        movimiento— y `efecto`, que es derivado (`tesoreria.efecto_de`)."""
        fuera = {"cuenta_contable", "efecto"}
        return {k: v for k, v in asdict(self).items() if k not in fuera and v not in ("", None, {}, [])}

    def como_entrada(self) -> dict:
        """Lo mismo que `como_movimiento`, por el nombre que no dice cuál de las dos cabeceras es.

        Existe para que quien escribe el documento del estándar no tenga que preguntar de qué libro viene: la
        clave del bloque la da `entradas_de` desde la tabla, y el contenido lo da el objeto. Las dos de una vez,
        y ni un `if` en el driver."""
        return self.como_movimiento()

    @property
    def clave(self) -> tuple:
        """La misma identidad de duplicados que `Movimiento.clave`, calculada con la misma función."""
        return clave_de_movimiento(self.cuenta, self.referencia, self.fecha, self.sentido, self.importe,
                                   self.descripcion)


@dataclass(frozen=True)
class MovimientoDelAsiento:
    """Un movimiento dentro del asiento del libro. Misma forma que `ComprobanteDelAsiento`, para que `desde`,
    `hasta` y `lineas()` sigan sirviendo sin que nadie tenga que saber de cuál de los dos se trata."""

    posicion: int
    sub_diario: str
    correlativo: str
    desde: int
    hasta: int
    cabecera: CabeceraDeMovimiento

    def lineas(self, todas: Sequence[LineaDiario]) -> list[LineaDiario]:
        return list(todas[self.desde:self.hasta])

    def a_dict(self) -> dict:
        return {"posicion": self.posicion, "sub_diario": self.sub_diario, "correlativo": self.correlativo,
                "lineas": [self.desde, self.hasta], "cabecera": self.cabecera.a_dict()}

    def identidad(self, libro: Libro) -> dict:
        return identidad_de_movimiento(libro, self.cabecera)


def identidad_de_movimiento(libro: Libro, m: Any) -> dict:
    """La identidad estable de un movimiento: **su `clave` escrita**, con el RUC y el libro delante.

    Dos ramas, las mismas dos de `tesoreria.clave_de`: con el número que dio el banco basta ese número, y sin él
    hacen falta la fecha, el sentido, el importe y el texto. Un test comprueba que este diccionario reconstruye esa
    tupla, para que no puedan separarse."""
    cuenta = str(_de(m, "cuenta") or "")
    referencia = str(_de(m, "referencia") or "")
    base = {"ruc": libro.ruc, "libro": libro.tipo, "cuenta": cuenta}
    if referencia:
        return {**base, "referencia": referencia}
    return {**base, "fecha": str(_de(m, "fecha") or ""), "sentido": str(_de(m, "sentido") or ""),
            "importe": str(_de(m, "importe") or ""), "descripcion": str(_de(m, "descripcion") or "")}


def _de(cosa: Any, nombre: str) -> Any:
    return cosa.get(nombre) if isinstance(cosa, dict) else getattr(cosa, nombre, None)


def exportacion_de(libro: Libro, lineas: Sequence[LineaDiario], indice: Sequence[Any]) -> dict:
    """Lo que hay que saber de un asiento para reconocerlo después: su huella y, por comprobante, su identidad, el
    tramo de líneas que le toca (`[desde, hasta)`) y la huella de ese tramo. Los tramos parten las líneas sin dejar
    hueco ni solaparse.

    Se arma aquí, y no en la capa de respuesta, porque **quien lo necesita lo tiene en la mano en dos sitios**: la
    respuesta del API lo pone en `_exportacion`, y un driver que escriba el documento del estándar puede llevarlo
    dentro del archivo, que es lo que el estándar admite en su raíz (`estandar/LEEME.md`, las claves `_`). Hasta la
    3.1 vivía solo en `pipeline/salida.py` y el archivo salía sin ello: quien recibiera el JSON a secas se quedaba
    sin la clave con la que no repetir un comprobante."""
    return {"huella": huella(lineas),
            # **La clave la dice la tabla**, y para eso `RASGOS.origen` es singular: `comprobantes` en una compra o
            # una venta, `movimientos` en tesorería. No es cosmética — quien lee la respuesta sabe qué hay dentro
            # sin mirar, y el día que entre un libro más no hay que decidirlo otra vez.
            libro.rasgos.origen: [{"identidad": entrada.identidad(libro),
                                   "lineas": [entrada.desde, entrada.hasta],
                                   "huella": huella(entrada.lineas(lineas))} for entrada in indice]}


def entradas_de(libro: Libro, indice: Sequence[Any]) -> dict:
    """El bloque del documento del que salió este asiento, bajo su propia clave: `{"comprobantes": [...]}` o
    `{"movimientos": [...]}`.

    Es lo que un driver que escriba el documento del estándar necesita para que su archivo **se baste**, y existe
    aquí por lo mismo que `exportacion_de`: la clave la dice la tabla (`RASGOS.origen`) y el contenido lo dice cada
    cabecera (`como_entrada`), así que el driver no tiene que preguntar de qué libro viene. Se devuelve un
    diccionario de una clave, y no la lista, para que se desempaquete con `**` donde se escribe el documento.
    """
    return {libro.rasgos.origen: [entrada.cabecera.como_entrada() for entrada in indice]}
