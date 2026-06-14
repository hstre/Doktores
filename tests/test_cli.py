"""The CLI runs the circle offline and drops valid packages."""

from __future__ import annotations

import json

from doktores import validate_research_output
from doktores.cli import main


def test_cli_prints_package(capsys):
    code = main(["routing prefers locality but memory prefers recency", "--topic", "routing",
                 "--id", "C-12"])
    assert code == 0
    out = capsys.readouterr().out
    # The first block is the JSON package list; validate it round-trips and is schema-valid.
    payload = out[out.index("[") : out.rindex("]") + 1]
    packages = json.loads(payload)
    assert len(packages) == 1
    assert validate_research_output(packages[0]) == []


def test_cli_writes_inbox(tmp_path, capsys):
    inbox = tmp_path / "research_inbox.json"
    code = main(["x vs y under drift", "--topic", "routing", "--inbox", str(inbox)])
    assert code == 0
    assert "wrote 1 new package" in capsys.readouterr().out
    assert validate_research_output(json.loads(inbox.read_text())[0]) == []


def test_cli_nothing_to_do_returns_2(capsys):
    assert main([]) == 2
    assert "nothing to research" in capsys.readouterr().out
