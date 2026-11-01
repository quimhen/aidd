# Verificación parcial con proveedores

`aidd provider run --coverage <ruta> --policy <ruta>` ejecuta un proveedor aprobado
por una unidad. Este resultado solo puede resolver el control de verificación de
`aidd guard commit` para los archivos cubiertos; no cierra una spec ni sustituye los
controles de aprobación, auditoría o verificación completa de cierre.

La cobertura `aidd-provider-coverage-v1` declara spec, unidad, proveedor y tareas;
cada tarea contiene listas explícitas de `targets`, `tests` y `rows`. La política
`aidd-provider-policy-v1` fija el proveedor Python y su SHA-256, el SHA-256 del
intérprete, el hash de la cobertura, argumentos como lista con un único `{receipt}`,
el entorno esperado y la lista ordenada de todos los inputs. Para una spec heredada,
este mapa puede citar las tareas y su verificación sin cambiar la tabla histórica de
FR; no presupone que una misma FR pruebe todas sus tareas.

La unidad debe tener un sello `unit_approved` vigente emitido por el flujo de
aprobación real. Su manifest debe incluir cobertura y política en `paths`, targets
en `targets`, tests en `inputs` o `targets`, y todos los archivos de su clausura en
los inputs de la política. El texto de tareas que se muestra al propietario debe
contener íntegros ambos objetos como JSON canónico: claves ordenadas, separadores
compactos y caracteres ASCII escapados. La relación entre tarea, archivos y pruebas
debe estar explícita en ese material; un archivo movido o renumerado no se presume
aprobado por similitud. No poner contraseñas en política ni argumentos.

El runner compara el índice Git antes de ejecutar, lanza el proveedor sin shell y
vincula el proceso y sus artefactos a la cobertura aprobada. Antes de autorizar un
commit, el guard vuelve a comprobar el sello, artefactos, entorno fijado y los bytes
de **todos** los inputs contra el índice, sin ejecutar el proveedor. Un resultado
posterior fallido o una diferencia no acreditada impide usar el resultado anterior.
Con entradas y política idénticas el runner reutiliza la observación vigente;
`--fresh` solicita expresamente una nueva ejecución si corresponde.

La integridad se basa en el equipo y el ejecutor AIDD locales; no es una firma contra
un usuario hostil con acceso de escritura al mismo equipo. Los proveedores deben
capturar por sí mismos el estado externo pertinente y el propietario debe aprobar la
política de entorno. Una versión o estado externo que no pueda establecerse queda
indeterminado. El guard no requiere que la base de datos siga arrancada.

El adaptador eDoc requiere una observación v5 generada durante su propia ejecución;
v4 y reportes previos no se convierten automáticamente en evidencia apta para guard.
La ejecución de base de datos sigue usando exclusivamente `db_verify.py` para las
bases de trabajo. No lanzar una prueba repetida solo para actualizar un sello.

La unidad debe incluir una fila propia en `## Verification` que invoque exactamente
`aidd provider run --coverage <ruta> --policy <ruta>`, declare `exit 0` y cubra las
tareas del mapa. Para cada archivo objetivo se incluyen todos sus copropietarios
afectados; ante ambigüedad se rechaza el uso parcial.

La política también fija `variables`, con SHA-256 de las variables de sistema
permitidas, y `catalogs`, con los directorios y filtros que determinan el conjunto
de entradas. El proveedor se lanza con Python aislado y solo esas variables; los
catálogos se comparan contra el disco, el índice y los inputs al ejecutar y al
verificar evidencia. Si un resultado ejecutado no puede registrarse, un marcador
pendiente impide reutilizar un resultado parcial anterior para los mismos archivos.
Esto no acredita hermeticidad frente a cambios hostiles de bibliotecas del sistema.
