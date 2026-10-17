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
    assert response.headers['cache-control'] == 'no-store'
    extractor.extract_info.assert_called_once_with('https://www.youtube.com/watch?v=abcdefghijk', download=False)


@pytest.mark.parametrize('token', ['', 'next+/=page'])
def test_playlist_page_token_and_order(alice, monkeypatch, token):
    service = MagicMock()
    monkeypatch.setattr(music, '_youtube_service', lambda request: (service, None))
    service.playlistItems().list().execute.return_value = {
        'items': [
            {'id': 'item-1', 'snippet': {'title': 'First', 'resourceId': {'videoId': 'abcdefghijk'}, 'videoOwnerChannelTitle': 'Artist'}},
            {'id': 'missing-video', 'snippet': {}},
            {'id': 'item-2', 'snippet': {'title': 'Repeated video', 'resourceId': {'videoId': 'abcdefghijk'}}},
        ], 'nextPageToken': 'next-page'
    }
    response = alice.get('/api/music/playlist/items', params={'playlist_id': 'PL-test', 'page_token': token})
    assert response.status_code == 200
    data = response.json()
    assert [i['itemId'] for i in data['items']] == ['item-1', 'item-2']
    assert data['items'][0]['channel'] == 'Artist'
    assert data['next_page_token'] == 'next-page'
    args = service.playlistItems().list.call_args.kwargs
    assert args['maxResults'] == 50 and args['playlistId'] == 'PL-test'
    assert args.get('pageToken', '') == token


def test_playlist_last_page_error_and_validation(alice, monkeypatch):
    service = MagicMock()
    original_provider = music._youtube_service
    monkeypatch.setattr(music, '_youtube_service', lambda request: (service, None))
    service.playlistItems().list().execute.return_value = {'items': []}
    assert alice.get('/api/music/playlist/items?playlist_id=PL-test').json() == {'items': [], 'next_page_token': ''}
    service.playlistItems().list().execute.side_effect = RuntimeError('private-provider-response')
    response = alice.get('/api/music/playlist/items?playlist_id=PL-test&page_token=page2')
    assert response.status_code == 500 and 'private-provider-response' not in response.text
    assert alice.get('/api/music/playlist/items', params={'playlist_id': 'PL-test', 'page_token': 'x' * 2049}).status_code == 422
    alice.cookies.clear()
    # Remove provider stub so the real authentication boundary is exercised.
    monkeypatch.setattr(music, '_youtube_service', original_provider)
    assert alice.get('/api/music/playlist/items?playlist_id=PL-test').status_code == 401


def test_stream_prefers_direct_m4a_and_preserves_signed_url_expiry(alice, monkeypatch):
    from yt_dlp import YoutubeDL
    original = YoutubeDL
    options = []
    extractor = MagicMock()
    extractor.__enter__.return_value = extractor
    extractor.extract_info.return_value = dict(url='https://example.test/audio?expire=2000000000', title='Track', ext='m4a', protocol='https')
    def factory(opts):
        options.append(opts)
        return extractor
    monkeypatch.setattr(music.yt_dlp, 'YoutubeDL', factory)
    data = alice.get('/api/music/stream?video_id=abcdefghijk').json()
    assert data['expires_at'] == 2000000000 and data['format'] == 'm4a' and data['protocol'] == 'https'
    # Exercise yt-dlp's real selector against competing formats, without any provider network calls.
    with original({'quiet': True}) as ydl:
        selector = ydl.build_format_selector(options[0]['format'])
        def fmt(name, ext, protocol, quality):
            return dict(format_id=name, url='https://example.test/' + name, ext=ext,
                        protocol=protocol, vcodec='none', acodec='aac' if ext == 'm4a' else 'opus', abr=quality)
        formats = [fmt('direct-aac', 'm4a', 'https', 128), fmt('hls-aac', 'm4a', 'm3u8_native', 160), fmt('opus', 'webm', 'https', 192)]
        context = dict(formats=formats, has_merged_format=False, incomplete_formats=False)
        assert list(selector(context))[0]['format_id'] == 'direct-aac'
        context['formats'] = [formats[-1]]
        assert list(selector(context))[0]['format_id'] == 'opus'  # Fallback remains available.
