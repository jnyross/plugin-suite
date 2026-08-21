import unittest


class SmokeTests(unittest.TestCase):
    def test_package_layout_imports(self):
        import contracts
        import engines
        import engines.gates
        import ops
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
