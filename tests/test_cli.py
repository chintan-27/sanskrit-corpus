from pathlib import Path

import pytest

from sanskrit_corpus.cli import main
from sanskrit_corpus.internet_archive import IaPullResult


def test_dry_run_writes_manifests(tmp_path) -> None:
    code = main(["pull", "--source", "ud_sanskrit_vedic", "--dry-run", "--root", str(tmp_path)])

    assert code == 0
    assert (tmp_path / "data" / "manifests" / "source_registry.jsonl").exists()
    assert (tmp_path / "data" / "manifests" / "pull_runs.jsonl").exists()


def test_unknown_source_fails(tmp_path) -> None:
    code = main(["pull", "--source", "missing", "--dry-run", "--root", str(tmp_path)])

    assert code == 2


def test_pipeline_commands(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw" / "itihasa"
    raw.mkdir(parents=True)
    (raw / "train.sn.csv").write_text("धर्मः\n", encoding="utf-8")
    (raw / "train.en.csv").write_text("Dharma\n", encoding="utf-8")

    assert main(["process", "--source", "itihasa", "--root", str(tmp_path)]) == 0
    assert main(["validate", "--source", "itihasa", "--root", str(tmp_path)]) == 0
    assert main(["report", "--root", str(tmp_path)]) == 0
    assert main(["audit", "--root", str(tmp_path)]) == 0
    assert main(["export", "--profile", "releasable", "--root", str(tmp_path)]) == 0


def test_cli_reports_existing_export(tmp_path: Path) -> None:
    release = tmp_path / "data" / "releases" / "releasable.jsonl"
    release.parent.mkdir(parents=True)
    release.write_text("existing", encoding="utf-8")

    assert main(["export", "--profile", "releasable", "--root", str(tmp_path)]) == 2


def test_ia_cli_prints_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(
        "sanskrit_corpus.cli.pull_internet_archive",
        lambda *args, **kwargs: IaPullResult("ok", 1, 2, 3, str(manifest)),
    )

    assert main(["ia-pull", "--root", str(tmp_path)]) == 0


def test_negative_cli_values_are_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["ia-pull", "--max-gb", "-1"])
