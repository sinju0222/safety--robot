import React, { useEffect, useRef, useState } from "react";

const SCALE = 6;
const API_URL = "http://127.0.0.1:8000";
const WS_URL = "ws://127.0.0.1:8000";

// Coordinates from /map OccupancyGrid and /tf(map->base_link) are in meters.
function worldToPixel(item, map) {
    if (!map || !map.origin || !(Number(map.resolution) > 0)) return null;
    const { x: ox, y: oy, yaw = 0 } = map.origin;
    const x = Number(item?.x), y = Number(item?.y);
    if (![x, y, ox, oy, yaw].every(Number.isFinite)) return null;

    const dx = x - ox, dy = y - oy;
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const gx = (c * dx + s * dy) / map.resolution;
    const gy = (-s * dx + c * dy) / map.resolution;
    if (gx < 0 || gy < 0 || gx >= map.width || gy >= map.height) return null;
    return {
        left: (gx + 0.5) * SCALE,
        top: (map.height - gy - 0.5) * SCALE,
    };
}

// IMPORTANT: In WorkplaceMain.jsx use <PixelGridMap workplaceId={workplace.id} />
export default function PixelGridMap({ workplaceId = 1 }) {
    const canvasRef = useRef(null);
    const [mapData, setMapData] = useState(null);
    const [hazards, setHazards] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [ackLoading, setAckLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        let active = true;
        const ws = new WebSocket(
            `${WS_URL}/ws/map?workplace_id=${encodeURIComponent(workplaceId)}`
        );
        ws.onmessage = ({ data }) => {
            try {
                const next = JSON.parse(data);
                if (active && next.type === "map") setMapData(next);
            } catch (err) {
                console.error("Map WebSocket JSON:", err);
            }
        };
        ws.onerror = () => console.warn("Map WebSocket disconnected");
        return () => { active = false; ws.close(); };
    }, [workplaceId]);

    useEffect(() => {
        let active = true;
        async function refresh() {
            try {
                const r = await fetch(
                    `${API_URL}/api/robot-events/hazards?workplace_id=${encodeURIComponent(workplaceId)}`,
                    { cache: "no-store" }
                );
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                const data = await r.json();
                if (active) {
                    setHazards(Array.isArray(data.hazards) ? data.hazards : []);
                    setError("");
                }
            } catch (err) {
                if (active) setError("위험 경고 서버에 연결할 수 없습니다.");
            }
        }
        refresh();
        const timer = setInterval(refresh, 2000);
        return () => { active = false; clearInterval(timer); };
    }, [workplaceId]);

    useEffect(() => {
        if (!mapData || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        canvas.width = mapData.width * SCALE;
        canvas.height = mapData.height * SCALE;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let y = 0; y < mapData.height; y++) {
            for (let x = 0; x < mapData.width; x++) {
                const index = x + (mapData.height - y - 1) * mapData.width;
                const value = mapData.data[index];
                ctx.fillStyle = value >= 65 ? "#222222"
                    : value === 0 ? "#ffffff" : "#dddddd";
                ctx.fillRect(x * SCALE, y * SCALE, SCALE, SCALE);
            }
        }
        ctx.strokeStyle = "#e5e5e5";
        ctx.lineWidth = 0.3;
        for (let x = 0; x <= mapData.width; x++) {
            ctx.beginPath();
            ctx.moveTo(x * SCALE, 0);
            ctx.lineTo(x * SCALE, canvas.height);
            ctx.stroke();
        }
        for (let y = 0; y <= mapData.height; y++) {
            ctx.beginPath();
            ctx.moveTo(0, y * SCALE);
            ctx.lineTo(canvas.width, y * SCALE);
            ctx.stroke();
        }
    }, [mapData]);

    async function acknowledge() {
        if (!selectedId || ackLoading) return;
        setAckLoading(true);
        try {
            const r = await fetch(
                `${API_URL}/api/robot-events/hazards/${encodeURIComponent(selectedId)}/ack`,
                { method: "POST" }
            );
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            setHazards((current) => current.filter((h) => h.event_id !== selectedId));
            setSelectedId(null);
            setError("");
        } catch (err) {
            setError("확인 처리에 실패했습니다.");
        } finally {
            setAckLoading(false);
        }
    }

    const selected = hazards.find((h) => h.event_id === selectedId);
    const robotPos = mapData?.robot ? worldToPixel(mapData.robot, mapData) : null;
    const showMetadataWarning = mapData && (!mapData.origin || !mapData.resolution);

    return (
        <div style={{ width: "100%", height: "100%", minHeight: 240,
            position: "relative", display: "flex", flexDirection: "column",
            background: "#111" }}>
            <div style={{ flex: 1, minHeight: 0, overflow: "auto", display: "flex",
                justifyContent: "center", alignItems: "center" }}>
                {mapData ? (
                    <div style={{ position: "relative", flexShrink: 0,
                        width: mapData.width * SCALE, height: mapData.height * SCALE,
                        border: "2px solid #555" }}>
                        <canvas ref={canvasRef} style={{ display: "block",
                            imageRendering: "pixelated" }} />

                        {/* Blue pin = current TurtleBot location; stale poses are removed by server */}
                        {robotPos && (
                            <div title={`TurtleBot X:${mapData.robot.x.toFixed(2)} Y:${mapData.robot.y.toFixed(2)}`}
                                style={{ position: "absolute", left: robotPos.left, top: robotPos.top,
                                    transform: "translate(-50%, -50%)", width: 20, height: 20,
                                    borderRadius: "50%", background: "#2563eb",
                                    border: "3px solid white", boxShadow: "0 0 12px #3b82f6",
                                    zIndex: 4, pointerEvents: "none" }} />
                        )}

                        {/* Red pin = an unacknowledged safety-policy violation */}
                        {hazards.map((hazard) => {
                            const p = worldToPixel(hazard, mapData);
                            if (!p) return null;
                            return (
                                <button key={hazard.event_id} type="button"
                                    title={hazard.reason || "위험 탐지"}
                                    aria-label={`위험 확인: ${hazard.reason || "위험 탐지"}`}
                                    onClick={() => setSelectedId(hazard.event_id)}
                                    style={{ position: "absolute", left: p.left, top: p.top,
                                        transform: "translate(-50%, -50%)", width: 32, height: 32,
                                        borderRadius: "50%", background: "#dc2626", color: "#fff",
                                        border: "2px solid white", boxShadow: "0 0 13px #dc2626",
                                        fontSize: 23, fontWeight: "bold", cursor: "pointer", zIndex: 5 }}>
                                    !
                                </button>
                            );
                        })}
                    </div>
                ) : <span style={{ color: "#aaa" }}>지도 데이터를 기다리는 중...</span>}
            </div>

            <div style={{ color: "#ddd", fontSize: 12, padding: 6,
                display: "flex", gap: 14, justifyContent: "center" }}>
                <span>🔵 TurtleBot {robotPos ? "위치 수신 중" : "위치 대기"}</span>
                <span>❗ 미확인 위험 {hazards.length}건</span>
            </div>
            {showMetadataWarning && (
                <div style={{ color: "#fca5a5", padding: 6, fontSize: 12 }}>
                    지도에 실제 원점/해상도 정보가 없어 좌표 마커를 표시하지 않습니다.
                </div>
            )}
            {error && <div style={{ color: "#fca5a5", padding: 6 }}>{error}</div>}

            {selected && (
                <div style={{ position: "absolute", bottom: 45, right: 12, width: 285,
                    maxWidth: "90%", maxHeight: "78%", overflowY: "auto",
                    padding: 15, borderRadius: 8, background: "#fff", color: "#222",
                    boxShadow: "0 4px 18px #0008", zIndex: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <strong style={{ color: "#dc2626" }}>❗ 위험 탐지</strong>
                        <button type="button" onClick={() => setSelectedId(null)}>닫기</button>
                    </div>
                    <p>{selected.reason || "안전정책 위반"}</p>
                    <p>구역: {selected.zoneName || "미지정"}</p>
                    <p>물체: {selected.label || "알 수 없음"}</p>
                    <p>X {Number(selected.x).toFixed(2)}m / Y {Number(selected.y).toFixed(2)}m</p>
                    {selected.imageUrl && (
                        <img src={`${API_URL}${selected.imageUrl}`} alt="위험 탐지 사진"
                            style={{ width: "100%", borderRadius: 6 }} />
                    )}
                    <button type="button" disabled={ackLoading} onClick={acknowledge}
                        style={{ width: "100%", border: "none", borderRadius: 6,
                            padding: 10, color: "white", background: "#2563eb",
                            cursor: "pointer" }}>
                        {ackLoading ? "처리 중..." : "관리자 확인 완료"}
                    </button>
                </div>
            )}
        </div>
    );
}
