from sanskrit_corpus.cli import main


def test_dry_run_writes_manifests(tmp_path) -> None:
    code = main(["pull", "--source", "ud_sanskrit_vedic", "--dry-run", "--root", str(tmp_path)])

    assert code == 0
    assert (tmp_path / "data" / "manifests" / "source_registry.jsonl").exists()
    assert (tmp_path / "data" / "manifests" / "pull_runs.jsonl").exists()


def test_unknown_source_fails(tmp_path) -> None:
    code = main(["pull", "--source", "missing", "--dry-run", "--root", str(tmp_path)])

    assert code == 2
