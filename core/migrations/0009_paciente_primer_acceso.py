from django.db import migrations, models
from django.utils import timezone


def backfill_primer_acceso(apps, schema_editor):
    Paciente = apps.get_model('core', 'Paciente')
    for p in Paciente.objects.select_related('user').iterator():
        if p.primer_acceso:
            continue
        candidatos = []
        if p.user and p.user.date_joined:
            candidatos.append(p.user.date_joined)
        if p.user and p.user.last_login:
            candidatos.append(p.user.last_login)
        if candidatos:
            p.primer_acceso = min(candidatos)
            p.save(update_fields=['primer_acceso'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_paciente_mmas_seguimiento_solicitado'),
    ]

    operations = [
        migrations.AddField(
            model_name='paciente',
            name='primer_acceso',
            field=models.DateTimeField(
                blank=True,
                help_text='Se registra automáticamente la primera vez que el paciente inicia sesión.',
                null=True,
                verbose_name='Primer acceso a la aplicación',
            ),
        ),
        migrations.RunPython(backfill_primer_acceso, migrations.RunPython.noop),
    ]
