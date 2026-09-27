import React, { useEffect, useRef, useState } from 'react';

const PixelGridMap = () => {
  const bgCanvasRef = useRef(null);    // 1. 멈춰있는 배경 맵 (최초 1회만 그림)
  const robotCanvasRef = useRef(null); // 2. 실시간 움직이는 로봇 (계속 갱신)
  const [mapInfo, setMapInfo] = useState({ width: 0, height: 0, resolution: 0.05 });

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/workplaces/1/robot');

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      // 🔴 [최초 1회 전송] 글로벌 맵 데이터가 들어왔을 때 (배경 캔버스에 그림)
      if (message.type === 'map') {
        const { width, height, resolution, data } = message;
        setMapInfo({ width, height, resolution });

        const bgCanvas = bgCanvasRef.current;
        const robotCanvas = robotCanvasRef.current;
        if (!bgCanvas || !robotCanvas) return;
        
        // 두 캔버스의 크기를 모두 맵 사이즈에 맞춤
        bgCanvas.width = width;
        bgCanvas.height = height;
        robotCanvas.width = width;
        robotCanvas.height = height;

        const ctx = bgCanvas.getContext('2d');
        const imageData = ctx.createImageData(width, height);

        for (let i = 0; i < data.length; i++) {
          const pixelIndex = i * 4;
          const val = data[i];

          if (val === 100) { // 장애물
            imageData.data.set([30, 30, 30, 255], pixelIndex);
          } else if (val === 0) { // 이동 가능
            imageData.data.set([245, 245, 245, 255], pixelIndex);
          } else { // 미지 영역
            imageData.data.set([180, 180, 180, 255], pixelIndex);
          }
        }
        ctx.putImageData(imageData, 0, 0); // 배경에 한 번 그리고 끝!
      }
      
      // 🔵 [차이점/실시간 갱신] 로봇 위치나 동적 데이터가 들어왔을 때 (투명 캔버스에 그림)
      if (message.type === 'position') {
        const { x, y } = message.position;
        const robotCanvas = robotCanvasRef.current;
        if (!robotCanvas || mapInfo.resolution === 0) return;

        const ctx = robotCanvas.getContext('2d');
        
        // 핵심: 이전 프레임의 로봇 잔상을 지우기 위해 투명 캔버스 전체를 싹 비움
        ctx.clearRect(0, 0, robotCanvas.width, robotCanvas.height);

        // 좌표 변환 (m -> pixel)
        const pixelX = x / mapInfo.resolution;
        const pixelY = robotCanvas.height - (y / mapInfo.resolution); 

        // 로봇 새 위치에 그리기
        ctx.beginPath();
        ctx.arc(pixelX, pixelY, 0.2 / mapInfo.resolution, 0, 2 * Math.PI);
        ctx.fillStyle = '#0066FF';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#003399';
        ctx.stroke();
      }
    };

    return () => ws.close();
  }, [mapInfo.resolution]); // 해상도 값이 세팅된 이후에 좌표 계산이 가능하도록 의존성 추가

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <h3>실시간 관제 맵 (최적화 렌더링)</h3>
      
      {/* 부모 div에 relative를 주고 자식 캔버스들을 absolute로 겹침 */}
      <div style={{ position: 'relative', width: '800px', height: '800px', border: '2px solid #ccc' }}>
        
        {/* 1. 바닥에 깔리는 글로벌 맵 (한 번만 그림) */}
        <canvas
          ref={bgCanvasRef}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            imageRendering: 'pixelated'
          }}
        />
        
        {/* 2. 그 위에 겹치는 투명한 로봇 레이어 (초당 수십 번 지웠다 그림) */}
        <canvas
          ref={robotCanvasRef}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            pointerEvents: 'none' // 마우스 클릭이 맵(아래 레이어)까지 닿도록 투과
          }}
        />

      </div>
    </div>
  );
};

export default PixelGridMap;

import asyncio
import json
import websockets
# (ROS2 관련 임포트는 생략)

async def run_websocket_bridge():
    uri = "ws://localhost:8000/ws/workplaces/1/robot"
    
    async with websockets.connect(uri) as websocket:
        print("✅ 웹소켓 연결 성공!")
        
        # 1. [최초 1회] 글로벌 맵 데이터 전송 (가상의 10x10 맵 배열)
        # 실제로는 ROS2의 /map 토픽 데이터를 콜백으로 받아와서 한 번만 쏩니다.
        mock_map_data = [0] * (200 * 200) 
        # (테스트용으로 중앙에 장애물 추가)
        for i in range(20000, 21000): mock_map_data[i] = 100 
        
        map_payload = {
            "type": "map",
            "width": 200,
            "height": 200,
            "resolution": 0.05,
            "data": mock_map_data
        }
        await websocket.send(json.dumps(map_payload))
        print("🗺️ 맵 데이터 1회 전송 완료")
        
        # 2. [무한 루프] 차이점(로봇 위치)만 고속으로 지속 전송
        # 실제로는 /odom 이나 /tf 데이터를 받아와서 쏩니다.
        x_pos = 2.0
        while True:
            position_payload = {
                "type": "position",
                "position": {
                    "x": x_pos,
                    "y": 3.5
                }
            }
            await websocket.send(json.dumps(position_payload))
            print(f"⚡ 위치 업데이트: X={x_pos}")
            
            x_pos += 0.05 # 로봇이 앞으로 이동하는 시뮬레이션
            await asyncio.sleep(0.1) # 초당 10번 전송 (10Hz)

if __name__ == "__main__":
    asyncio.run(run_websocket_bridge())
