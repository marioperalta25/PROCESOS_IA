---
id: calicar_math_y_rasgo_latino
titulo: calicar math y rasgo latino
descripcion: a continuacion mas detalle
categoria: ia_web
columnas_requeridas: 
columnas_salida: 
version: 6
resultados_json: []
creado_en_utc: 2026-11-02T17:10:40.386563+00:00
---
[ENTRADA]
Cada línea contiene un registro en este formato:
EMPRESA | PROPIETARIO
Procesa cada fila de forma independiente y conserva el orden de entrada.
[1. CLASIFICACIÓN DEL APELLIDO]
Evalúa la raíz lingüística probable del apellido del propietario.
- Usa LATINO CONFIRMADO cuando el apellido tenga una raíz hispana clara.
- Usa NO LATINO en los demás casos, incluidos los de origen dudoso.
Estas etiquetas son códigos de clasificación del apellido.
El nombre de pila y el nombre comercial quedan fuera de este cálculo.
[2. CONSISTENCIA ENTRE EMPRESA Y PROPIETARIO]
Ignora diferencias de mayúsculas y tildes. Para esta sección, aplica
las reglas en orden y detente en la primera que corresponda.
1. Si la empresa identifica claramente a una persona distinta del
   propietario, asigna NO MACHEA. Lee «TONY S TREE SERVICE» como
   «TONY'S TREE SERVICE». Antes de decidir si son personas distintas,
   comprueba las equivalencias de apodos indicadas abajo.
2. Si la empresa contiene el nombre de pila o un apellido del
   propietario como palabra completa, asigna MACHEA. Aplica también
   estas equivalencias autorizadas: TONY ↔ ANTHONY, DANNY ↔ DANIEL,
   JESS ↔ JESUS. Usa únicamente las equivalencias de esta lista.
3. Si la empresa contiene un bloque claro de iniciales, como M&Q,
   JC o J.C., compáralo con las iniciales del propietario.
   Una o más letras en común → MACHEA.
   Cero letras en común → NO MACHEA.
   Excluye abreviaturas legales como LLC, INC y CO. Una palabra
   escrita en mayúsculas no se convierte por eso en una sigla.
4. Si el nombre comercial es descriptivo o geográfico, asigna MACHEA.
5. En cualquier otro caso, asigna NO MACHEA.
[SALIDA]
Combina ambos campos. Devuelve exactamente una línea por cada fila
recibida, en el mismo orden, usando una de estas cuatro salidas:
LATINO CONFIRMADO - MACHEA
LATINO CONFIRMADO - NO MACHEA
NO LATINO - MACHEA
NO LATINO - NO MACHEA
Cuando recibas registros, devuelve únicamente las líneas de resultados.
Si recibes estas instrucciones sin registros, responde únicamente LISTO.
