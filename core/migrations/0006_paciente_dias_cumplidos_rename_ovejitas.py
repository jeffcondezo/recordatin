# Generated manually for ovejitas → dias_cumplidos rename

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_cuidador_alertas'),
    ]

    operations = [
        migrations.RenameField(
            model_name='paciente',
            old_name='ovejitas',
            new_name='dias_cumplidos',
        ),
        migrations.RenameField(
            model_name='registrorecompensadiaria',
            old_name='ovejitas_antes',
            new_name='dias_antes',
        ),
        migrations.RenameField(
            model_name='registrorecompensadiaria',
            old_name='ovejitas_despues',
            new_name='dias_despues',
        ),
        migrations.AlterModelOptions(
            name='registrorecompensadiaria',
            options={
                'ordering': ['-fecha'],
                'verbose_name': 'Registro de cumplimiento diario',
                'verbose_name_plural': 'Registros de cumplimiento diario',
            },
        ),
        migrations.AlterField(
            model_name='paciente',
            name='dias_cumplidos',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='Días cumpliendo con fármacos',
            ),
        ),
    ]
