"""Unit tests for Database Migration & Schema Optimizer."""

import unittest
from saleha.core.db_optimizer import db_optimizer


class DBOptimizerTests(unittest.TestCase):

    def test_schema_analysis_and_migration_generation(self):
        ddl = """
        CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));
        CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, amount DECIMAL);
        """
        res = db_optimizer.analyze_schema(ddl)
        self.assertEqual(len(res.tables_found), 2)
        self.assertIn("users", res.tables_found)
        self.assertIn("orders", res.tables_found)
        self.assertTrue(len(res.missing_indexes) > 0)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_user_id", res.migration_sql_up)
        self.assertIn("DROP INDEX IF EXISTS idx_user_id", res.migration_sql_down)


if __name__ == "__main__":
    unittest.main()

