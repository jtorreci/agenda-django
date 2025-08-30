"""
Command para migrar usuarios existentes del sistema legacy al nuevo sistema de perfiles
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import CustomUser, TipoPerfil, AsignacionPerfil


class Command(BaseCommand):
    help = 'Migra usuarios existentes del sistema de roles al nuevo sistema de perfiles dinámicos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta una simulación sin hacer cambios reales',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la migración incluso si el usuario ya tiene perfiles asignados',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('=== Migración de Usuarios a Sistema de Perfiles ==='))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se realizarán cambios reales'))
        
        # Verificar que existan los tipos de perfil
        try:
            perfil_estudiante = TipoPerfil.objects.get(codigo='STUDENT')
            perfil_profesor = TipoPerfil.objects.get(codigo='TEACHER') 
            perfil_coordinador = TipoPerfil.objects.get(codigo='COORDINATOR')
            perfil_admin = TipoPerfil.objects.get(codigo='ADMIN')
        except TipoPerfil.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'Error: No se encontró un tipo de perfil necesario. Ejecuta las migraciones primero.')
            )
            return
        
        # Obtener usuarios a migrar
        usuarios = CustomUser.objects.all()
        migrados = 0
        saltados = 0
        errores = 0
        
        with transaction.atomic():
            for usuario in usuarios:
                # Verificar si ya tiene perfiles asignados
                perfiles_actuales = usuario.asignaciones_perfil.filter(activa=True).count()
                
                if perfiles_actuales > 0 and not force:
                    self.stdout.write(
                        self.style.WARNING(f'Saltando {usuario.username}: ya tiene {perfiles_actuales} perfil(es) asignado(s)')
                    )
                    saltados += 1
                    continue
                
                try:
                    perfiles_a_asignar = []
                    
                    # Mapear rol legacy a perfiles
                    if usuario.role == 'STUDENT':
                        perfiles_a_asignar = [perfil_estudiante]
                    elif usuario.role == 'TEACHER':
                        perfiles_a_asignar = [perfil_profesor]
                    elif usuario.role == 'COORDINATOR':
                        # Los coordinadores son también profesores
                        perfiles_a_asignar = [perfil_profesor, perfil_coordinador]
                    elif usuario.role == 'ADMIN':
                        # Los admins tienen todos los perfiles
                        perfiles_a_asignar = [perfil_profesor, perfil_coordinador, perfil_admin]
                    
                    # Asignar perfiles
                    if not dry_run:
                        for perfil in perfiles_a_asignar:
                            AsignacionPerfil.objects.get_or_create(
                                usuario=usuario,
                                tipo_perfil=perfil,
                                defaults={
                                    'activa': True,
                                    'notas': f'Migrado automáticamente desde rol legacy: {usuario.role}'
                                }
                            )
                    
                    perfiles_nombres = [p.nombre for p in perfiles_a_asignar]
                    self.stdout.write(
                        self.style.SUCCESS(f'OK {usuario.username} ({usuario.role}) -> {", ".join(perfiles_nombres)}')
                    )
                    migrados += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error procesando {usuario.username}: {str(e)}')
                    )
                    errores += 1
        
        # Resumen
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== RESUMEN ==='))
        self.stdout.write(f'Usuarios migrados: {migrados}')
        self.stdout.write(f'Usuarios saltados: {saltados}')
        if errores > 0:
            self.stdout.write(self.style.ERROR(f'Errores: {errores}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Esto fue una simulación. Ejecuta sin --dry-run para aplicar los cambios.'))
        else:
            self.stdout.write(self.style.SUCCESS('Migración completada exitosamente.'))