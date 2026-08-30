# Rankings importados

Cada archivo `.txt` de esta carpeta es el ranking de otra fuente. El nombre del
archivo es el nombre de la fuente: `mi-analista.txt` aparecerá como
«mi analista» en la interfaz.

## Formato

Un jugador por línea, en orden. Se acepta casi cualquier cosa que copies de un
vídeo, una web o una hoja de cálculo:

```
# Top 10 de Fulanito, pretemporada 2026
1. Ja'Marr Chase
2  Bijan Robinson RB ATL
3, Justin Jefferson, WR, MIN
4) Amon-Ra St. Brown (WR - DET)
5. Brock Bowers TE1
6. SF DEF
Puka Nacua
```

- El número de delante es **opcional**: si no está, manda el orden de las líneas.
- La posición y el equipo del final se descartan solos.
- Las líneas vacías y las que empiezan por `#` se ignoran. Si la primera línea es
  un comentario, se usa como descripción de la fuente.

## Qué hace la herramienta con esto

No sustituye al ranking propio: lo pone al lado. En la tabla aparece el puesto
de cada fuente y **la diferencia con el nuestro**, que es lo único que importa
de verdad. Si dos listas coinciden en que alguien es el número tres, no hay nada
que decidir; si una lo pone quince puestos por delante, ahí hay una opinión que
merece mirarse.

Los nombres que no se reconozcan se avisan en los logs y en `/api/external`,
para que puedas corregir el archivo.
