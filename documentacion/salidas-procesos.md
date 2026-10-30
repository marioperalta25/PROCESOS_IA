# Organizacion comun de resultados

La jerarquia y el sufijo de copias se declaran en
`recursos/configuracion/salidas.toml`. La raiz procede de `EnrutadorSalidas`
o de la carpeta base elegida por el usuario.

```text
<raiz>/extracciones/
    deepseek/
    gemini/
    ia_local/
    ia_general/
        imagenes/
        modo_ia/
```

Cada rama contiene `en_proceso`, `completados`, `fallidos` y `cancelados`.
Dentro de cada estado hay una carpeta por trabajo, con su resultado,
auditoria y archivos de recuperacion asociados. Los archivos de imagen
originales no se trasladan: `imagenes` organiza resultados de Lens para
URL individual, carpeta de imagenes y archivo tabular con URLs.

## Trabajo nuevo

El consumidor llama a `EnrutadorSalidas.reservar_salida` antes de escribir.
Una reserva nueva nunca se interpreta como continuacion por tener el mismo nombre.
Si el nombre ya esta ocupado se agrega `_copia1`, `_copia2`, etc., tanto a la
carpeta del trabajo como al archivo principal. Los nombres se reservan mediante
creacion exclusiva de directorios en la carpeta tecnica `reservas` de cada rama.
Estas reservas persisten aunque el resultado cambie de estado; no deben eliminarse
mientras se requiera mantener la numeracion y evitar reutilizaciones.

La ruta permanece estable durante la escritura. Al terminar y cerrar los archivos,
el consumidor indica el estado a `SalidaProceso.finalizar`. Se mueve la carpeta
completa y se devuelve la ruta definitiva. Las interfaces conservan esa ruta para
mostrar o abrir el resultado. Los errores inesperados dentro del contexto de la
reserva conservan lo escrito en `fallidos`.

La politica tecnica no decide si una respuesta de IA es valida ni transforma
telefonos, columnas o contenido. El escritor CSV comun conserva todos los campos
y consolida mediante un temporal en el mismo directorio y reemplazo atomico.

## Continuaciones

La logica del modulo decide explicitamente si continua una salida. Una continuacion
de Lens conserva su nombre; `GestorSalidasProceso.retomar` la devuelve a `en_proceso`
cuando pertenece a la jerarquia actual. Los archivos antiguos elegidos expresamente
conservan su ubicacion. No se realiza una migracion automatica de resultados anteriores.

En el procesamiento local se buscan respaldos incompletos cuya identidad coincida
con el origen y la evaluacion vigentes. La interfaz permite continuar ese trabajo,
iniciar una copia nueva o cancelar. La continuacion conserva el nombre de salida
y el checkpoint, incluso si el nombre contiene `_copiaN`. Un origen o una evaluacion
modificados no reutilizan esos resultados. Esta decision pertenece al flujo local;
la reserva general de un trabajo nuevo sigue creando un destino independiente.

Este incremento organiza salidas y evita sobrescrituras entre trabajos nuevos.
La seleccion por filas pendientes o con error y el respaldo recuperable para todos
los flujos web requieren sus propios contratos; no se deducen de la carpeta de estado.
La persistencia WAL del procesamiento local se conserva.
