

## 250827-9:12
perfecto!. Tres cosillas: 
- la vista logout no está implementada; la vista teacher no incluye la selección de titulación/asignatura para dar de alta actividades (hay que tener en cuenta que cada profesor puede impartir clase en varias   titulaciones y a varios cursos);
- tanto para esta última vista como para la de estudiante no es correcto mostrar una lista de   todas las asignaturas, ya que hay muchas; debería haber un selector de titulación-curso-semestre. En el semestre las opciones  deberían ser "Primer Semestre", "Segundo Semestre", "Optativa", dependiendo de que el semestre sea 1,2,3. El TFG no debe listarse para profesores, ya que será el coordinador el único que pueda poner actividades (como fechas del calendario de   exámenes) 
- Habría que implementar un sistema de cambio de rol (para los roles permitidos) o un sistema de menú de vistas, que permita a un coordinador actuar como profesor, a un administrador tener acceso a los dashboards de coordinador y actuar como profesor y a un profesor (y por lo tanto a un coordinador y a un administrador) tener acceso a vistas tipo estudiante (supongo que esto no es diferente de establecer filtros en cada usuario)


## 250827-11:11 
En rol de profesor:
- La vista de selección de asignaturas no debería ser un listado desordenado. Propongo que se elija titulación y se obtenga una tabla ordenada por curso y semestre de asignaturas, cada una con un checkbox para marcarla.
- Una vez que un profesor ha elegido sus asignaturas, en su vista se deben mostrar esas asignaturas con un checkbox, de modo que al pulsar el botón "Añadir nueva actividad" se añada a esas asignaturas (eso permite añadir una actividad de forma simultánea a más de una asignatura). De este modo no es necesario elegir curso y semestre, porque se opera sobre las asignaturas del profesor.
- Cuando tenemos un selector de curso, en lugar de mostrar 1,2,3,4,10,1000 sería bueno mostrar "Primer Curso", "Segundo Curso", "Tercer Curso", "Cuarto Curso", "Optativa", y no mostrar la correspondiente a 1000 si estamos en vista profesor, ya que es el TFG, pero si mostrarlo si somos coordinador, y en este caso en el selector mostrar "TFE" (porque en realidad puede ser TFG o TFM).
