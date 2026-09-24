from __future__ import annotations

from repolens.graph.diff_anchor import (
    anchor_ratchet_breach,
    format_github_actions_error,
    parse_added_import_lines,
)

_ORDERS_DIFF = """diff --git a/app/orders.py b/app/orders.py
index 1234567..abcdefg 100644
--- a/app/orders.py
+++ b/app/orders.py
@@ -39,6 +39,7 @@ class Order:
     def total(self):
         return self.amount
 
+from app import billing
 
     def charge(self):
         pass
"""


def test_parse_added_import_lines_finds_line_and_number():
    rows = parse_added_import_lines(_ORDERS_DIFF)
    assert ("app/orders.py", 42, "from app import billing") in rows


def test_parse_added_import_lines_skips_non_import_additions():
    diff = """diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,3 +1,4 @@
 x = 1
+foo = 2
+import os
"""
    rows = parse_added_import_lines(diff)
    assert rows == [("app/orders.py", 3, "import os")]


def test_anchor_ratchet_breach_prefers_fingerprint_intersection():
    added = [["app.orders", "app.billing", "app.notifications"]]
    hit = anchor_ratchet_breach(diff_text=_ORDERS_DIFF, added_fingerprints=added)
    assert hit == ("app/orders.py", 42, "from app import billing")


def test_anchor_ratchet_breach_returns_none_without_added_fingerprints():
    assert anchor_ratchet_breach(diff_text=_ORDERS_DIFF, added_fingerprints=[]) is None


def test_anchor_ratchet_breach_returns_none_when_no_import_in_diff():
    diff = """diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,2 +1,3 @@
 x = 1
+only_a_comment_change = 2
"""
    added = [["app.orders", "app.billing"]]
    assert anchor_ratchet_breach(diff_text=diff, added_fingerprints=added) is None


def test_anchor_ratchet_breach_prefers_representative_paths():
    diff = """diff --git a/app/other.py b/app/other.py
--- a/app/other.py
+++ b/app/other.py
@@ -1,2 +1,3 @@
 x = 1
+from app import billing
diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,2 +1,3 @@
 x = 1
+from app import notifications
"""
    added = [["app.orders", "app.billing", "app.notifications"]]
    hit = anchor_ratchet_breach(
        diff_text=diff,
        added_fingerprints=added,
        representative_paths=["app/orders.py"],
    )
    assert hit is not None
    assert hit[0] == "app/orders.py"


def test_format_github_actions_error():
    line = format_github_actions_error(
        "app/orders.py",
        42,
        "Ratchet breach: cyclicity increased",
    )
    assert line == (
        "::error file=app/orders.py,line=42::"
        "Ratchet breach%3A cyclicity increased"
    )


def test_format_github_actions_error_escapes_percent():
    line = format_github_actions_error("f.py", 1, "100% done")
    assert "100%25 done" in line


def test_anchor_ratchet_breach_empty_fingerprint_modules():
    assert anchor_ratchet_breach(diff_text=_ORDERS_DIFF, added_fingerprints=[[]]) is None


def test_anchor_skips_non_matching_import_when_better_exists():
    diff = """diff --git a/app/orders.py b/app/orders.py
--- a/app/orders.py
+++ b/app/orders.py
@@ -1,2 +1,4 @@
 x = 1
+import unrelated.widget
+from app import billing
"""
    added = [["app.orders", "app.billing"]]
    hit = anchor_ratchet_breach(diff_text=diff, added_fingerprints=added)
    assert hit == ("app/orders.py", 3, "from app import billing")


def test_parse_added_import_lines_multiline_from_import():
    diff = """diff --git a/pkg/__init__.py b/pkg/__init__.py
--- a/pkg/__init__.py
+++ b/pkg/__init__.py
@@ -1,2 +1,6 @@
 x = 1
+from app import (
+    billing,
+    notifications as n,
+)
"""
    rows = parse_added_import_lines(diff)
    assert len(rows) == 1
    assert rows[0][0] == "pkg/__init__.py"
