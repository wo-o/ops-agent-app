import ast
import http.server
import logging
import pathlib
import unittest


APP_PATH = pathlib.Path(__file__).parents[1] / "app.py"


def load_handler(db_func):
    source = APP_PATH.read_text()
    tree = ast.parse(source, filename=str(APP_PATH))
    handler = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "H"
    )
    namespace = {"http": http, "logging": logging, "db": db_func}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace["H"]


class TroublemakerRouteTest(unittest.TestCase):
    def test_troublemaker_is_disabled_without_database_access(self):
        calls = []

        def failing_db():
            calls.append(True)
            raise AssertionError("/troublemaker must not access the database")

        handler = load_handler(failing_db).__new__(load_handler(failing_db))
        handler.path = "/troublemaker"
        response = []
        handler._send = lambda code, body, ctype="text/plain": response.append((code, body, ctype))

        handler.do_GET()

        self.assertEqual([(200, "troublemaker disabled", "text/plain")], response)
        self.assertEqual([], calls)
