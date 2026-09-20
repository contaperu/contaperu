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
from decimal import Decimal

import pytest

from contaperu import api, modelo
from contaperu.asiento import motor
from contaperu.asiento.indice import Cabecera

# Los únicos campos del comprobante que NO son hechos contables: dicen de dónde salió el dato y qué opina la
# validación, no qué pasó. Un driver que mirara `confianza` estaría decidiendo contabilidad con la certeza de
# un modelo de lenguaje, y `estado` u `observaciones` son el resultado de mirar el comprobante, no el
# comprobante. La aplicación los tiene; el driver no los necesita.
DEL_PROCESO = frozenset({"origen", "confianza", "archivo_nombre", "datos_originales",
                         "estado", "excluida", "observaciones"})

# Lo que la cabecera no lleva porque ya viaja DENTRO de la línea, en su bloque `documento`, `referencia` o
# `detraccion` (`LineaDiario`): repetirlo sería tener el mismo hecho en dos sitios.
EN_LA_LINEA = frozenset({"fecha_vencimiento", "tipo_cambio", "concepto", "detraccion",
                         "ref_fecha", "ref_tipo_cp", "ref_serie", "ref_numero"})


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
