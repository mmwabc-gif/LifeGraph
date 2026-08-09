from pathlib import Path
import hashlib
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

MIB=1024*1024

def make_client(data_dir: Path):
    return TestClient(create_app(Settings(data_dir=data_dir, session_ttl_seconds=60)))

def init(c):
    r=c.post('/api/v1/auth/initialize',json={'display_name':'x','birth_date':'1990-01-01','target_age':100,'timezone':'Asia/Shanghai','pin':'123456','recovery_secret':'abcdefghijklmnop'})
    return {'Authorization':f"Bearer {r.json()['data']['token']}"}

def test_export_survives_missing_preview(tmp_path: Path):
    data=tmp_path/'vault'; c=make_client(data); h=init(c)
    payload=b'v'*(MIB+123)
    r=c.post('/api/v1/materials/large/uploads',headers=h,json={'filename':'x.mp4','media_type':'video/mp4','size_bytes':len(payload),'chunk_size':MIB})
    assert r.status_code==200, r.text
    u=r.json()['data']
    pr=c.put(f"/api/v1/materials/large/uploads/{u['session_id']}/preview",headers={**h,'Content-Type':'image/jpeg'},content=b'fake-jpeg-preview'*100)
    assert pr.status_code==200,pr.text
    for i,off in enumerate(range(0,len(payload),MIB)):
        rr=c.put(f"/api/v1/materials/large/uploads/{u['session_id']}/chunks/{i}",headers={**h,'Content-Type':'application/octet-stream'},content=payload[off:off+MIB])
        assert rr.status_code==200,rr.text
    fin=c.post(f"/api/v1/materials/large/uploads/{u['session_id']}/finalize",headers=h)
    assert fin.status_code==200,fin.text
    m=fin.json()['data']
    p=data/'previews'/m['id'][:2].lower()/f"{m['id']}.lgpreview"
    assert p.is_file(); p.unlink()
    check=c.get('/api/v1/backup/check',headers=h)
    assert check.status_code==200, check.text
    assert check.json()['data']['preview_files_missing']==1
    exp=c.get('/api/v1/backup/export',headers=h)
    assert exp.status_code==200, exp.text
    auto=c.post('/api/v1/backup/auto/run',headers=h)
    assert auto.status_code==200, auto.text
