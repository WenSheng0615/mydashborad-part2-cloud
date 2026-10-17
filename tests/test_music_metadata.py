from unittest.mock import MagicMock

import pytest
from routers import music


@pytest.mark.parametrize('provider,expected', [({'channel': 'Channel name', 'uploader': 'Uploader'}, 'Channel name'), ({'uploader': 'Uploader'}, 'Uploader'), ({}, '')])
def test_stream_supplies_metadata_without_extra_provider_request(alice, monkeypatch, provider, expected):
    extractor = MagicMock()
    extractor.__enter__.return_value = extractor
    extractor.extract_info.return_value = dict(url='https://example.test/audio', title='Track title',
                                               thumbnail='https://example.test/cover.jpg', **provider)
    monkeypatch.setattr(music.yt_dlp, 'YoutubeDL', lambda _: extractor)
    response = alice.get('/api/music/stream?video_id=abcdefghijk')
    assert response.status_code == 200
    assert response.json()['channel'] == expected
    assert response.json()['title'] == 'Track title'
    extractor.extract_info.assert_called_once_with('https://www.youtube.com/watch?v=abcdefghijk', download=False)
