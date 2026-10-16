"""El libro: la cabecera de lo que se registra —un RUC, un mes, ventas o compras—.

Es lo primero que se valida de un documento y lo que decide todo lo demás: de su tipo cuelga qué cuentas se usan,
qué sub-diario toca y qué columnas escribe cada driver.

**Y desde la 9.0 eso cuelga de una tabla y no de un booleano**, que es el cambio que rompe. Hasta la 8.x el motor
preguntaba `libro.es_venta` en medio centenar de sitios y usaba `not es_venta` para decir «es compra»: correcto
mientras el catálogo tuviera dos valores, y un error silencioso en cuanto tuviera tres. La 8.2 puso una puerta que
lo paraba; la 9.0 lo arregla, que es distinto — **ahora cada tipo de libro declara lo que el motor necesita saber
de él**, y añadir uno es añadir una fila en vez de auditar cincuenta `if`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from .. import vocabulario
from .coerciones import solo_digitos

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0.
TIPOS_LIBRO = vocabulario.TIPOS_LIBRO


# El valor de `sentido_principal` que dice «esto no lo decide el libro». En ventas el ingreso siempre va al haber
# y en compras el gasto siempre al debe; en tesorería **depende de cada operación**, porque entra o sale dinero de
# una misma cuenta de activo. Es el primer rasgo que no es una constante del libro, y por eso tiene nombre.
POR_OPERACION = "por_operacion"


class SentidoNoLoDiceElLibro(ValueError):
    """Se le pidió al libro un lado que no es suyo: en tesorería lo dice cada operación."""


@dataclass(frozen=True)
class Rasgos:
    """Lo que el motor necesita saber de un libro para armar su asiento, declarado en vez de deducido.

    **Cada campo era un `if es_venta` repartido por el núcleo.** Juntarlos tiene tres efectos que valen la mayor
    que cuesta: se ve de un vistazo en qué se diferencian dos libros, un libro nuevo es una fila, y lo que el
    motor todavía no sabe hacer se nota — porque hay que rellenar el campo y no hay con qué.

    `sentido_principal` es el del HECHO: en una venta el ingreso va al haber, en una compra el gasto va al debe.
    La contraparte va al contrario, y por eso no se declara: se deriva.

    **`roles` es una declaración y no un mapa**, y la distinción costó un intento. Hubo una versión con
    `rol_principal` y `rol_contraparte`, que suponía que todo libro tiene un hecho y una contraparte. En tesorería
    eso no sobrevive: en un pago que cancela una deuda el hecho es el dinero moviéndose, y en una comisión del banco
    el hecho es el gasto y el dinero es la otra cara. Preguntar «cuál es el principal» fuerza una respuesta que a
    veces es mentira. Odoo lo esquiva no preguntándolo —su pago tiene `liquidity`, `counterpart` y `writeoff`, sin
    jerarquía—, y esto hace lo mismo: el libro dice qué roles caben, no cuál manda.

    Quién escribe cada rol en cada línea es de quien genera el asiento, y eso es correcto: el camino del
    comprobante lleva roles de comprobante. La declaración se comprueba **ejecutando el motor y comparando lo que
    sale con lo declarado** (`tests/test_vocabulario.py`), que es una garantía más fuerte que un campo que alguien
    lee."""

    tipo: str

    # ── Qué ES este libro. Es lo que de verdad lo distingue, y por eso va primero (John, 10-oct-2026).
    origen: str                 # de qué bloque del documento salen sus líneas
    roles: tuple[str, ...]      # qué roles pueden aparecer en su asiento. Una DECLARACIÓN, no un mapa
    sentido_principal: str      # 'D' | 'H', o `POR_OPERACION` cuando lo dice cada operación y no el libro
    cuenta_contraparte: str     # la clave de `cuentas` con la que se salda; vacía si no la pone el libro

    # ── Qué reglas le tocan. Las tres son de las compras, y por eso las tres son `False` en lo demás.
    da_credito_fiscal: bool     # el IGV entra como crédito (compras) o como débito del que se recauda (ventas)
    lleva_detraccion: bool
    lleva_honorarios: bool      # el recibo por honorarios y su retención de 4ta

    # ── A dónde va. No es lo que un libro ES sino por dónde sale, y va al final por eso.
    sub_diario: str             # la clave de configuración que nombra su sub-diario
    # Cómo se llama este libro DENTRO del nombre de un archivo: `COMPRAS_202610_<RUC>.xlsx`. Es un rasgo del libro
    # y no de cada driver porque la convención es una sola para todos (`drivers/kit/nombres.py`), y está aquí y no
    # en una tabla aparte porque una tabla paralela a ésta es exactamente lo que la 9.0 vino a quitar: hasta la
    # 12.10 el nombre salía de `'VENTAS' if libro.es_venta else 'COMPRAS'`, el último sitio donde el booleano de
    # antes de la 9.0 seguía decidiendo algo — y habría llamado «COMPRAS» a un archivo de tesorería.
    #
    # En plural donde el uso lo tiene («compras», «ventas») y en singular donde lo tiene («tesorería»): es cómo lo
    # dice un contador, y por eso se declara en vez de derivarse del `tipo`.
    etiqueta_de_archivo: str

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    @property
    def es_compra(self) -> bool:
        return self.tipo == "compra"

    @property
    def decide_la_operacion(self) -> bool:
        """¿El lado del hecho lo dice cada operación en vez del libro? Solo en tesorería, de momento."""
        return self.sentido_principal == POR_OPERACION

    @property
    def sentido_contraparte(self) -> str:
        """Al revés que el hecho, siempre. Es la partida doble, y por eso se deriva en vez de declararse.

        **Y se niega a contestar cuando el lado lo dice la operación.** Hasta aquí la línea era
        `"D" if sentido_principal == "H" else "H"`, que con cualquier valor que no fuera `"H"` devolvía `"H"`: con
        `por_operacion` habría contestado «haber» callada y mal, que es exactamente el fallo que la 9.0 vino a
        cerrar en el otro eje. Un `else` que acierta por casualidad mientras los valores son dos deja de acertar
        en cuanto son tres."""
        if self.decide_la_operacion:
            raise SentidoNoLoDiceElLibro(
                f"En un libro {self.tipo!r} el lado lo dice cada operación, no el libro: una entrada lleva la "
                f"cuenta de efectivo al debe y una salida al haber. Pregúntale a la operación "
                f"(`tesoreria.Movimiento.efecto`) en vez de al libro.")
        return "D" if self.sentido_principal == "H" else "H"


# En qué se diferencia cada tipo de libro del catálogo. **Vuelve a coincidir con `asiento.TIPOS_DEL_MOTOR`** desde
# la 12.8, y el que no coincidieran fue información útil mientras duró: entre el 10-oct-2026 y esa versión esta
# tabla tuvo tres filas y aquella tupla dos, porque el motor sabía qué ES un libro de tesorería y no sabía armar su
# asiento. Un libro que esté aquí y no allí se para en la puerta nombrando los que sí
# (`asiento.LibroQueElMotorNoOrigina`), que es para lo que se puso y que hoy no se dispara nunca — y ése es el
# momento de tenerla, porque el día que el catálogo crezca (B13) lo que falle será eso.
RASGOS: dict[str, "Rasgos"] = {
    # Los roles de cada uno están MEDIDOS ejecutando el motor, no deducidos: una venta y una compra simples dan
    # los tres primeros; una compra con detracción añade `recorte` y `detraccion`; un recibo por honorarios añade
    # `retencion`. De ahí sale `asiento.ROLES_DEL_MOTOR`, que ya no se mantiene a mano.
    "venta": Rasgos(tipo="venta", origen="comprobantes",
                    roles=("principal", "impuesto", "tercero"),
                    sentido_principal="H", cuenta_contraparte="clientes",
                    da_credito_fiscal=False, lleva_detraccion=False, lleva_honorarios=False,
                    sub_diario="sub_diario_ventas", etiqueta_de_archivo="VENTAS"),
    "compra": Rasgos(tipo="compra", origen="comprobantes",
                     roles=("principal", "impuesto", "tercero", "retencion", "recorte", "detraccion"),
                     sentido_principal="D", cuenta_contraparte="cxp",
                     da_credito_fiscal=True, lleva_detraccion=True, lleva_honorarios=True,
                     sub_diario="sub_diario_compras", etiqueta_de_archivo="COMPRAS"),
    # El dinero moviéndose. Dos campos no son constantes aquí, y que la tabla lo enseñe es la mitad de su valor:
    #
    #
    # - `cuenta_contraparte` está **vacía a propósito**: no hay una sola cuenta con la que se salde. Un lado es la
    #   cuenta de efectivo que el contribuyente declaró en su maestro (su 104) y el otro lo pone la imputación,
    #   igual que hoy pone la cuenta de un gasto — «sin imputación no hay cuenta» (`resolucion/imputado.py`). La
    #   única excepción es la `transferencia`, cuyas dos patas son cuentas declaradas.
    # - `sentido_principal` es `POR_OPERACION`: una entrada lleva el efectivo al debe y una salida al haber, así
    #   que el lado es de cada operación. Es el primer rasgo que el libro no puede fijar.
    # - `sub_diario` está vacío porque **su clave de configuración todavía no existe**, y eso es información y no
    #   un hueco: entra con el archivo del sub-diario de bancos que CONCAR haya aceptado, y hasta entonces este
    #   libro se arma pero no se numera (`LibroQueTodaviaNoSeNumera`). Se
    #   intentó declararla ya y el contrato de drivers lo paró con la razón exacta — «una clave que nadie lee se
    #   configura para nada»—, porque hasta que el motor origine este libro nadie puede leerla.
    # Y los roles de tesorería **se declaran vacíos a propósito**, que es la respuesta honesta a «¿cuáles serían?»
    # (John, 10-oct-2026). Hubo un intento de poner `("tesoreria", "contrapartida")` y era una adivinanza
    # disfrazada de dato: el motor no emite ni una línea de tesorería, así que no hay forma de medirlo —las filas de
    # venta y compra SÍ están medidas ejecutándolo—, y además estaba incompleta, porque un pago a proveedor lleva el
    # 42 con el documento del proveedor y eso es `tercero`.
    #
    # **Y la pregunta de si esa línea del 42 es `tercero` o `contrapartida` quedó contestada: es `tercero`**
    # (11-oct-2026). Cuatro argumentos, tres comprobables: el catálogo define `tercero` como «la cuenta del total»,
    # que es justo el saldo que un pago mueve; define `contrapartida` como «la otra cara de un hecho que **no se le
    # debe a nadie**», y un 42 se le debe a alguien; CONCAR llena su anexo auxiliar desde esa línea y
    # `contrato.CENTRO_EN_ANEXO` ya está cableado a `tercero`, así que con el otro la columna no se llenaría nunca;
    # y es **derivable**, porque esa línea lleva `contraparte_doc` y la comisión del banco no.
    #
    # De ahí una corrección: **`contrapartida` no es vocabulario de tesorería.** Su caso real es la depreciación, el
    # asiento de destino y la planilla, o sea el hito B13 — el diario que un ERP nos manda.
    #
    # **Y ese día llegó en la 12.8.** El motor emite su primera línea de tesorería, así que los roles se declaran
    # MEDIDOS, que es lo que esta nota prometía: son `tesoreria`, `tercero` y `principal`, y los tres salen de
    # ejecutarlo. La línea del 42 es `tercero` —contestado el 11-oct— y la del efectivo es `tesoreria`, que la
    # regla distingue por el elemento **10 del PCGE**, «Efectivo y equivalentes al efectivo» (p. 17): es la fuente
    # publicada que dice qué cuenta es dinero, y es palabra por palabra lo que el catálogo del estándar define como
    # ese rol. Lo que no es ninguna de las dos —el gasto de una comisión— es `principal`.
    #
    # **`sub_diario` sigue vacío, y ahora significa otra cosa**: no «este libro no lo origina el motor», sino
    # «este libro todavía no se numera». La distinción la hizo visible tesorería y la comprueba
    # `LibroQueTodaviaNoSeNumera`. La misma disciplina con la que el contrato de drivers paró el
    # `sub_diario_bancos`: una clave que nadie lee se configura para nada.
    # **El Libro Diario (B13, 16-oct-2026): el libro que no se arma, se RECIBE.** Es el tercer caso del eje y la
    # 13.1 no lo había previsto: estrena origen y **no estrena motor**. Sus líneas llegan ya hechas en el bloque
    # `asiento` del documento —que el estándar admite de entrada desde la 1.0 y el motor lee desde la 5.2—, y
    # tienen que llegar así porque armarlas pediría reglas que este motor no tiene ni va a tener: una planilla
    # pide las reglas de la planilla y una depreciación pide el activo y su vida útil.
    #
    # Por qué UN libro y no uno por hecho —`planilla`, `depreciacion`, `destino`—: porque cada uno de esos hechos
    # **ya tiene su libro en la RS 234-2006** —el Registro de Planillas, el de Activos Fijos, el de Costos— y los
    # tres asientan en el mismo Formato 5.1, que es el contenedor genérico. Abrir uno por hecho sería inventar
    # categorías de gasto y llamarlas libros, que es lo que el `honorario` ya intentó y se descartó: `libro` es el
    # libro tributario. Medido en el 5.1 aceptado de un mes real: 1 441 asientos en 19 sub-diarios, de los que
    # unos 530 no son del registro de compras ni del de ventas.
    #
    # Los cinco campos vacíos o falsos dicen lo que el motor no hace con él, que es casi todo, y es correcto:
    # `roles` vacío porque no emite ninguna línea suya —se las dan—, `sub_diario` vacío porque **ya vienen
    # numeradas** por quien las mandó (el CUO es suyo y renumerar le cambiaría el número a un asiento presentado),
    # y las tres reglas de compras no le tocan.
    "diario": Rasgos(tipo="diario", origen="asiento",
                     roles=(), sentido_principal=POR_OPERACION, cuenta_contraparte="",
                     da_credito_fiscal=False, lleva_detraccion=False, lleva_honorarios=False,
                     sub_diario="", etiqueta_de_archivo="DIARIO"),
    "tesoreria": Rasgos(tipo="tesoreria", origen="movimientos",
                        roles=("tesoreria", "tercero", "principal"),
                        sentido_principal=POR_OPERACION, cuenta_contraparte="",
                        da_credito_fiscal=False, lleva_detraccion=False, lleva_honorarios=False,
                        sub_diario="", etiqueta_de_archivo="TESORERIA"),
}


# De qué bloques del documento salen los libros que hay, sin repetir y en el orden del catálogo. Es una COLUMNA de
# la tabla de arriba, no una tabla paralela: no crece con cada libro, sino con cada forma de entrar —hoy dos, y
# tres libros—. Por eso es la clave con la que cada capa decide qué camino toma un libro (`CAMINOS_DEL_ASIENTO` y
# sus hermanas), en lugar de preguntar por el nombre de uno: un libro nuevo que entre por `movimientos` no añade
# una entrada en ninguna de esas tablas, y uno que estrene bloque las pone rojas todas a la vez, que es lo que se
# quiere — estrenar un bloque es escribir un motor, no rellenar una fila.
#
# Vivía calcado en `pipeline/armado.py` y sube aquí porque lo leen tres capas, y el núcleo es la única que las
# tres pueden ver. **No se llama `ORIGENES` a secas** porque esa palabra ya está cogida dos veces para otra cosa
# —de dónde salió un comprobante (`manual`, `archivo`, `api`) y de dónde salió una aplicación—, y son ejes
# distintos que se leerían igual.
ORIGENES_DE_LIBRO: tuple[str, ...] = tuple(dict.fromkeys(r.origen for r in RASGOS.values()))

# El bloque donde van las LÍNEAS de un asiento, que es también el origen de un libro que llega ya armado —el
# Libro Diario—. Tiene nombre propio porque es el único origen que no describe una entrada aparte: las entradas
# de una compra son sus comprobantes y las de tesorería sus movimientos, pero las de un diario **son sus propias
# líneas**, que ya están en la respuesta. De ahí que `armado.por_entrada` no le abra una clave: sería repetir el
# asiento dentro de sí mismo.
ORIGEN_YA_ARMADO = "asiento"


class LibroSinRasgos(ValueError):
    """Se pidieron los rasgos de algo que el motor no CONOCE, o de un booleano de antes de la 9.0.

    No confundir con `asiento.LibroQueElMotorNoOrigina`, que es el otro «no» y hasta el 10-oct-2026 se decía con
    las mismas palabras: éste es «no sé qué es un libro así» y aquél «sé lo que es y no sé armar su asiento». El
    libro de tesorería es justo el caso que los separa, y por eso el mensaje tuvo que cambiar."""


def rasgos_de(libro: Rasgos | Libro | str) -> Rasgos:
    """Los rasgos de lo que sea que te hayan pasado: unos rasgos, un `Libro` o el tipo por su nombre.

    Es generoso a propósito —quien llama pasa lo que tenga— con una excepción que es el motivo de que exista:
    **un `bool` da un error que dice qué hacer**. Hasta la 8.x estas funciones recibían `es_venta`, y un `True`
    que se colara elegiría la rama equivocada en silencio, que es justo lo que la 9.0 viene a quitar."""
    if isinstance(libro, Rasgos):
        return libro
    if isinstance(libro, bool):
        cual = "venta" if libro else "compra"
        raise LibroSinRasgos(
            f"Esto recibía `es_venta: bool` hasta la 8.x y desde la 9.0 recibe los rasgos del libro. "
            f"En vez de {libro!r}, pasa `libro.rasgos`, o `modelo.RASGOS[{cual!r}]` si no tienes el libro.")
    tipo = getattr(libro, "tipo", libro)
    rasgos = RASGOS.get(str(tipo or "").strip().lower())
    if rasgos is None:
        raise LibroSinRasgos(f"El motor no conoce ningún libro de tipo {tipo!r}: "
                             f"conoce {', '.join(sorted(RASGOS))}")
    return rasgos


@dataclass
class Libro:
    """El registro que se genera: un RUC, un mes, ventas o compras."""

    ruc: str
    razon_social: str
    periodo: str  # 'AAAAMM'
    tipo: str     # 'venta' | 'compra'

    def __post_init__(self) -> None:
        self.ruc = solo_digitos(self.ruc)
        self.periodo = solo_digitos(self.periodo)[:6]
        self.razon_social = " ".join(str(self.razon_social or "").split())
        self.tipo = str(self.tipo or "").strip().lower()
        if len(self.ruc) != 11:
            raise ValueError(f"RUC inválido: {self.ruc!r} (11 dígitos)")
        if not re.fullmatch(r"20[0-9]{2}(0[1-9]|1[0-2])", self.periodo):
            raise ValueError(f"Periodo inválido: {self.periodo!r} (AAAAMM)")
        if self.tipo not in TIPOS_LIBRO:
            raise ValueError(f"Tipo de libro inválido: {self.tipo!r} ({'|'.join(sorted(TIPOS_LIBRO))})")

    @property
    def anio(self) -> int:
        return int(self.periodo[:4])

    @property
    def mes(self) -> int:
        return int(self.periodo[4:6])

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    @property
    def es_compra(self) -> bool:
        """La pareja de `es_venta`, y no es redundante: hasta la 8.x `not es_venta` significaba «es compra» en medio
        centenar de sitios, y eso solo era cierto mientras el catálogo tuviera dos valores. Con las dos preguntas por
        separado, un tipo de libro nuevo da `False` a las dos y **cada rama tiene que decidir** en vez de heredar
        «compra». Lo sigue preguntando lo que tiene el libro en la mano —los lectores, `validar`, los drivers—;
        lo que recibe el eje por parámetro recibe los `rasgos`."""
        return self.tipo == "compra"

    @property
    def es_tesoreria(self) -> bool:
        """La tercera, y entra con el mismo argumento que la segunda: tres preguntas separadas obligan a cada rama
        a decidir, mientras que `not es_venta` daba por hecho que lo demás era una compra."""
        return self.tipo == "tesoreria"

    @property
    def rasgos(self) -> Rasgos:
        """Lo que el motor necesita saber de este libro. Es lo que se le pasa al núcleo desde la 9.0."""
        return rasgos_de(self.tipo)

    def a_dict(self) -> dict[str, str]:
        return {"ruc": self.ruc, "razon_social": self.razon_social, "periodo": self.periodo, "tipo": self.tipo}

    @classmethod
    def de_dict(cls, d: dict) -> "Libro":
        """**Lo desconocido NO se ignora** (7.0). Hasta la 6.5 se filtraba en silencio, y era el último sitio del
        estándar donde pasaba: un dato que se cuela sin error es un dato que se pierde sin aviso.

        Dejaba al lector **más laxo que el esquema publicado**, que rechaza por su `additionalProperties: false`
        (`estandar/open-accounting.schema.json`, `$defs.libro`). Es el mismo agujero que la 4.0 cerró para el
        comprobante, y el CHANGELOG de entonces dio por hecho que «faltaba solo el comprobante»: faltaba también
        el libro. De ahí sale la forma de este rechazo —nombrar TODAS las sobrantes, no reventar en la primera—.

        **Las claves `_` tampoco pasan**, y aquí es más estricto que el comprobante a propósito: `$defs.libro` es
        el único bloque del esquema sin `patternProperties: {"^_": …}`, así que el estándar no admite una anotación
        del productor dentro del libro. Su sitio es la raíz del documento.

        **El mensaje dice las cuatro que hay** en vez de señalar una válvula: el comprobante puede mandar lo que
        el motor no entiende a `datos_originales`, y el libro no tiene dónde. El molde es
        `configuracion._errores_del_objeto`, que lista las claves válidas por eso mismo.

        Lo que **falta** sigue llegando vacío: `razon_social` es opcional en la práctica —los golden traen tres
        claves— y lo que no se puede suponer lo rechaza la validación del libro con su propio `ValueError`.
        """
        if not isinstance(d, dict):
            raise ValueError("El libro tiene que ser un objeto con ruc, razon_social, periodo y tipo")
        validas = [f.name for f in fields(cls)]
        desconocidas = sorted(set(d) - set(validas))
        if desconocidas:
            raise ValueError(f"Claves que no son de un libro: {', '.join(desconocidas)}. "
                             f"Las que hay: {', '.join(validas)}")
        return cls(**{nombre: d.get(nombre, "") for nombre in validas})

