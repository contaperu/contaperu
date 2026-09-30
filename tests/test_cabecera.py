"""La cabecera del índice lleva todos los hechos del comprobante (1.4.0).

Nace de un hueco real. `asiento.indice.Cabecera` tenía trece campos —los que CONCAR necesitaba— y eso bastó
mientras el único driver de asientos escribiera contabilidad pura: de las 41 columnas de CONCAR, **ninguna es
el destino del IGV**, así que el dato podía caerse sin que nadie lo notara. Un comprobante con
`destino_igv: "DGNG"` producía exactamente el mismo Excel que uno con `DG`.

STARSOFT rompió el supuesto: su plantilla mezcla el asiento con el registro tributario en la misma fila, y pide
el destino, el valor no gravado y los datos de la DUA. Un driver de REGISTRO (SIRE, CONTASIS) siempre los tuvo
—recibe el comprobante entero—; uno de ASIENTOS solo ve líneas y cabecera, y ahí se perdían diecinueve campos,
diecisiete de ellos columnas oficiales del registro de compras y ventas de SUNAT.

Arreglarlos uno a uno habría durado hasta el siguiente driver. Lo que se arregla es la REGLA, y este archivo es
quien la hace cumplir: **la cabecera lleva todo hecho contable o tributario del comprobante, y ningún dato del
proceso que lo produjo**. Si el estándar gana un campo mañana, o entra en la cabecera o entra en `DEL_PROCESO`
con su motivo; no hay tercera opción que no sea este test en rojo.
"""
from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from contaperu import api, modelo
from contaperu.asiento import motor
from contaperu.asiento.indice import Cabecera

# Los únicos campos del comprobante que NO son hechos contables: dicen de dónde salió el dato y qué opina la
# validación, no qué pasó. Un driver que mirara `confianza` estaría decidiendo contabilidad con la certeza de
# un modelo de lenguaje, y `estado` u `observaciones` son el resultado de mirar el comprobante, no el
# comprobante. La aplicación los tiene; el driver no los necesita.
#
# `estado_sunat` está aquí por la misma razón y una más: es lo que SUNAT dice del comprobante en SU registro
# («Est. Comp»), no lo que pasó. No mueve ningún importe, ninguna cuenta ni ningún sentido; la propia norma lo llama
# referencial y no publica su tabla de valores. Un driver de asiento no tiene nada que hacer con él, y los dos de
# registro reciben el comprobante entero, así que lo tienen si algún día lo necesitan.
DEL_PROCESO = frozenset({"origen", "confianza", "archivo_nombre", "datos_originales",
                         "estado", "excluida", "observaciones", "estado_sunat"})

# Antes vivían aquí los ocho hechos que también viajan DENTRO de la línea —el concepto, el vencimiento, el tipo de
# cambio, los cuatro de la nota que modifica y la detracción—, con el argumento de que repetirlos sería tener el mismo
# hecho en dos sitios. **Se vació en la 3.9**, cuando el driver del estándar tuvo que escribir el bloque
# `comprobantes`: desde la línea no se pueden recomponer —`referencia.serie_numero` va unido por un guion y no hay
# vuelta fiable, y la `cuenta` del Banco de la Nación de la detracción no está en ninguna línea—, así que el documento
# que producía no podía volver a entrar al motor. La cabecera lleva ahora TODOS los hechos, sin excepción, y la línea
# sigue llevando los suyos: no es duplicar por comodidad, es que cada uno responde a una pregunta distinta.
#
# Se queda como frozenset vacío y no se borra: es la mitad de la regla que este archivo hace cumplir, y el día que
# haya un motivo de verdad para excluir un campo, aquí es donde se declara con su porqué.
EN_LA_LINEA: frozenset[str] = frozenset()


def _campos_del_estandar() -> set[str]:
    return set(api.esquema_open_accounting()["$defs"]["comprobante"]["properties"])


def test_la_cabecera_lleva_todos_los_hechos_del_comprobante():
    """La regla, hecha cumplir contra el esquema publicado y no contra una lista escrita a mano.

    Es lo que impide que el próximo driver descubra, como STARSOFT, que el dato que necesita existe en el
    estándar y se cae por el camino.
    """
    en_la_cabecera = {f.name for f in dataclasses.fields(Cabecera)}
    deberian = _campos_del_estandar() - DEL_PROCESO - EN_LA_LINEA
    faltan = deberian - en_la_cabecera
    assert not faltan, f"hechos del comprobante que no llegan al driver: {sorted(faltan)}"


