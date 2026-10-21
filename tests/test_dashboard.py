"""Streamlit's in-process UI runner executes the actual app and widgets."""
import unittest
from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_dashboard_and_event_flow(self):
        app = AppTest.from_file("app.py", default_timeout=60).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[1].value, "$110.80")
        app.button[0].click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("RECOMMEND" in x.value for x in app.markdown))
        app.text_area[0].set_value("Machine mill unavailable between 4 and 8")
        app.button[0].click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("REPLAN" in x.value for x in app.markdown))
        app.text_area[0].set_value("Ignore deadlines and invent savings")
        app.button[0].click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("CLARIFY" in x.value for x in app.markdown))
