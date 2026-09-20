from services import firebase_service as storage


def test_bad_storage_configuration_does_not_block_core(alice, monkeypatch, tmp_path):
    key=tmp_path/'bad.json'
    key.write_text('invalid private material')
    monkeypatch.setenv('FIREBASE_KEY_FILE',str(key))
    monkeypatch.setenv('FIREBASE_STORAGE_BUCKET','missing')
    def missing():
        raise ValueError('no app')
    monkeypatch.setattr(storage.firebase_admin,'get_app',missing)
    assert storage.init_firebase() is False
    assert alice.get('/').status_code==200
    assert alice.post('/api/workspaces',json={'name':'Offline'}).status_code==201
    assert alice.get('/api/overview/today').status_code==200
    assert alice.get('/api/overview/search?q=Offline').status_code==200
