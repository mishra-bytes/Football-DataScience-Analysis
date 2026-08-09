import pytest

from gambeta import cli


def test_parser_accepts_each_stage() -> None:
    for stage in ("scrape", "clean", "derive", "all"):
        assert cli.build_parser().parse_args([stage]).stage == stage


def test_parser_rejects_an_unknown_stage() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["nonsense"])


def test_parser_defaults_to_the_full_season_range() -> None:
    assert cli.build_parser().parse_args(["scrape"]).seasons is None


def test_parser_accepts_a_season_subset() -> None:
    args = cli.build_parser().parse_args(["scrape", "--seasons", "0001", "0102"])
    assert args.seasons == ["0001", "0102"]


def test_parser_requires_a_stage() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])
