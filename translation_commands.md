# 🌍 Django Translation Commands

## Compilar traducciones (después de editar archivos .po)

```bash
# Activa el entorno virtual
c:\venv\django\Scripts\activate

# Compila las traducciones
python manage.py compilemessages

# O específicamente para español:
python manage.py compilemessages -l es
```

## Extraer nuevas cadenas traducibles (cuando añadas más strings)

```bash
# Activa el entorno virtual  
c:\venv\django\Scripts\activate

# Extrae strings de archivos Python y HTML
python manage.py makemessages -l es -e html,py

# Con más verbosidad para ver el proceso:
python manage.py makemessages -l es -e html,py --verbosity=2
```

## Verificar traducciones

```bash
# Ver estadísticas de traducción
python manage.py makemessages -l es --dry-run

# Verificar archivos generados
ls -la locale/es/LC_MESSAGES/
```

## Workflow completo de traducción

1. **Marcar strings en código**:
   ```python
   from django.utils.translation import gettext_lazy as _
   mensaje = _('Texto a traducir')
   ```

2. **Marcar strings en templates**:
   ```html
   {% load i18n %}
   <h1>{% trans "Título a traducir" %}</h1>
   ```

3. **Extraer strings**:
   ```bash
   python manage.py makemessages -l es -e html,py
   ```

4. **Editar traducciones** en `locale/es/LC_MESSAGES/django.po`:
   ```po
   msgid "Hello"
   msgstr "Hola"
   ```

5. **Compilar traducciones**:
   ```bash
   python manage.py compilemessages
   ```

6. **Reiniciar servidor**:
   ```bash
   python manage.py runserver
   ```

## Archivos importantes

- **Settings**: `agenda_academica/settings.py` (configuración de i18n)
- **Traducciones**: `locale/es/LC_MESSAGES/django.po` (archivo editable)
- **Compilado**: `locale/es/LC_MESSAGES/django.mo` (archivo binario generado)

## Troubleshooting

Si tienes problemas con los scripts Python, usa directamente los comandos de Django mostrados arriba. Son más confiables y están mejor documentados.