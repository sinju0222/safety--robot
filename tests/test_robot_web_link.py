"""Offline integration checks: real map storage, map->zone projection, hazards/ack."""
import json
import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import main as app_main
import telemetry_api as telemetry
import websocket_server as websock
import robot_event_api as robot_events


def test_robot_to_web_pipeline(tmp_path, monkeypatch):
    root = tmp_path / 'robot_data'
    monkeypatch.setattr(telemetry, 'DATA_ROOT', root)
    monkeypatch.setattr(websock, 'DATA_ROOT', root)
    monkeypatch.setattr(app_main, 'DATA_ROOT', root)
    monkeypatch.setattr(app_main, 'STATE_FILE', root / 'workplaces.json')
    monkeypatch.setattr(robot_events, 'DATA_DIR', tmp_path / 'events')
    monkeypatch.setattr(robot_events, 'IMAGE_DIR', tmp_path / 'events' / 'images')
    monkeypatch.setattr(robot_events, 'LATEST_FILE', tmp_path / 'events' / 'latest.json')
    monkeypatch.setattr(robot_events, 'HISTORY_FILE', tmp_path / 'events' / 'events.jsonl')
    monkeypatch.setattr(robot_events, 'HAZARDS_FILE', tmp_path / 'events' / 'hazards.json')
    robot_events.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(robot_events, 'analyze_with_ai', lambda **kw: {
        'analysis': {'change': {'change_type': 'ADDED'},
                     'risk_assessment': {'risk_level': 'HIGH', 'hazard_present': True,
                                         'hazard_types': ['path_obstruction']},
                     'situation': {'summary': '통로 장애물'}, 'recommended_actions': ['제거']}
    })

    client = TestClient(app_main.app)
    workplace_id = client.post('/workplaces', json={'name': '지도 테스트'}).json()['id']
    map_payload = {'workplace_id': workplace_id, 'width': 20, 'height': 10,
                   'resolution': 0.1,
                   'origin': {'x': -1, 'y': -2, 'yaw': 0},
                   'data': [0] * 200}
    assert client.post('/workplaces/%d/map/start' % workplace_id).status_code == 200
    assert client.post('/workplaces/%d/map/scan-complete' % workplace_id).status_code == 409
    assert client.post('/api/telemetry/map', json=map_payload).status_code == 200
    assert client.get('/api/telemetry/map-meta', params={'workplace_id': workplace_id}).json()['width'] == 20
    assert client.post('/workplaces/%d/map/scan-complete' % workplace_id).status_code == 200
    assert client.put('/workplaces/%d/map/zones' % workplace_id, json=[
        {'id': 1, 'name': '통로', 'type': 'passage',
         'bounds': {'x1': 2, 'y1': 1, 'x2': 15, 'y2': 8}}
    ]).status_code == 200
    workplace = app_main.workplaces[workplace_id]
    # world (-0.5, -1.7) converts to grid (5,3)
    assert app_main.find_zone_for_position(workplace, -0.5, -1.7).id == 1
    assert app_main.find_zone_for_position(workplace, -100, -100) is None

    assert client.post('/api/telemetry/pose', json={'workplace_id': workplace_id,
        'x': -0.5, 'y': -1.7, 'yaw': 1.1}).status_code == 200
    with client.websocket_connect('/ws/map?workplace_id=%d' % workplace_id) as ws:
        data = ws.receive_json()
        assert (data['width'], data['height']) == (20,10)
        assert data['robot']['x'] == -0.5
        assert data['origin']['x'] == -1

    event = {'event_id': 'evt_test_001', 'workplace_id': workplace_id,
             'change': {'type': 'ADDED', 'x': -0.5, 'y': -1.7},
             'objects': [{'label': 'box', 'confidence': .9}]}
    res = client.post('/api/robot-events',
            data={'event_json':json.dumps(event)},
            files={'baseline_image': ('old.jpg', b'test-old', 'image/jpeg'),
                   'current_image': ('new.jpg', b'test-new', 'image/jpeg')})
    assert res.status_code == 200, res.text
    assert res.json()['risk']['is_danger'] is True
    hazards = client.get('/api/robot-events/hazards',params={'workplace_id':workplace_id}).json()['hazards']
    assert len(hazards) == 1 and hazards[0]['x'] == -0.5
    assert client.post('/api/robot-events/hazards/evt_test_001/ack').status_code == 200
    assert client.get('/api/robot-events/hazards',params={'workplace_id':workplace_id}).json()['hazards'] == []

    # Alternative risk mode from original requirement: YOLO + workplace policy
    workplace.map.status = 'ready'
    workplace.policies = {'1': app_main.ZonePolicy(noObjects=True)}
    monkeypatch.setattr(robot_events, 'RISK_MODE', 'yolo_policy')
    event['event_id'] = 'evt_yolo_002'
    res = client.post('/api/robot-events', data={'event_json':json.dumps(event)}, files={
        'baseline_image':('old.jpg', b'old','image/jpeg'),
        'current_image':('new.jpg', b'new','image/jpeg')})
    assert res.status_code == 200, res.text
    assert res.json()['ai_status'] == 'skipped_yolo_policy'
    assert res.json()['risk']['source'] == 'yolo_policy'
    assert res.json()['risk']['is_danger'] is True
    assert res.json()['risk']['zoneName'] == '통로'


def test_ai_failure_does_not_generate_hazard(tmp_path,monkeypatch):
    monkeypatch.setattr(robot_events,'DATA_DIR',tmp_path)
    monkeypatch.setattr(robot_events,'IMAGE_DIR',tmp_path/'images')
    monkeypatch.setattr(robot_events,'LATEST_FILE',tmp_path/'latest.json')
    monkeypatch.setattr(robot_events,'HISTORY_FILE',tmp_path/'events.jsonl')
    monkeypatch.setattr(robot_events,'HAZARDS_FILE',tmp_path/'hazards.json')
    robot_events.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    def failed(**kw): raise RuntimeError('AI unavailable')
    monkeypatch.setattr(robot_events,'analyze_with_ai',failed)
    client=TestClient(app_main.app)
    event={'event_id':'evt_offline','workplace_id':1,'change':{'type':'ADDED','x':0.2,'y':0.3}}
    response=client.post('/api/robot-events',data={'event_json':json.dumps(event)},files={
        'baseline_image':('old.jpg',b'abc','image/jpeg'),
        'current_image':('new.jpg',b'xyz','image/jpeg')})
    assert response.status_code==200
    assert response.json()['ai_status']=='error'
    assert response.json()['risk']['is_danger'] is False
    assert client.get('/api/robot-events/hazards').json()['hazards']==[]
