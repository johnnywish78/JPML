from app.domain import (
    Episode,
    MediaFile,
    Movie,
    Person,
    Season,
    TVShow,
)


def test_movie_can_have_multiple_files_and_people() -> None:
    movie = Movie(
        title="Blade Runner",
        year=1982,
        imdb_id="tt0083658",
    )

    movie.files.append(
        MediaFile(
            path="/movies/Blade Runner/Blade Runner.mkv",
            filename="Blade Runner.mkv",
            extension=".mkv",
        )
    )

    movie.files.append(
        MediaFile(
            path="/movies/Blade Runner/Blade Runner 4K.mkv",
            filename="Blade Runner 4K.mkv",
            extension=".mkv",
        )
    )

    movie.people.append(
        Person(
            name="Ridley Scott",
            imdb_id="nm0000631",
        )
    )

    assert movie.title == "Blade Runner"
    assert movie.year == 1982
    assert movie.imdb_id == "tt0083658"
    assert len(movie.files) == 2
    assert len(movie.people) == 1


def test_tv_show_hierarchy() -> None:
    show = TVShow(
        title="Breaking Bad",
        year=2008,
        imdb_id="tt0903747",
    )

    season = Season(
        season_number=1,
        title="Season 1",
    )

    episode = Episode(
        title="Pilot",
        episode_number=1,
        season_number=1,
        imdb_id="tt0959621",
    )

    episode.files.append(
        MediaFile(
            path="/tv/Breaking Bad/Season 01/S01E01.mkv",
            filename="S01E01.mkv",
            extension=".mkv",
        )
    )

    season.episodes.append(episode)
    show.seasons.append(season)

    assert show.title == "Breaking Bad"
    assert len(show.seasons) == 1
    assert show.seasons[0].season_number == 1
    assert len(show.seasons[0].episodes) == 1
    assert show.seasons[0].episodes[0].title == "Pilot"
    assert len(show.seasons[0].episodes[0].files) == 1


def test_domain_objects_are_storage_independent() -> None:
    movie = Movie(title="Test")

    assert movie.id is None
    assert movie.files == []
    assert movie.people == []

    movie.files.append(
        MediaFile(
            path="/tmp/test.mp4",
            filename="test.mp4",
        )
    )

    assert movie.files[0].path == "/tmp/test.mp4"
