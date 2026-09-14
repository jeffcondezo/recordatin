from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_estudio_mmas8'),
    ]

    operations = [
        migrations.AddField(
            model_name='paciente',
            name='mmas_seguimiento_solicitado',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Si está activo, al iniciar sesión el paciente verá el cuestionario '
                    'de seguimiento (si aún no lo ha respondido).'
                ),
                verbose_name='Solicitar MMAS-8 de seguimiento al entrar',
            ),
        ),
    ]
