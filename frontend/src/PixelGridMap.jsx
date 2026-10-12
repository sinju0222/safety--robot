import React, { useEffect, useRef, useState } from "react";

const SCALE = 6;
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws");

function worldToPixel(item, map) {
  if (!map?.origin || !(Number(map.resolution) > 0)) return null;
  const { x: ox, y: oy, yaw = 0 } = map.origin;
  const x = Number(item?.x), y = Number(item?.y);
  if (![x, y, ox, oy, yaw].every(Number.isFinite)) return null;
  const dx = x - ox, dy = y - oy, c = Math.cos(yaw), s = Math.sin(yaw);
  const gx = (c * dx + s * dy) / map.resolution;
  const gy = (-s * dx + c * dy) / map.resolution;
  if (gx < 0 || gy < 0 || gx >= map.width || gy >= map.height) return null;
  return { left: (gx + 0.5) * SCALE, top: (map.height - gy - 0.5) * SCALE };
}

function zoneStyle(zone, map) {
  if (!zone?.bounds || !map) return null;
  const { x1, x2, y1, y2 } = zone.bounds;
  const minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
  const minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
  return {
    position: "absolute", left: minX * SCALE,
    top: (map.height - maxY) * SCALE,
    width: (maxX - minX) * SCALE, height: (maxY - minY) * SCALE,
    border: "2px solid rgba(0,150,255,.9)",
    background: "rgba(0,150,255,.15)", boxSizing: "border-box",
    display: "flex", justifyContent: "center", alignItems: "center",
    color: "#0066aa", fontWeight: "bold", fontSize: 14,
    pointerEvents: "none", overflow: "hidden",
  };
}

