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

# Tasas de IGV que la validación RECONOCE: la general y las reducidas de las MYPE de restaurantes,
# hoteles y alojamiento turístico. Reconocer no es aprobar —qué rige HOY lo dice `TASAS_IGV_VIGENTES`,
# aquí abajo—: una factura de 2023 al 8 % se sigue leyendo, se asienta y se exporta igual, y
# `igv.tasa_legal` recorre esta tupla para decir qué tasa escribir en el archivo.
TASA_IGV = "0.18"
TASAS_IGV_REDUCIDAS = ("0.10", "0.105", "0.08")
# Las que RIGEN hoy, que es otra pregunta (28-oct-2026). Una reducida que ya no rige se avisa para que
# alguien la mire (`IGV_TASA_REDUCIDA`); una vigente no dice nada, porque es la tasa correcta y
# repetirlo en cada factura de un hotel no es una señal: es ruido, y además dejaba el comprobante
# —y con él su mes— en «observada» para siempre.
#
# El 10,5 % **no es un IGV que subió**: el reducido sigue en 8 %, y lo que cambió es el Impuesto de
# Promoción Municipal, del 2 % al 2,5 %. Ley 32219 (prórroga de la tasa reducida) y Ley 32387 (el IPM).
# ⚠️ Las dos se tomaron de prensa especializada, NO del texto en El Peruano ni de SUNAT: antes de
# apoyarse en ellas para otra cosa, verificarlas.
# ⚠️ La prórroga llega hasta el **31-dic-2026**. Ese día cambia esta constante, con su cita al lado —el
# mismo molde que `PLAZO_ANOTACION_MESES`—. **No hay tramos por fecha, y es deliberado** (John,
# 27-sep-2026 y 28-oct-2026): esto no mira la fecha del comprobante, solo dice qué rige hoy.
TASAS_IGV_VIGENTES = (TASA_IGV, "0.105")
# Cuánto puede separarse el IGV escrito del calculado por redondeos del emisor. Vivía en `validar.py` y la leía
# también `igv.py`, que por eso dependía de la validación entera (1.0: las dependencias ocultas se cortan).
TOLERANCIA_IGV = Decimal("0.05")
