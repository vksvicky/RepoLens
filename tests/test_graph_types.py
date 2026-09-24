from repolens.graph.types import EdgeKind, GraphResult, ImportEdge, ImportScope


def test_import_edge_defaults():
    e = ImportEdge(importer="pkg.a", imported="pkg.b", kind=EdgeKind.RUNTIME, scope=ImportScope.MODULE)
    assert e.line is None
    assert e.kind is EdgeKind.RUNTIME