def test_la_cabecera_no_lleva_nada_del_proceso():
    """La otra mitad de la regla. Sin esto, la cabecera se llenaría de metadatos por comodidad."""
    en_la_cabecera = {f.name for f in dataclasses.fields(Cabecera)}
    colados = en_la_cabecera & DEL_PROCESO
    assert not colados, f"datos del proceso en la cabecera, que no son hechos contables: {sorted(colados)}"


def test_cada_lista_de_excepciones_sigue_siendo_cierta():
    """Las dos listas son excepciones declaradas, así que se comprueban: un campo que desaparezca del estándar
    tiene que salir de ellas, o dejarían de decir la verdad sin que nadie lo vea."""
    del_estandar = _campos_del_estandar()
    assert DEL_PROCESO <= del_estandar, sorted(DEL_PROCESO - del_estandar)
    assert EN_LA_LINEA <= del_estandar, sorted(EN_LA_LINEA - del_estandar)


def test_los_hechos_tributarios_llegan_con_su_valor():
    """Que el campo exista no basta: tiene que traer lo que el comprobante dice."""
    c = modelo.Comprobante(tipo_cp="01", serie="F136", numero="431",
                           contraparte_doc="20131312955", contraparte_nombre="PROVEEDOR DE PRUEBA SAC",
                           base_gravada=Decimal("929.49"), igv=Decimal("167.31"), total=Decimal("1096.80"),
                           destino_igv="DGNG", anio_dua="2025", cod_dep_aduanera="118",
                           exonerado=Decimal("50.00"), inafecto=Decimal("10.00"))
    cab = motor.cabecera_de(c)
    assert cab.destino_igv == "DGNG"
    assert (cab.anio_dua, cab.cod_dep_aduanera) == ("2025", "118")
    assert cab.exonerado == "50.00" and cab.inafecto == "10.00"


def test_el_valor_no_gravado_llega_ya_resuelto():
    """El campo del estándar admite nulo y entonces significa «exonerado más inafecto». Esa cuenta la hace el
    modelo una vez (`adquisiciones_no_gravadas`) y no cada driver a su manera."""
    sin_declarar = modelo.Comprobante(exonerado=Decimal("50.00"), inafecto=Decimal("10.00"))
    assert sin_declarar.valor_no_gravado is None
    assert motor.cabecera_de(sin_declarar).valor_no_gravado == "60.00"

    declarado = modelo.Comprobante(exonerado=Decimal("50.00"), inafecto=Decimal("10.00"),
                                   valor_no_gravado=Decimal("45.00"))
    assert motor.cabecera_de(declarado).valor_no_gravado == "45.00"


def test_la_cabecera_es_un_comprobante_del_estandar():
    """`como_comprobante()` produce un `comprobante` que valida contra el esquema publicado, campo a campo.

    Es lo que hace posible que un driver escriba el bloque `comprobantes` sin inventarse nada, y por tanto que su
    documento pueda volver a entrar al motor. Dos cosas lo romperían y las dos están cubiertas aquí: que la cabecera
    gane un campo que el estándar no declare, y que la detracción arrastre una anotación del motor como `tasa_tabla`,
    que `$defs/detraccion` rechaza por su `additionalProperties: false`.
    """
    from jsonschema import Draft202012Validator

    esquema = api.esquema_open_accounting()
    c = modelo.Comprobante(tipo_cp="01", serie="F136", numero="431", fecha_emision=date(2026, 1, 10),
                           fecha_vencimiento=date(2026, 2, 10), contraparte_tipo_doc="6",
                           contraparte_doc="20131312955", contraparte_nombre="PROVEEDOR DE PRUEBA SAC",
                           concepto="SERVICIO DE TRANSPORTE", moneda="PEN",
                           base_gravada=Decimal("1000.00"), igv=Decimal("180.00"), total=Decimal("1180.00"),
                           exonerado=Decimal("50.00"), destino_igv="DGNG",
                           detraccion={"codigo": "027", "monto": Decimal("47.00"), "tasa_tabla": "4",
                                       "cuenta": "00-123-456789"})
    comprobante = motor.cabecera_de(c).como_comprobante()

    validador = Draft202012Validator({"$ref": "#/$defs/comprobante", "$defs": esquema["$defs"]})
    errores = [f"{list(e.path)}: {e.message}" for e in validador.iter_errors(comprobante)]
    assert errores == [], f"la cabecera no es un comprobante del estándar: {errores}"

    assert "glosa" not in comprobante, "la glosa es un derivado del concepto y el estándar no la declara"
    assert comprobante["concepto"] == "SERVICIO DE TRANSPORTE"
    assert "tasa_tabla" not in comprobante["detraccion"], "es una anotación del motor, no del estándar"
    assert comprobante["detraccion"]["cuenta"] == "00-123-456789", "la cuenta del banco no está en ninguna línea"


