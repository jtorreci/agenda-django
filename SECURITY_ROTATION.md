# Rotación de secretos de producción

## Estado

`.env.production` fue retirado del índice de Git y se conserva únicamente como archivo local. No debe volver a versionarse.

## Acciones obligatorias antes del despliegue

1. Rotar la `SECRET_KEY` de Django y invalidar las sesiones existentes si procede.
2. Rotar credenciales de base de datos, correo y cualquier token que hubiese figurado en el archivo.
3. Crear `/home/jtorreci/agenda/agenda-django/.env.garnocex` exclusivamente en el servidor, con permisos del usuario de despliegue y fuera de Git.
4. Registrar en GitHub Actions solo los secretos mínimos de despliegue; nunca copiar el archivo completo.
5. Revocar las credenciales SSH que se expusieron en la documentación y usar una identidad de despliegue dedicada.

## Verificación

```bash
git ls-files --error-unmatch .env.production
git check-ignore -v .env.production
```

El primer comando debe fallar tras confirmar la eliminación en un commit. El segundo debe mostrar la regla de `.gitignore`.
