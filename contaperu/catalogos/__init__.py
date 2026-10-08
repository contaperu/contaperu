"""Catálogos de SUNAT que usa el motor (los que hacen falta, no todos).

Era un módulo de 426 líneas que hacía cinco cosas —los códigos de un comprobante, los
tributos, el canal y el formato del SIRE, el formato del PLE y el contribuyente—, y desde
la 6.2.0 es un paquete con un fichero por tema. **Lo que se importa no cambió**: este
`__init__` reexporta exactamente los mismos nombres, y el test de la superficie pública
lo demuestra al seguir pasando sin regenerarse.

Fuentes: Anexo 1 de la RS 112-2021 (documentos de identidad, monedas y tipos de
comprobante del RVIE), Anexo 1 de la RS 040-2022 (tipos de comprobante del RCE) y
Anexo 3 de la RS 169-2015 (tipos de medio de pago) y Anexo N.° 8 de la RS 097-2012,
con el texto de la RS 244-2019 (códigos de tributo, el Catálogo 05 de la factura
electrónica).

**Un catálogo se nombra por lo que ES, nunca por su número de tabla.** Cada anexo de SUNAT numera las suyas
empezando por 1, así que hay una «Tabla 1» de documentos de identidad (Anexo 1 de la RS 112-2021) y otra de medios de
pago (Anexo 3 de la RS 169-2015), y el número suelto no identifica nada: solo vale dentro de su cita, que es donde
vive, en `fuente`. Y el número puede cambiar con la siguiente resolución; lo que el catálogo es, no.

**Los catálogos viven en datos, con su fuente** (1.1, primer paso del hito C1 de la hoja de ruta): los tipos de
comprobante, los documentos de identidad, las monedas, los medios de pago, los motivos de nota y los códigos de
tributo se leen de `datos/sunat/catalogos.json`, y
`FUENTES` dice de dónde sale cada uno. Los nombres y los tipos de siempre no cambian. Lo demás de este módulo son
reglas del motor sobre esos códigos, con su porqué al lado.
"""
from __future__ import annotations

# `ErrorContaperu` está en la superficie pública de este módulo desde que las excepciones del contribuyente
# entraron (6.1.0): quitarlo sería retirar un nombre sin avisar, así que se reexporta a propósito.
from ..errores import ErrorContaperu
from ._fuente import FUENTES
from .comprobantes import (ADUANEROS, EXIGEN_VENCIMIENTO, FUERA_DEL_REGISTRO_SUNAT, MEDIOS_PAGO, MONEDAS,
                           MOTIVOS_NOTA_CREDITO, MOTIVOS_NOTA_DEBITO, NOTAS, NOTAS_CREDITO, NOTAS_DEBITO,
                           SCHEME_A_TIPO_DOC, SIN_CONTRAPARTE_OK, TIPO_BOLETA, TIPO_HONORARIOS,
                           TIPOS_CP, TIPOS_DOC_IDENTIDAD, TIPOS_INVIERTEN, TIPOS_NOTA,
                           motivos_de_nota, ruc_valido)
from .contribuyente import (CRONOGRAMAS, ESTADOS_DE_REGIMEN, REGLAS_DE_REGIMEN, RUTA_REGIMENES,
                            RUTA_VENCIMIENTOS, CatalogoInvalido, SinCronograma, anios_con_cronograma,
                            cronogramas_de_vencimiento, regimenes_tributarios, validar_regimenes,
                            vence_el_registro, vence_la_declaracion)
from .ple import FORMATO_PLE, campos_del_ple, columnas_del_ple
from .sire import REGISTRO_SIRE, api_sire, campos_del_sire, columnas_del_sire, nombres_del_sire
from .tributos import (CATEGORIA_RENTA_4TA, CLASES_IGV_COMPRA, CLASES_IGV_VENTA, TASA_IGV,
                       TASAS_IGV_REDUCIDAS, TOLERANCIA_IGV, TRIBUTO_EXONERADO, TRIBUTO_EXPORTACION,
                       TRIBUTO_GRATUITO, TRIBUTO_ICBPER, TRIBUTO_IGV, TRIBUTO_INAFECTO, TRIBUTO_ISC,
                       TRIBUTO_IVAP, TRIBUTO_OTROS, TRIBUTO_RENTA, TRIBUTOS)

# Los mismos nombres que exponía el módulo, escritos a mano: así una reorganización interna no puede
# llevarse uno por descuido, y lo que un consumidor importa no depende de en qué fichero acabó.
__all__ = [
    "ADUANEROS", "CATEGORIA_RENTA_4TA", "CLASES_IGV_COMPRA", "CLASES_IGV_VENTA", "CRONOGRAMAS", "CatalogoInvalido",
    "ESTADOS_DE_REGIMEN", "EXIGEN_VENCIMIENTO", "ErrorContaperu", "FORMATO_PLE", "FUENTES",
    "FUERA_DEL_REGISTRO_SUNAT", "MEDIOS_PAGO", "MONEDAS", "MOTIVOS_NOTA_CREDITO", "MOTIVOS_NOTA_DEBITO", "NOTAS",
    "NOTAS_CREDITO", "NOTAS_DEBITO", "REGISTRO_SIRE", "REGLAS_DE_REGIMEN", "RUTA_REGIMENES", "RUTA_VENCIMIENTOS",
    "SCHEME_A_TIPO_DOC", "SIN_CONTRAPARTE_OK", "SinCronograma", "TASAS_IGV_REDUCIDAS", "TASA_IGV", "TIPOS_CP",
    "TIPOS_DOC_IDENTIDAD", "TIPOS_INVIERTEN", "TIPOS_NOTA", "TIPO_BOLETA", "TIPO_HONORARIOS", "TOLERANCIA_IGV",
    "TRIBUTOS", "TRIBUTO_EXONERADO", "TRIBUTO_EXPORTACION", "TRIBUTO_GRATUITO", "TRIBUTO_ICBPER", "TRIBUTO_IGV",
    "TRIBUTO_INAFECTO", "TRIBUTO_ISC", "TRIBUTO_IVAP", "TRIBUTO_OTROS", "TRIBUTO_RENTA", "anios_con_cronograma",
    "api_sire", "campos_del_ple", "campos_del_sire", "columnas_del_ple", "columnas_del_sire",
    "cronogramas_de_vencimiento", "motivos_de_nota", "nombres_del_sire", "regimenes_tributarios", "ruc_valido",
    "validar_regimenes", "vence_el_registro", "vence_la_declaracion",
]
