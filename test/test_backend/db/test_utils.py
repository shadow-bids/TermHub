"""Tests

How to run:
    python -m unittest discover
"""
import os
import sys
import unittest
from pathlib import Path
from typing import Dict, List

from sqlalchemy.engine.base import Connection

TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = Path(TEST_DIR).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from backend.db.utils import get_db_connection, insert_fetch_statuses, run_sql, select_failed_fetches, sql_query


class FetchAuditTestRunner(unittest.TestCase):
    n1: int = None
    mock_data: List[Dict] = None
    con: Connection = None

    @classmethod
    def setUpClass(cls):
        """setUp"""
        cls.con = get_db_connection(schema='')
        cls.n1 = sql_query(cls.con, 'SELECT COUNT(*) FROM fetch_audit;')[0]['count']
        insert_fetch_statuses(cls.mock_data)

    @classmethod
    def tearDownClass(cls):
        """tearDown"""
        run_sql(cls.con, f"DELETE FROM fetch_audit WHERE comment = 'Unit testing.';")
        n3 = sql_query(cls.con, 'SELECT COUNT(*) FROM fetch_audit;')[0]['count']
        # https://stackoverflow.com/questions/43483683/python-unittest-teardownclass-for-the-instance-how-to-have-it
        assert cls.n1 == n3  # .assertEqual() deosn't work here; see above
        cls.con.close()


class TestBackendDbUtilsFetchAudit(FetchAuditTestRunner):
    mock_data = [{'table': 'code_sets', 'primary_key': codeset_id, 'status_initially': 'fail-excessive-items',
                  'comment': 'Unit testing.'} for codeset_id in [1, 2, 3]] + \
                [{'table': 'code_sets', 'primary_key': codeset_id, 'status_initially': 'fail-excessive-members',
                  'comment': 'Unit testing.'} for codeset_id in [1, 2, 3]] + \
                [{'table': 'code_sets', 'primary_key': codeset_id, 'status_initially': 'fail-0-members',
                  'comment': 'Unit testing.'} for codeset_id in [1, 2, 3]]

    def test_insert_fetch_status(self):
        """Test insert_fetch_status()"""
        with get_db_connection(schema='') as con:
            n2 = sql_query(con, 'SELECT COUNT(*) FROM fetch_audit;')[0]['count']
            self.assertEqual(n2 - self.n1, len(self.mock_data))

    def test_select_failed_fetches(self):
        """Test select_failed_fetches()"""
        results = select_failed_fetches()
        self.assertEqual(len(results), self.n1 + len(self.mock_data))


# Uncomment this and run this file and run directly to run all tests
# if __name__ == '__main__':
#     unittest.main()
