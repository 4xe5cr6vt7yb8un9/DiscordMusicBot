import discord
from src.models.song import Song

def test_song_initialization_and_duration_formatting():
    # Test short duration (minutes and seconds)
    song1 = Song(
        title="Test Song 1",
        webpage_url="https://www.youtube.com/watch?v=12345",
        stream_url="https://googlevideo.com/videoplayback/test",
        duration=225,
        uploader="Test Artist",
        thumbnail_url="https://img.youtube.com/vi/12345/hqdefault.jpg",
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song1.formatted_duration == "03:45"

    # Test long duration (hours, minutes, seconds)
    song2 = Song(
        title="Long Track",
        webpage_url="https://www.youtube.com/watch?v=67890",
        stream_url="https://googlevideo.com/videoplayback/long",
        duration=3665,
        uploader="Ambient Musician",
        thumbnail_url=None,
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song2.formatted_duration == "01:01:05"

    # Test live stream or unknown duration
    song3 = Song(
        title="Live Stream",
        webpage_url="https://www.youtube.com/watch?v=live",
        stream_url="https://googlevideo.com/videoplayback/live",
        duration=0,
        uploader="Live Channel",
        thumbnail_url=None,
        requester_name="Aiden",
        requester_id=111222333,
    )
    assert song3.formatted_duration == "Live / Unknown"

def test_song_create_embed():
    song = Song(
        title="Sample Song",
        webpage_url="https://www.youtube.com/watch?v=abcde",
        stream_url="https://stream.url",
        duration=180,
        uploader="Channel Name",
        thumbnail_url="https://thumbnail.url/img.jpg",
        requester_name="Listener",
        requester_id=999888,
    )
    embed = song.create_embed(status="Enqueued")
    assert isinstance(embed, discord.Embed)
    assert "Enqueued" in embed.title
    assert embed.description == "[Sample Song](https://www.youtube.com/watch?v=abcde)"
    assert embed.thumbnail.url == "https://thumbnail.url/img.jpg"

    fields = {f.name: f.value for f in embed.fields}
    assert fields["Duration"] == "03:00"
    assert fields["Channel"] == "Channel Name"
    assert fields["Requested By"] == "Listener"
