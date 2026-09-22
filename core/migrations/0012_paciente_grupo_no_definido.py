# Generated manually for grupo no_definido

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_paciente_nombre_completo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paciente',
            name='grupo',
            field=models.CharField(
                choices=[
                    ('intervencion', 'Intervención (app + notificaciones)'),
                    ('control', 'Control'),
                    ('no_definido', 'No definido'),
                ],
                db_index=True,
                default='no_definido',
                max_length=20,
                verbose_name='Grupo del estudio',
            ),
        ),
    ]
