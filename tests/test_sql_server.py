# encoding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

from __future__ import absolute_import, division, unicode_literals

from unittest import TestCase

from mo_parsing.debug import Debugger

from mo_sql_parsing import parse_sqlserver as parse


class TestSqlServer(TestCase):
    def test_select_top_5(self):
        sql = """
        select	TOP (5)
            country_code,
            impact_code,
            impact_description,
            number_sites
        from	EUNIS.v1.BISE_Country_Threats_Pressures_Number_Sites
        order by number_sites desc
        """
        result = parse(sql)

        self.assertEqual(
            result,
            {
                "top": 5,
                "select": [
                    {"value": "country_code"},
                    {"value": "impact_code"},
                    {"value": "impact_description"},
                    {"value": "number_sites"},
                ],
                "from": "EUNIS.v1.BISE_Country_Threats_Pressures_Number_Sites",
                "orderby": {"value": "number_sites", "sort": "desc"},
            },
        )

    def test_issue13_top(self):
        # https://docs.microsoft.com/en-us/sql/t-sql/queries/top-transact-sql?view=sql-server-ver15
        sql = "SELECT TOP 3 * FROM Customers"
        result = parse(sql)
        self.assertEqual(result, {"top": 3, "select": "*", "from": "Customers",})

        sql = "SELECT TOP func(value) WITH TIES *"
        result = parse(sql)
        self.assertEqual(
            result, {"top": {"value": {"func": "value"}, "ties": True}, "select": "*"},
        )

        sql = "SELECT TOP 1 PERCENT WITH TIES *"
        result = parse(sql)
        self.assertEqual(
            result, {"top": {"percent": 1, "ties": True}, "select": "*"},
        )

        sql = "SELECT TOP a(b) PERCENT item"
        result = parse(sql)
        self.assertEqual(
            result, {"top": {"percent": {"a": "b"}}, "select": {"value": "item"}},
        )

        sql = "SELECT TOP a(b) PERCENT"
        with self.assertRaises(Exception):
            parse(sql)  # MISSING ANY COLUMN

    def test_issue143a(self):
        sql = "Select [A] from dual"
        result = parse(sql)
        expected = {"select": {"value": "A"}, "from": "dual"}
        self.assertEqual(result, expected)

    def test_issue143b(self):
        sql = "Select [A] from [dual]"
        result = parse(sql)
        expected = {"select": {"value": "A"}, "from": "dual"}
        self.assertEqual(result, expected)

    def test_issue143c(self):
        sql = "Select [A] from dual [T1]"
        result = parse(sql)
        expected = {"select": {"value": "A"}, "from": {"value": "dual", "name": "T1"}}
        self.assertEqual(result, expected)

    def test_issue143d_quote(self):
        sql = 'Select ["]'
        result = parse(sql)
        expected = {"select": {"value": '"'}}
        self.assertEqual(result, expected)

    def test_issue143e_close(self):
        sql = "Select []]]"
        result = parse(sql)
        expected = {"select": {"value": "]"}}
        self.assertEqual(result, expected)

    def test_issue_52(self):
        sql = """SELECT [Timestamp] ,[RowsCount] ,[DataName] FROM [myDB].[myTable] where [Timestamp] >='2020-01-01' and [Timestamp]<'2020-12-31'"""
        result = parse(sql)
        expected = {
            "from": "myDB.myTable",
            "select": [
                {"value": "Timestamp"},
                {"value": "RowsCount"},
                {"value": "DataName"},
            ],
            "where": {"and": [
                {"gte": ["Timestamp", {"literal": "2020-01-01"}]},
                {"lt": ["Timestamp", {"literal": "2020-12-31"}]},
            ]},
        }
        self.assertEqual(result, expected)

    def test_issue_78_top(self):
        sql = """
            SELECT TOP 1000 *
            FROM (
                    SELECT result
                    FROM dbo.b AS B
                ) AS X
            WHERE expected <> result
        """
        result = parse(sql)
        expected = {
            "from": {
                "name": "X",
                "value": {
                    "from": {"name": "B", "value": "dbo.b"},
                    "select": {"value": "result"},
                },
            },
            "select": "*",
            "top": 1000,
            "where": {"neq": ["expected", "result"]},
        }
        self.assertEqual(result, expected)

    def test_issue_79a_no_lock(self):
        sql = """
        SELECT col1
        FROM table1 WITH (NOLOCK)
        """
        result = parse(sql)
        expected = {
            "from": {"value": "table1", "hint": "nolock"},
            "select": {"value": "col1"},
        }
        self.assertEqual(result, expected)

    def test_issue_79b_cross_apply(self):
        sql = """
        SELECT * FROM Department D 
        CROSS APPLY dbo.fn_GetAllEmployeeOfADepartment(D.DepartmentID)
        """
        result = parse(sql)
        expected = {
            "from": [
                {"name": "D", "value": "Department"},
                {"cross apply": {
                    "dbo.fn_getallemployeeofadepartment": "D.DepartmentID"
                }},
            ],
            "select": "*",
        }
        self.assertEqual(result, expected)

    def test_issue_79b_outer_apply(self):
        sql = """
        SELECT * FROM Department D 
        OUTER APPLY dbo.fn_GetAllEmployeeOfADepartment(D.DepartmentID) 
        """
        result = parse(sql)
        expected = {
            "from": [
                {"name": "D", "value": "Department"},
                {"outer apply": {
                    "dbo.fn_getallemployeeofadepartment": "D.DepartmentID"
                }},
            ],
            "select": "*",
        }
        self.assertEqual(result, expected)

    def test_issue_90_tablesample1(self):
        sql = "SELECT * FROM foo TABLESAMPLE bernoulli (1) WHERE a < 42"
        result = parse(sql)
        expected = {
            "from": {
                "tablesample": {"method": "bernoulli", "percent": 1},
                "value": "foo",
            },
            "select": "*",
            "where": {"lt": ["a", 42]},
        }
        self.assertEqual(result, expected)

    def test_issue_90_tablesample2(self):
        sql = "SELECT * FROM foo f TABLESAMPLE bernoulli (1) WHERE f.a < 42"
        result = parse(sql)
        expected = {
            "from": {
                "name": "f",
                "tablesample": {"method": "bernoulli", "percent": 1},
                "value": "foo",
            },
            "select": "*",
            "where": {"lt": ["f.a", 42]},
        }
        self.assertEqual(result, expected)

    def test_pivot_table(self):
        # FROM https://docs.microsoft.com/en-us/sql/t-sql/queries/from-using-pivot-and-unpivot?view=sql-server-ver16
        sql = """
        SELECT * FROM p  
        PIVOT  
        (  
        COUNT (id)  
        FOR E IN ( 250, 251, 256, 257, 260 )  
        ) AS pvt  
        """
        result = parse(sql)
        expected = {
            "select": "*",
            "from": {
                "name": "pvt",
                "pivot": {
                    "aggregate": {"count": "id"},
                    "for": "E",
                    "in": [250, 251, 256, 257, 260],
                },
                "value": "p",
            },
        }
        self.assertEqual(result, expected)
