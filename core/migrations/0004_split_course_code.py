import django.contrib.postgres.indexes
import django.db.models.functions.text
from django.db import migrations, models


def backfill_department_and_course_code(apps, schema_editor):
    """
    Split existing rows' combined code (e.g. "CSCI 0320") into the new
    department_code/course_code columns, on the first space only, so anything
    unusual after the department stays intact in course_code.
    """
    CourseSession = apps.get_model("core", "CourseSession")
    for session in CourseSession.objects.all():
        department_code, _, course_code = session.code.partition(" ")
        session.department_code = department_code
        session.course_code = course_code
        session.save(update_fields=["department_code", "course_code"])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_coursesession_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursesession',
            name='department_code',
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AddField(
            model_name='coursesession',
            name='course_code',
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.RunPython(backfill_department_and_course_code, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='coursesession',
            name='department_code',
            field=models.CharField(max_length=16),
        ),
        migrations.AlterField(
            model_name='coursesession',
            name='course_code',
            field=models.CharField(max_length=64),
        ),
        migrations.RemoveConstraint(
            model_name='coursesession',
            name='unique_code_section_sem',
        ),
        migrations.RemoveIndex(
            model_name='coursesession',
            name='coursesession_trgm_idx',
        ),
        migrations.RemoveField(
            model_name='coursesession',
            name='code',
        ),
        migrations.AddField(
            model_name='coursesession',
            name='code',
            field=models.GeneratedField(
                db_persist=True,
                expression=django.db.models.functions.text.Concat(
                    'department_code', models.Value(' '), 'course_code'
                ),
                output_field=models.CharField(max_length=64),
            ),
        ),
        migrations.AddIndex(
            model_name='coursesession',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['code', 'title'],
                name='coursesession_trgm_idx',
                opclasses=['gin_trgm_ops', 'gin_trgm_ops'],
            ),
        ),
        migrations.AddConstraint(
            model_name='coursesession',
            constraint=models.UniqueConstraint(
                fields=('code', 'section', 'sem_id'), name='unique_code_section_sem'
            ),
        ),
    ]
