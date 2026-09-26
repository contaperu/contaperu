"""Quién escribe cada campo de un comprobante: el documento, el sistema o la revisión.

El reparto en sí es una tupla de nombres; **el valor está en estos tests**, porque una lista de campos
escrita a mano no se queja de lo que le falta. Ese es el caso que trajo esto al motor: la primera
aplicación que abrió una puerta de entrada escribió su lista a mano y se dejó cinco campos que su propia
base ya guardaba —los dos descuentos, el ICBPER, el valor no gravado y el destino del IGV—; los datos se
perdían sin error y sin aviso, y su test solo comprobaba que la lista fuera un **subconjunto** del
estándar, así que un olvido pasaba en verde para siempre.
"""
from __future__ import annotations

from dataclasses import fields

from contaperu import api, modelo
from contaperu.modelo import Comprobante

TRAMOS = (modelo.CAMPOS_DEL_DOCUMENTO, modelo.CAMPOS_DEL_SISTEMA, modelo.CAMPOS_DE_LA_REVISION)


def test_los_tres_tramos_cubren_el_comprobante_entero_y_no_se_solapan():
    """**El test que hace útil el reparto.** Un campo nuevo en el modelo que nadie clasifique deja esto
    rojo, que es exactamente lo que no pasaba cuando la lista vivía en una aplicación: allí un campo
    nuevo del estándar simplemente no se aceptaba, y nadie se enteraba."""
    del_modelo = {f.name for f in fields(Comprobante)}
    repartidos = [campo for tramo in TRAMOS for campo in tramo]

    sin_clasificar = sorted(del_modelo - set(repartidos))
    assert not sin_clasificar, (f"campos del comprobante que nadie reparte: {sin_clasificar}. "
                               f"Ponlos en el tramo que les toque, en `contaperu/modelo.py`.")
    inventados = sorted(set(repartidos) - del_modelo)
    assert not inventados, f"campos repartidos que el comprobante no tiene: {inventados}"
    assert len(repartidos) == len(set(repartidos)), "un campo está en dos tramos a la vez"


def test_cada_campo_repartido_existe_en_el_estandar():
    """El reparto habla del documento `open-accounting`, no de un modelo interno: si el estándar renombra
    un campo, esto lo dice."""
    del_estandar = set(api.esquema_open_accounting()["$defs"]["comprobante"]["properties"])
    for tramo, nombre in zip(TRAMOS, ("documento", "sistema", "revision")):
        fuera = sorted(set(tramo) - del_estandar)
        assert not fuera, f"el tramo «{nombre}» nombra campos que el estándar no tiene: {fuera}"


def test_lo_obligatorio_lo_dice_siempre_el_documento():
    """Nada que el papel no diga puede ser obligatorio: si lo fuera, una puerta de entrada tendría que
    pedirle a quien dicta un dato que solo el sistema conoce."""
    obligatorios = set(api.esquema_open_accounting()["$defs"]["comprobante"]["required"])
    del_sistema = set(modelo.CAMPOS_DEL_SISTEMA) | set(modelo.CAMPOS_DE_LA_REVISION)
    assert not obligatorios & del_sistema
    assert obligatorios <= set(modelo.CAMPOS_DEL_DOCUMENTO)


def test_lo_que_decide_el_sistema_no_se_acepta_de_quien_dicta():
    """Los cinco del sistema y los tres de la revisión, uno por uno y por su nombre. Escritos aquí a
    propósito: son la lista que una puerta de entrada tiene que rechazar, y verla completa es el sentido
    de que este test exista."""
    assert set(modelo.CAMPOS_DEL_SISTEMA) == {"origen", "confianza", "archivo_nombre", "id_externo",
                                              "datos_originales"}
    assert set(modelo.CAMPOS_DE_LA_REVISION) == {"estado", "excluida", "observaciones"}
    # Y los que SÍ se dictan y más se olvidan, porque son los que costaron el caso: los descuentos, el
    # impuesto a la bolsa, el valor no gravado y el destino del IGV.
    for campo in ("dscto_base", "dscto_igv", "icbper", "valor_no_gravado", "destino_igv", "medio_pago"):
        assert campo in modelo.CAMPOS_DEL_DOCUMENTO, campo


def test_por_la_api_sale_con_sus_obligatorios():
    r = api.campos_del_comprobante()
    assert set(r) == {"documento", "sistema", "revision", "obligatorios"}
    assert r["obligatorios"] == ["tipo_cp", "fecha_emision", "total"]
    assert r["documento"] == list(modelo.CAMPOS_DEL_DOCUMENTO)
    # Listas y no tuplas: viaja como JSON, y una tupla no tiene forma en JSON.
    assert all(isinstance(v, list) for v in r.values())
