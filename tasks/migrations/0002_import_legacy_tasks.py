from django.db import migrations


def import_legacy_tasks(apps, schema_editor):
    connection = schema_editor.connection
    if "base_task" not in connection.introspection.table_names():
        return
    task = apps.get_model("tasks", "Task")
    # Never silently merge two histories: colliding IDs could refer to different owners.
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM base_task")
        if not cursor.fetchone()[0]:
            return
        if task.objects.using(connection.alias).exists():
            raise RuntimeError("Both base_task and tasks_task contain data. Back up and reconcile them before migrating.")
        cursor.execute(
            'INSERT INTO tasks_task (id, user_id, title, description, complete, "create") '
            'SELECT id, user_id, title, description, complete, "create" FROM base_task'
        )


class Migration(migrations.Migration):
    dependencies = [("tasks", "0001_initial")]
    operations = [migrations.RunPython(import_legacy_tasks, migrations.RunPython.noop)]
