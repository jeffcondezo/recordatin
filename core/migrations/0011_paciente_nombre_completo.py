from django.db import migrations, models


def unificar_nombres(apps, schema_editor):
    Paciente = apps.get_model('core', 'Paciente')
    for p in Paciente.objects.all():
        nombre = (p.nombre or '').strip()
        apellidos = (p.apellidos or '').strip()
        if not apellidos:
            continue
        completo = f'{nombre} {apellidos}'.strip()
        # Evitar duplicar si ya estaba unificado
        if nombre.endswith(apellidos):
            completo = nombre
        p.nombre = completo[:250]
        p.apellidos = ''
        p.save(update_fields=['nombre', 'apellidos'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_paciente_dni_edad_enfermedades'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paciente',
            name='nombre',
            field=models.CharField(max_length=250, verbose_name='Nombres y apellidos'),
        ),
        migrations.AlterField(
            model_name='paciente',
            name='apellidos',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Campo antiguo; el nombre completo va en «Nombres y apellidos».',
                max_length=150,
                verbose_name='Apellidos (legado)',
            ),
        ),
        migrations.RunPython(unificar_nombres, noop_reverse),
    ]