// `editor` draws only the same occupancy grid, flush to the editing surface.
// `zones` are browser-saved grid cells (not meter coordinates).
export default function PixelGridMap({ workplaceId = 1, zones = [], editor = false }) {
  const canvasRef = useRef(null);
  const holderRef = useRef(null);
  const [dimensions, setDimensions] = useState({ w: 700, h: 450 });
  const [mapData, setMapData] = useState(null);
  const [waiting, setWaiting] = useState("지도 수신 대기 중...");
  const [hazards, setHazards] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [ackLoading, setAckLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setMapData(null);
    let active = true;
    let ws;
    let retry;
    const connect = () => {
      if (!active) return;
      ws = new WebSocket(`${WS_URL}/ws/map?workplace_id=${encodeURIComponent(workplaceId)}`);
      ws.onmessage = ({ data }) => {
        try {
          const payload = JSON.parse(data);
          if (!active) return;
          if (payload.type === "map") { setMapData(payload); setWaiting(""); }
          else if (payload.type === "waiting") { setWaiting(payload.message || "지도 수신 대기 중..."); setMapData(null); }
        } catch (e) { console.warn("Malformed map message", e); }
      };
      ws.onclose = () => { if (active) { setWaiting("지도 연결 재시도 중..."); retry = setTimeout(connect, 2500); } };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => { active = false; clearTimeout(retry); ws?.close(); };
  }, [workplaceId]);

  useEffect(() => {
    if (editor) return;
    let active = true;
    async function refresh() {
      try {
        const res = await fetch(`${API_URL}/api/robot-events/hazards?workplace_id=${encodeURIComponent(workplaceId)}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        if (active) { setHazards(Array.isArray(payload.hazards) ? payload.hazards : []); setError(""); }
      } catch (e) { if (active) setError("위험 경고 서버 연결 오류"); }
    }
    refresh(); const timer = setInterval(refresh, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [workplaceId, editor]);

  useEffect(() => {
    if (editor || !holderRef.current) return;
    const holder = holderRef.current;
    const measure = () => setDimensions({ w: holder.clientWidth || 700, h: holder.clientHeight || 450 });
    const observer = new ResizeObserver(measure);
    observer.observe(holder); measure();
    return () => observer.disconnect();
  }, [editor]);

  useEffect(() => {
    if (!mapData || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    const canvas = canvasRef.current;
    canvas.width = mapData.width * SCALE;
    canvas.height = mapData.height * SCALE;
    for (let row = 0; row < mapData.height; row++) {
      for (let col = 0; col < mapData.width; col++) {
        const val = mapData.data[col + (mapData.height - row - 1) * mapData.width];
        ctx.fillStyle = val >= 65 ? "#222222" : val === 0 ? "#ffffff" : "#dddddd";
        ctx.fillRect(col * SCALE, row * SCALE, SCALE, SCALE);
      }
    }
    ctx.strokeStyle = "#e5e5e5"; ctx.lineWidth = 0.3;
    for (let x = 0; x <= mapData.width; x++) {
      ctx.beginPath(); ctx.moveTo(x * SCALE, 0); ctx.lineTo(x * SCALE, canvas.height); ctx.stroke();
    }
    for (let y = 0; y <= mapData.height; y++) {
      ctx.beginPath(); ctx.moveTo(0, y * SCALE); ctx.lineTo(canvas.width, y * SCALE); ctx.stroke();
    }
  }, [mapData]);

  async function acknowledge() {
    if (!selectedId || ackLoading) return;
    setAckLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/robot-events/hazards/${encodeURIComponent(selectedId)}/ack`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHazards(prev => prev.filter(h => h.event_id !== selectedId));
      setSelectedId(null); setError("");
    } catch (e) { setError("관리자 확인 처리 실패"); }
    finally { setAckLoading(false); }
  }

  const rawW = mapData ? mapData.width * SCALE : 1;
  const rawH = mapData ? mapData.height * SCALE : 1;
  const scale = editor ? 1 : Math.max(0.01, Math.min(dimensions.w / rawW, dimensions.h / rawH));
  const robotPos = !editor && mapData?.robot ? worldToPixel(mapData.robot, mapData) : null;
  const selected = hazards.find(h => h.event_id === selectedId);
  const drawing = mapData && (
    <div style={{ position: "relative", width: rawW, height: rawH, transformOrigin: "0 0",
      transform: editor ? undefined : `scale(${scale})` }}>
      <canvas ref={canvasRef} style={{ display: "block", imageRendering: "pixelated", width: rawW, height: rawH }} />
      {!editor && zones.map(zone => {
        const style = zoneStyle(zone, mapData);
        return style && <div key={zone.id} style={style}>{zone.name}</div>;
      })}
      {!editor && robotPos && (
        <div title={`TurtleBot X:${mapData.robot.x.toFixed(2)} Y:${mapData.robot.y.toFixed(2)}`}
          style={{ position: "absolute", left: robotPos.left, top: robotPos.top,
            transform: "translate(-50%, -50%)", width: 20, height: 20, borderRadius: "50%",
            background: "#2563eb", border: "3px solid white", boxShadow: "0 0 12px #3b82f6",
            pointerEvents: "none", zIndex: 4 }} />
      )}
      {!editor && hazards.map(hazard => {
        const p = worldToPixel(hazard, mapData);
        if (!p) return null;
        return <button type="button" key={hazard.event_id}
          title={hazard.reason || "위험 발견"} onClick={() => setSelectedId(hazard.event_id)}
          style={{ position: "absolute", left: p.left, top: p.top, transform: "translate(-50%, -50%)",
            background: "#dc2626", border: "2px solid white", borderRadius: "50%",
            width: 32, height: 32, color: "white", fontWeight: "bold", fontSize: 22,
            boxShadow: "0 0 12px #dc2626", cursor: "pointer", zIndex: 5 }}>!</button>;
      })}
    </div>
  );

  if (editor) return <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
    {mapData ? <div style={{ width: "100%", height: "100%" }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", imageRendering: "pixelated" }} />
    </div> : <div style={{ padding: 10, color: "#666" }}>{waiting}</div>}
  </div>;

  return <div style={{ width: "100%", height: "100%", position: "relative",
      display: "flex", flexDirection: "column", background: "#111" }}>
    <div ref={holderRef} style={{ flex: 1, minHeight: 0, position: "relative", overflow: "hidden",
        display: "flex", alignItems: "center", justifyContent: "center" }}>
      {mapData ? <div style={{ width: rawW * scale, height: rawH * scale, flexShrink: 0,
        position: "relative", border: "1px solid #555", boxSizing: "content-box" }}>{drawing}</div>
        : <span style={{ color: "#ddd" }}>{waiting}</span>}
    </div>
    <div style={{ color: "#ddd", padding: 8, fontSize: 12, display: "flex", gap: 16,
      justifyContent: "center" }}>
      <span>🔵 TurtleBot {robotPos ? "위치 수신 중" : "위치 대기"}</span>
      <span>❗ 미확인 위험 {hazards.length}건</span>
    </div>
    {error && <div style={{ color: "#fca5a5", padding: 6 }}>{error}</div>}
    {selected && <div style={{ position: "absolute", bottom: 45, right: 12,
        background: "white", color: "#222", borderRadius: 8, padding: 14,
        width: 285, maxWidth: "90%", maxHeight: "78%", overflowY: "auto", zIndex: 9 }}>
      <strong style={{ color: "#dc2626" }}>❗ 위험 감지</strong>
      <button type="button" style={{ float: "right" }} onClick={() => setSelectedId(null)}>닫기</button>
      <p>{selected.reason || "위험 감지"}</p>
      <p>구역: {selected.zoneName || "미지정"}</p>
      <p>위치: X {Number(selected.x).toFixed(2)}m, Y {Number(selected.y).toFixed(2)}m</p>
      {selected.imageUrl && <img src={`${API_URL}${selected.imageUrl}`} alt="위험 사진" style={{ width: "100%" }} />}
      <button type="button" disabled={ackLoading} onClick={acknowledge}
        style={{ width: "100%", padding: 10, color: "white", background: "#2563eb", border: 0 }}>
        {ackLoading ? "처리 중..." : "관리자 확인 완료"}</button>
    </div>}
  </div>;
}
