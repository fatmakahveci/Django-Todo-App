from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LegacyMigrationTests(TransactionTestCase):
    def setUp(self):
        self.latest = MigrationExecutor(connection).loader.graph.leaf_nodes("tasks")
        executor = MigrationExecutor(connection)
        executor.migrate([("tasks", "0001_initial")])
        self.apps = executor.loader.project_state([("tasks", "0001_initial")]).apps
        self.owner = self.apps.get_model("auth", "User").objects.create(username="legacy-owner")
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE base_task (id integer PRIMARY KEY, user_id integer, title varchar(200), description text, complete bool, "create" datetime)')
            cursor.execute('INSERT INTO base_task VALUES (41, %s, %s, NULL, 0, %s)', [self.owner.pk, "Legacy task", "2024-01-02 10:00:00"])

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS base_task")
        MigrationExecutor(connection).migrate(self.latest)
        super().tearDown()

    def test_import_preserves_identity_and_adds_new_fields(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.latest)
        task = executor.loader.project_state(self.latest).apps.get_model("tasks", "Task").objects.get(pk=41)
        self.assertEqual(task.title, "Legacy task")
        self.assertEqual(task.user_id, self.owner.pk)
        self.assertEqual(task.create.year, 2024)
        self.assertEqual(task.priority, 2)
        self.assertIsNone(task.due_date)
        self.assertIsNone(task.description)
        # Applying migrate again must not duplicate imported data.
        MigrationExecutor(connection).migrate(self.latest)
        self.assertEqual(type(task).objects.count(), 1)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM base_task")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_two_nonempty_histories_stop_without_overwriting(self):
        self.apps.get_model("tasks", "Task").objects.create(title="Current task")
        with self.assertRaisesMessage(RuntimeError, "Both base_task and tasks_task contain data"):
            MigrationExecutor(connection).migrate(self.latest)
        self.assertEqual(self.apps.get_model("tasks", "Task").objects.get().title, "Current task")