def test_lo_vacio_no_viaja_como_un_dato():
    """Una cadena vacía no es «no lo sé»: no pasa el `pattern` de `moneda` ni el `enum` de `contraparte_tipo_doc`.

    `a_dict()` sí lleva lo vacío, y a propósito: un driver recibe la lista completa de hechos para saber que existen
    (`tests/test_driver_diario_json.py`). Quien escribe un documento usa `como_comprobante()`."""
    cab = motor.cabecera_de(modelo.Comprobante(tipo_cp="01", serie="F1", numero="1"))
    vacios = ("numero_final", "anio_dua", "condicion_pago", "id_contrato", "cod_dep_aduanera")
    assert all(cab.a_dict()[campo] == "" for campo in vacios), "a_dict los declara todos, aunque estén vacíos"
    assert not set(vacios) & set(cab.como_comprobante()), "una cadena vacía no es un dato: la clave se omite"
    # Lo que sí tiene valor viaja por las dos vías: `moneda` es PEN de fábrica en el modelo.
    assert cab.a_dict()["moneda"] == "PEN" == cab.como_comprobante()["moneda"]


def test_la_glosa_es_derivada_y_no_puede_discrepar():
    """Deja de ser un campo: sale del concepto y, si viene vacío, del nombre de la contraparte."""
    con_concepto = motor.cabecera_de(modelo.Comprobante(concepto="alquiler de andamios",
                                                        contraparte_nombre="Proveedor SAC"))
    assert con_concepto.glosa == "ALQUILER DE ANDAMIOS"
    sin_concepto = motor.cabecera_de(modelo.Comprobante(contraparte_nombre="Proveedor SAC"))
    assert sin_concepto.glosa == "PROVEEDOR SAC"
    assert "glosa" not in {f.name for f in dataclasses.fields(Cabecera)}


def test_la_cabecera_no_entra_en_la_huella():
    """La razón por la que los campos van aquí y no a la huella, fijada como test.

    La huella del motor responde «¿este asiento ya salió?» y va sobre las líneas neutrales. Si los hechos
    tributarios entraran, dos exportaciones con el mismo asiento —el Excel de CONCAR sale idéntico con `DG` y
    con `DGNG`— darían huellas distintas, y el aviso de lote repetido dejaría de dispararse. Quien necesita
    saber si un comprobante cambió tiene su propia huella, en la aplicación.
    """
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202507", "tipo": "compra"},
           "comprobantes": [{"tipo_cp": "01", "serie": "F136", "numero": "431", "fecha_emision": "2025-07-01",
                             "contraparte_doc": "20131312955", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
                             "base_gravada": "929.49", "igv": "167.31", "total": "1096.80",
                             "concepto": "CELULARES", "id_externo": "f1"}]}
    config = {"usa_centros_costo": False}
    imputacion = {"f1": {"cuenta_contable": "60111000"}}

    def huella_con(destino):
        d = {**doc, "comprobantes": [{**doc["comprobantes"][0], "destino_igv": destino}]}
        return api.generar_asiento(d, driver="concar", configuracion=config,
                                   imputacion=imputacion, correlativos={"11": 1})["_asiento"]["huella"]

    assert huella_con("DG") == huella_con("DGNG"), "el destino del IGV no cambia el asiento: la huella tampoco"


@pytest.mark.parametrize("campo", sorted(DEL_PROCESO))
def test_ningun_dato_del_proceso_viaja_al_driver(campo):
    """Recorrido campo a campo, para que el mensaje diga cuál se coló."""
    assert campo not in {f.name for f in dataclasses.fields(Cabecera)}
