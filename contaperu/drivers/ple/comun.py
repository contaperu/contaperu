"""Lo que SUNAT impone igual a todos los libros del PLE, escrito una vez.

Son dos drivers —el Libro Diario 5.1 y su detalle del plan contable 5.3— y van en el mismo envase: las mismas
opciones de texto, la misma oportunidad, las mismas banderas del nombre y el mismo estado. Lo que cambia entre ellos
es su código de libro, sus campos y de qué saca cada fila.

La casa ya tiene jurisprudencia contra escribir esto dos veces: cuando el `sire` dejó de ser el único libro
electrónico, la nomenclatura `LE…` salió a `kit/nombres.py` con el motivo escrito — «una regla que SUNAT impone no
puede estar escrita en dos drivers». Esto es lo mismo un piso más abajo: lo que comparten los dos libros del PLE, y
que el kit no puede llevar porque no es de todos los drivers sino de éstos.
"""
from __future__ import annotations

from ..kit import Opciones

# `cero="0.00"` lo pide el 5.1, que lleva el Debe y el Haber en DOS columnas y escribe el cero en la que no toca. El
# 5.3 no lleva importes y no lo usa; está aquí porque las opciones son del envase, no de los campos.
#
# Y `codificacion="cp1252"` sale del archivo contrastado, no de una preferencia: su 5.3 escribe «ALQUILER DE
# BAÑOS QUIMICOS» con el byte `0xD1` —una Ñ de cp1252, no los dos bytes de UTF-8— y SUNAT lo aceptó, con su
# constancia. Hasta la 5.2 estos dos drivers heredaban el `ascii` que `Opciones` trae de fábrica, sin que nadie
# lo hubiera decidido, y escribían «BANOS»: cuatro de las 725 cuentas de ese mes salían con el nombre cambiado.
# El 5.3 exige la denominación del contribuyente justamente para no declararle a SUNAT un nombre que no usa,
# así que cambiársela es el mismo pecado, más pequeño.
OPCIONES = Opciones(fecha="DD/MM/AAAA", nueva_linea="\r\n", tc_pen="", cero="0.00", extension=".TXT",
                    codificacion="cp1252")

# Oportunidad y banderas del nombre del fichero, tal como vienen en el archivo contrastado. El `sire` usa `02` porque
# reemplaza una propuesta; un libro del PLE no reemplaza nada.
OPORTUNIDAD = "00"
BANDERAS = "1111"

# El día del NOMBRE del fichero va en `00` cuando el libro es del periodo entero. Ojo: no es el mismo día que va
# DENTRO del 5.3, cuyo campo 1 es `AAAAMMDD` y lleva `01`. Confundirlos es fácil y los dos salen del mismo archivo.
DIA_DEL_NOMBRE = "00"

# `1` cuando lo que se informa corresponde al periodo. El `8` —de un periodo anterior— y el `9` —que corrige algo ya
# anotado— los decide quien lleva el libro, no el motor.
ESTADO_DEL_PERIODO = "1"
