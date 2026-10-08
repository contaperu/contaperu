"""Los tributos: su código del Catálogo 05 de SUNAT, la tasa del IGV y cómo se clasifica una operación.

Aquí no hay ninguna regla de cómo se mueve el dinero —eso es `tributos.igv`—: solo qué tributo es cada cosa y
con qué tasa se contrasta lo que el comprobante ya trae.
"""
from __future__ import annotations

from decimal import Decimal

from ._fuente import CATALOGOS

# Código de tributo del XML de la factura electrónica, en `cac:TaxCategory/cac:TaxScheme/cbc:ID`: el Catálogo 05 del
# Anexo N.° 8, que **entra en datos con su fuente en la 5.0** y hasta entonces era lo único de este módulo que
# afirmaba códigos de SUNAT sin citar la norma de la que salen —ni en `FUENTES`, ni en la fachada, ni con un test que
# fijara un solo valor—. Su `fuente` dice de qué anexo se transcribió y qué columna se dejó fuera.
#
# Los nueve nombres de siempre se quedan **leyendo de la tabla**: están en la superficie pública congelada y nunca
# avisaron de que fueran a irse, así que retirarlos rompería la promesa de que lo que se retira avisa durante toda la
# mayor anterior. `TRIBUTO_RENTA` es nuevo: el `3000` estaba en el anexo y no en el motor, y es el tributo que la
# línea de rol `retencion` cita en su bloque.
TRIBUTOS: dict[str, str] = dict(CATALOGOS["tributos"]["codigos"])
TRIBUTO_IGV = "1000"
TRIBUTO_IVAP = "1016"
TRIBUTO_ISC = "2000"
TRIBUTO_RENTA = "3000"      # la retención de 4ta es de este tributo, no del IGV
TRIBUTO_ICBPER = "7152"
TRIBUTO_EXPORTACION = "9995"
TRIBUTO_GRATUITO = "9996"   # operaciones gratuitas: NO entran en el cuadre ni en el registro
TRIBUTO_EXONERADO = "9997"
TRIBUTO_INAFECTO = "9998"
TRIBUTO_OTROS = "9999"
# La categoría de renta de la retención que el motor escribe. **No es un catálogo de SUNAT sino de la LEY**: las cinco
# categorías de renta son los artículos 22 y siguientes del TUO de la Ley del Impuesto a la Renta (D.S. 179-2004-EF), y
# la cuarta es la del trabajo independiente —su artículo 33—, que es la que muestra un recibo por honorarios y la
# única que el motor produce. Va aquí, al lado del tributo, porque juntas son lo que el bloque `retencion` de la línea
# dice: de qué tributo y de qué categoría. Las otras cuatro entran el día que un libro las necesite.
CATEGORIA_RENTA_4TA = "4"

# Que los diez nombres digan lo que la tabla dice, y no una copia que se pueda separar de ella en silencio, lo guarda
# un test (`test_cada_constante_de_tributo_apunta_a_su_fila`) y no un `assert` aquí: un `assert` desaparece con
# `python -O`. Es el mismo reparto que entre este módulo y `modelo` con las dos listas de notas.

# Cómo se llama en castellano cada clase de `igv.clase_de_igv`, para que la pantalla no las escriba a mano y no haya
# dos vocabularios. **Son dos tablas y no una**, porque los dos libros no informan lo mismo: el RVIE separa lo
# exonerado (campo 19) de lo inafecto (campo 20) y el RCE tiene una sola columna de adquisiciones no gravadas (campo
# 21) que no dice cuál de los dos es. Llamar «Inafecto» a una compra afirmaría algo que el archivo no distingue.
#
# La cadena vacía no está en ninguna de las dos **a propósito**: es lo que devuelve `clase_de_igv` cuando el
# comprobante no tiene ningún importe —así declara SUNAT lo que se da de baja— y entonces no hay clase que enseñar.
# Un comprobante en cero no es gravado ni no gravado.
#
# Ojo con «Mixto», que se parece a otra cosa a dos centímetros: aquí significa «lleva importes con y sin IGV», y en
# `destino_igv` el `DGNG` es «la compra se usa para ventas con y sin IGV». Qué te cobraron y para qué lo usas.
CLASES_IGV_COMPRA = {
    "gravada": "Gravada",
    "no_gravada": "No gravada",
    "importacion": "Importación",
    "mixto": "Mixto",
}
CLASES_IGV_VENTA = {
    "afecto": "Afecto",
    "exonerado": "Exonerado",
    "inafecto": "Inafecto",
    "exportacion": "Exportación",
    "mixto": "Mixto",
}

# Tasas de IGV que la validación reconoce. La general es 18 %; las reducidas
# (restaurantes y hoteles) se aceptan con aviso, no como error.
TASA_IGV = "0.18"
TASAS_IGV_REDUCIDAS = ("0.10", "0.105", "0.08")
# Cuánto puede separarse el IGV escrito del calculado por redondeos del emisor. Vivía en `validar.py` y la leía
# también `igv.py`, que por eso dependía de la validación entera (1.0: las dependencias ocultas se cortan).
TOLERANCIA_IGV = Decimal("0.05")
