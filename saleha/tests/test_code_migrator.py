"""Unit tests for 1-Click Polyglot Codebase Migrator."""

from __future__ import annotations

import unittest
from saleha.core.code_migrator import CodeMigrator, MigrationResult


class CodeMigratorTests(unittest.TestCase):

    def setUp(self):
        self.migrator = CodeMigrator()

    def test_migrate_js_to_ts(self):
        js_code = """const express = require('express');
function add(x, y) {
    return x + y;
}
module.exports = add;
"""
        res = self.migrator.migrate(js_code, source="js", target="ts")
        self.assertEqual(res.source_framework, "javascript")
        self.assertEqual(res.target_framework, "typescript")
        self.assertIn("import express from 'express';", res.migrated_code)
        self.assertIn("function add(x: any, y: any): any", res.migrated_code)
        self.assertIn("export default add;", res.migrated_code)
        self.assertGreater(res.changes_count, 0)

    def test_migrate_flask_to_fastapi(self):
        flask_code = """from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/items', methods=['POST'])
def create_item():
    return jsonify({'created': True})
"""
        res = self.migrator.migrate(flask_code, source="flask", target="fastapi")
        self.assertTrue(res.is_valid_syntax)
        self.assertEqual(res.target_framework, "fastapi")
        self.assertIn("from fastapi import FastAPI", res.migrated_code)
        self.assertIn("app = FastAPI(", res.migrated_code)
        self.assertIn("@app.get('/health')", res.migrated_code)
        self.assertIn("@app.post('/items')", res.migrated_code)

    def test_migrate_unittest_to_pytest(self):
        unittest_code = """import unittest

class TestMath(unittest.TestCase):
    def test_add(self):
        self.assertEqual(1 + 1, 2)
        self.assertTrue(True)
        self.assertIn('a', 'abc')

if __name__ == '__main__':
    unittest.main()
"""
        res = self.migrator.migrate(unittest_code, source="unittest", target="pytest")
        self.assertTrue(res.is_valid_syntax)
        self.assertEqual(res.target_framework, "pytest")
        self.assertIn("class TestMath:", res.migrated_code)
        self.assertIn("assert 1 + 1 == 2", res.migrated_code)
        self.assertIn("assert True", res.migrated_code)
        self.assertIn("assert 'a' in 'abc'", res.migrated_code)
        self.assertNotIn("unittest.main()", res.migrated_code)


if __name__ == "__main__":
    unittest.main()
