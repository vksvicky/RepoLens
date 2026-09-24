from repolens.graph.cycles import cyclicity, strongly_connected_components


def test_two_node_cycle():
    sccs = strongly_connected_components([("a", "b"), ("b", "a")])
    cyclic = [s for s in sccs if len(s) >= 2]
    assert len(cyclic) == 1
    assert set(cyclic[0]) == {"a", "b"}
    assert cyclicity(cyclic) == 4


def test_acyclic():
    sccs = strongly_connected_components([("a", "b"), ("b", "c")])
    assert [s for s in sccs if len(s) >= 2] == []
    assert cyclicity([]) == 0
