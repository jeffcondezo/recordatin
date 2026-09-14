from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_paciente_dias_cumplidos_rename_ovejitas'),
    ]

    operations = [
        migrations.AddField(
            model_name='paciente',
            name='codigo_estudio',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=20,
                null=True,
                unique=True,
                verbose_name='Código de estudio',
            ),
        ),
        migrations.AddField(
            model_name='paciente',
            name='fecha_ingreso_estudio',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Fecha de ingreso al estudio',
            ),
        ),
        migrations.AddField(
            model_name='paciente',
            name='grupo',
            field=models.CharField(
                choices=[
                    ('intervencion', 'Intervención (app + notificaciones)'),
                    ('control', 'Control'),
                ],
                db_index=True,
                default='intervencion',
                max_length=20,
                verbose_name='Grupo del estudio',
            ),
        ),
        migrations.AddField(
            model_name='paciente',
            name='sexo',
            field=models.CharField(
                blank=True,
                choices=[
                    ('M', 'Masculino'),
                    ('F', 'Femenino'),
                    ('O', 'Otro / no especifica'),
                ],
                max_length=1,
                verbose_name='Sexo',
            ),
        ),
        migrations.CreateModel(
            name='EvaluacionMMAS8',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('momento', models.CharField(
                    choices=[
                        ('basal', 'Basal (inicio)'),
                        ('seguimiento', 'Seguimiento'),
                    ],
                    max_length=20,
                )),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('respuestas', models.JSONField(
                    help_text='Respuestas MMAS-8: items 1-7 sí/no e item 8 escala 0-4.',
                )),
                ('puntaje', models.DecimalField(decimal_places=2, max_digits=4)),
                ('categoria', models.CharField(
                    choices=[
                        ('alta', 'Adherencia alta'),
                        ('media', 'Adherencia media'),
                        ('baja', 'Adherencia baja'),
                    ],
                    max_length=10,
                )),
                ('registrado_por', models.CharField(
                    choices=[
                        ('paciente', 'Paciente'),
                        ('admin', 'Administrador'),
                    ],
                    default='paciente',
                    max_length=20,
                )),
                ('paciente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evaluaciones_mmas8',
                    to='core.paciente',
                )),
            ],
            options={
                'verbose_name': 'Evaluación MMAS-8',
                'verbose_name_plural': 'Evaluaciones MMAS-8',
                'ordering': ['momento', '-fecha'],
            },
        ),
        migrations.AddConstraint(
            model_name='evaluacionmmas8',
            constraint=models.UniqueConstraint(
                fields=('paciente', 'momento'),
                name='unique_mmas8_por_momento',
            ),
        ),
    ]
