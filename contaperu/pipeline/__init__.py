"""El pipeline: cómo se prepara y se orquesta un mes, escrito una sola vez (1.0).

Hasta la 0.10 la preparación de un documento vivía en la fachada, la orquestación del asiento en `generar.py` y el
diagnóstico en otra función de la fachada, y cada puerta la recorría a su manera. Aquí queda cada paso en su módulo:

- `preparacion` — del documento al libro y los comprobantes, la configuración aplicada y la imputación
- `lectura`     — de los archivos de SUNAT al documento
- `seleccion`   — qué comprobantes salen hacia un destino y cuáles bloquean
- `armado`      — el asiento: lo que exige el destino, la numeración, el cuadre y la forma del driver
- `salida`      — el archivo del destino y su resumen (`Exportado`)
- `diagnostico` — lo que hay que mirar de un mes antes de exportarlo

Es interno: puede cambiar en una versión menor. Lo estable es `contaperu.api`, que se apoya en esto.
"""
