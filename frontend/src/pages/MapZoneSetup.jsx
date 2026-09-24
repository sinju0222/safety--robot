import {
    useRef,
    useState,
  } from "react";
  
  const API_BASE =
    "http://127.0.0.1:8000";
  
  const MAP_SIZE = 6;
  
  const ZONE_TYPES = [
    {
      value: "work_area",
      label: "작업구역",
    },
    {
      value: "passage",
      label: "통로",
    },
    {
      value: "storage",
      label: "창고",
    },
    {
      value: "empty_area",
      label: "빈공간",
    },
    {
      value: "hazard_area",
      label: "위험구역",
    },
    {
      value: "restricted_area",
      label: "접근제한구역",
    },
  ];
  
  
  function MapZoneSetup({
    workplace,
    onComplete,
  }) {
    const mapRef =
      useRef(null);
  
    const [
      zones,
      setZones,
    ] = useState(
      workplace.map?.zones || []
    );
  
    const [
      drawing,
      setDrawing,
    ] = useState(false);
  
    const [
      startPoint,
      setStartPoint,
    ] = useState(null);
  
    const [
      currentRect,
      setCurrentRect,
    ] = useState(null);
  
    const [
      pendingBounds,
      setPendingBounds,
    ] = useState(null);
  
    const [
      zoneName,
      setZoneName,
    ] = useState("");
  
    const [
      zoneType,
      setZoneType,
    ] = useState("work_area");
  
    const [
      selectedZoneId,
      setSelectedZoneId,
    ] = useState(null);
  
    const [
      saving,
      setSaving,
    ] = useState(false);
  
  
    /*
     * ==========================================
     * 좌표 제한
     * ==========================================
     */
  
    const clamp = (
      value,
      min,
      max
    ) => {
      return Math.min(
        Math.max(
          value,
          min
        ),
        max
      );
    };
  
  
    /*
     * ==========================================
     * Pointer 위치
     * ==========================================
     */
  
    const getPointerPosition = (
      event
    ) => {
      if (!mapRef.current) {
        return null;
      }
  
      const rect =
        mapRef.current
          .getBoundingClientRect();
  
      return {
        x: clamp(
          event.clientX -
            rect.left,
          0,
          rect.width
        ),
  
        y: clamp(
          event.clientY -
            rect.top,
          0,
          rect.height
        ),
  
        width: rect.width,
  
        height: rect.height,
      };
    };
  
  
    /*
     * ==========================================
     * 화면 좌표 → SLAM Mock 좌표
     *
     * 화면:
     * 좌측 상단 = 0,0
     *
     * Map:
     * 좌측 하단 = 0,0
     * ==========================================
     */
  
    const screenToMap = (
      x,
      y,
      width,
      height
    ) => {
      const mapX =
        (x / width) *
        MAP_SIZE;
  
      const mapY =
        MAP_SIZE -
        (y / height) *
          MAP_SIZE;
  
      return {
        x: Number(
          mapX.toFixed(2)
        ),
  
        y: Number(
          mapY.toFixed(2)
        ),
      };
    };
  
  
    /*
     * ==========================================
     * Map 좌표 → CSS 위치
     * ==========================================
     */
  
    const boundsToStyle = (
      bounds
    ) => {
      const minX =
        Math.min(
          bounds.x1,
          bounds.x2
        );
  
      const maxX =
        Math.max(
          bounds.x1,
          bounds.x2
        );
  
      const minY =
        Math.min(
          bounds.y1,
          bounds.y2
        );
  
      const maxY =
        Math.max(
          bounds.y1,
          bounds.y2
        );
  
      return {
        left:
          `${(
            minX /
            MAP_SIZE
          ) * 100}%`,
  
        top:
          `${(
            1 -
            maxY /
              MAP_SIZE
          ) * 100}%`,
  
        width:
          `${(
            (maxX -
              minX) /
            MAP_SIZE
          ) * 100}%`,
  
        height:
          `${(
            (maxY -
              minY) /
            MAP_SIZE
          ) * 100}%`,
      };
    };
  
  
    /*
     * ==========================================
     * 구역 종류 표시
     * ==========================================
     */
  
    const getZoneTypeLabel = (
      type
    ) => {
      const found =
        ZONE_TYPES.find(
          (item) =>
            item.value ===
            type
        );
  
      return found
        ? found.label
        : type;
    };
  
  
    /*
     * ==========================================
     * 구역 종류별 CSS
     * ==========================================
     */
  
    const getZoneClass = (
      type
    ) => {
      return (
        `zone-type-${type}`
      );
    };
  
  
    /*
     * ==========================================
     * Drag Start
     * ==========================================
     */
  
    const handlePointerDown = (
      event
    ) => {
      /*
       * 이미 신규 구역 입력 중이면
       * 먼저 등록/취소하도록 함
       */
  
      if (pendingBounds) {
        return;
      }
  
      /*
       * 마우스 왼쪽 버튼만
       */
  
      if (
        event.pointerType ===
          "mouse" &&
        event.button !== 0
      ) {
        return;
      }
  
      const point =
        getPointerPosition(
          event
        );
  
      if (!point) {
        return;
      }
  
      event.currentTarget
        .setPointerCapture(
          event.pointerId
        );
  
      setSelectedZoneId(
        null
      );
  
      setDrawing(true);
  
      setStartPoint(
        point
      );
  
      setCurrentRect({
        left: point.x,
        top: point.y,
        width: 0,
        height: 0,
      });
    };
  
  
    /*
     * ==========================================
     * Drag Move
     * ==========================================
     */
  
    const handlePointerMove = (
      event
    ) => {
      if (
        !drawing ||
        !startPoint
      ) {
        return;
      }
  
      const point =
        getPointerPosition(
          event
        );
  
      if (!point) {
        return;
      }
  
      const left =
        Math.min(
          startPoint.x,
          point.x
        );
  
      const top =
        Math.min(
          startPoint.y,
          point.y
        );
  
      const width =
        Math.abs(
          point.x -
            startPoint.x
        );
  
      const height =
        Math.abs(
          point.y -
            startPoint.y
        );
  
      setCurrentRect({
        left,
        top,
        width,
        height,
      });
    };
  
  
    /*
     * ==========================================
     * Drag End
     * ==========================================
     */
  
    const handlePointerUp = (
      event
    ) => {
      if (
        !drawing ||
        !startPoint
      ) {
        return;
      }
  
      const point =
        getPointerPosition(
          event
        );
  
      setDrawing(false);
  
      try {
        event.currentTarget
          .releasePointerCapture(
            event.pointerId
          );
      } catch {
        // Pointer capture가 이미
        // 해제된 경우 무시
      }
  
      if (!point) {
        setStartPoint(null);
        setCurrentRect(null);
  
        return;
      }
  
      const pixelWidth =
        Math.abs(
          point.x -
            startPoint.x
        );
  
      const pixelHeight =
        Math.abs(
          point.y -
            startPoint.y
        );
  
      /*
       * 너무 작은 드래그는 무시
       */
  
      if (
        pixelWidth < 25 ||
        pixelHeight < 25
      ) {
        setStartPoint(null);
        setCurrentRect(null);
  
        return;
      }
  
      const startMap =
        screenToMap(
          startPoint.x,
          startPoint.y,
          startPoint.width,
          startPoint.height
        );
  
      const endMap =
        screenToMap(
          point.x,
          point.y,
          point.width,
          point.height
        );
  
      setPendingBounds({
        x1: Math.min(
          startMap.x,
          endMap.x
        ),
  
        y1: Math.min(
          startMap.y,
          endMap.y
        ),
  
        x2: Math.max(
          startMap.x,
          endMap.x
        ),
  
        y2: Math.max(
          startMap.y,
          endMap.y
        ),
      });
  
      setZoneName(
        `구역 ${zones.length + 1}`
      );
  
      setZoneType(
        "work_area"
      );
  
      setStartPoint(null);
      setCurrentRect(null);
    };
  
  
    /*
     * ==========================================
     * 신규 구역 등록
     * ==========================================
     */
  
    const addZone = () => {
      if (!pendingBounds) {
        return;
      }
  
      if (
        !zoneName.trim()
      ) {
        alert(
          "구역 이름을 입력해주세요."
        );
  
        return;
      }
  
      const nextId =
        zones.length === 0
          ? 1
          : Math.max(
              ...zones.map(
                (zone) =>
                  zone.id
              )
            ) + 1;
  
      const newZone = {
        id: nextId,
  
        name:
          zoneName.trim(),
  
        type:
          zoneType,
  
        bounds:
          pendingBounds,
      };
  
      setZones(
        (prev) => [
          ...prev,
          newZone,
        ]
      );
  
      setPendingBounds(
        null
      );
  
      setZoneName("");
  
      setZoneType(
        "work_area"
      );
  
      setSelectedZoneId(
        nextId
      );
    };
  
  
    /*
     * ==========================================
     * 신규 선택 취소
     * ==========================================
     */
  
    const cancelPendingZone =
      () => {
        setPendingBounds(
          null
        );
  
        setZoneName("");
  
        setZoneType(
          "work_area"
        );
      };
  
  
    /*
     * ==========================================
     * 구역 삭제
     * ==========================================
     */
  
    const deleteZone = (
      zoneId
    ) => {
      setZones(
        (prev) =>
          prev.filter(
            (zone) =>
              zone.id !==
              zoneId
          )
      );
  
      if (
        selectedZoneId ===
        zoneId
      ) {
        setSelectedZoneId(
          null
        );
      }
    };
  
  
    /*
     * ==========================================
     * Step 1 완료
     * ==========================================
     */
  
    const completeZoneSetup =
      async () => {
        if (saving) {
          return;
        }
  
        if (pendingBounds) {
          alert(
            "현재 선택한 구역을 먼저 등록하거나 취소해주세요."
          );
  
          return;
        }
  
        if (
          zones.length === 0
        ) {
          alert(
            "최소 1개의 구역을 설정해주세요."
          );
  
          return;
        }
  
        try {
          setSaving(true);
  
          /*
           * 1. 구역 저장
           */
  
          const saveResponse =
            await fetch(
              `${API_BASE}/workplaces/${workplace.id}/map/zones`,
              {
                method: "PUT",
  
                headers: {
                  "Content-Type":
                    "application/json",
                },
  
                body:
                  JSON.stringify(
                    zones
                  ),
              }
            );
  
          if (
            !saveResponse.ok
          ) {
            const error =
              await saveResponse.json();
  
            throw new Error(
              error.detail ||
                "구역 저장에 실패했습니다."
            );
          }
  
          /*
           * 2. Step 1 완료
           */
  
          const completeResponse =
            await fetch(
              `${API_BASE}/workplaces/${workplace.id}/map/zones/complete`,
              {
                method: "POST",
              }
            );
  
          if (
            !completeResponse.ok
          ) {
            const error =
              await completeResponse.json();
  
            throw new Error(
              error.detail ||
                "구역 설정 완료 처리에 실패했습니다."
            );
          }
  
          const result =
            await completeResponse.json();
  
          /*
           * App.jsx에서
           * Step 2로 전환
           */
  
          onComplete(
            result.map
          );
        } catch (error) {
          console.error(
            error
          );
  
          alert(
            error.message ||
              "구역 설정 중 오류가 발생했습니다."
          );
        } finally {
          setSaving(false);
        }
      };
  
  
    return (
      <div className="screen">
  
        {/* ================================= */}
        {/* HEADER */}
        {/* ================================= */}
  
        <header className="map-setup-header">
  
          <span className="map-setup-step">
            STEP 1 / 2
          </span>
  
          <h2>
            구역 설정
          </h2>
  
          <p>
            지도 위를 드래그하여
            구역을 선택한 뒤 공간의
            용도를 지정해주세요.
          </p>
  
        </header>
  
  
        {/* ================================= */}
        {/* CONTENT */}
        {/* ================================= */}
  
        <main className="zone-setup-page">
  
          {/* GUIDE */}
  
          <section className="zone-setup-guide">
  
            <strong>
              구역을 드래그하여 선택
            </strong>
  
            <p>
              작업구역, 통로, 창고,
              위험구역 등 작업장의
              공간 정보를 등록합니다.
            </p>
  
          </section>
  
  
          {/* ================================= */}
          {/* MAP */}
          {/* ================================= */}
  
          <section className="zone-map-section">
  
            <div
              ref={mapRef}
              className={
                pendingBounds
                  ? "zone-drawing-map selection-locked"
                  : "zone-drawing-map"
              }
              onPointerDown={
                handlePointerDown
              }
              onPointerMove={
                handlePointerMove
              }
              onPointerUp={
                handlePointerUp
              }
              onPointerCancel={() => {
                setDrawing(false);
                setStartPoint(null);
                setCurrentRect(null);
              }}
            >
  
              {/* GRID */}
  
              <div className="zone-map-grid" />
  
  
              {/* MOCK WALLS */}
  
              <div className="zone-map-wall zone-map-wall-1" />
  
              <div className="zone-map-wall zone-map-wall-2" />
  
              <div className="zone-map-wall zone-map-wall-3" />
  
  
              {/* HOME */}
  
              <span className="zone-map-home">
                H
              </span>
  
  
              {/* ================================= */}
              {/* SAVED ZONES */}
              {/* ================================= */}
  
              {zones.map(
                (zone) => {
                  const style =
                    boundsToStyle(
                      zone.bounds
                    );
  
                  const selected =
                    selectedZoneId ===
                    zone.id;
  
                  return (
                    <button
                      key={zone.id}
                      type="button"
                      className={
                        `saved-map-zone ${getZoneClass(
                          zone.type
                        )} ${
                          selected
                            ? "selected"
                            : ""
                        }`
                      }
                      style={style}
                      onPointerDown={(
                        event
                      ) => {
                        event.stopPropagation();
                      }}
                      onClick={(
                        event
                      ) => {
                        event.stopPropagation();
  
                        setSelectedZoneId(
                          selected
                            ? null
                            : zone.id
                        );
                      }}
                    >
  
                      <span className="saved-zone-name">
                        {zone.name}
                      </span>
  
                      <span className="saved-zone-type">
                        {getZoneTypeLabel(
                          zone.type
                        )}
                      </span>
  
                    </button>
                  );
                }
              )}
  
  
              {/* ================================= */}
              {/* CURRENT DRAG */}
              {/* ================================= */}
  
              {drawing &&
                currentRect && (
                <div
                  className="current-zone-selection"
                  style={{
                    left:
                      currentRect.left,
  
                    top:
                      currentRect.top,
  
                    width:
                      currentRect.width,
  
                    height:
                      currentRect.height,
                  }}
                />
              )}
  
  
              {/* ================================= */}
              {/* PENDING ZONE */}
              {/* ================================= */}
  
              {pendingBounds && (
                <div
                  className="pending-map-zone"
                  style={
                    boundsToStyle(
                      pendingBounds
                    )
                  }
                >
                  새 구역
                </div>
              )}
  
  
              <span className="zone-map-label">
                작업장 지도 · 6m × 6m
              </span>
  
            </div>
  
          </section>
  
  
          {/* ================================= */}
          {/* NEW ZONE FORM */}
          {/* ================================= */}
  
          {pendingBounds && (
            <section className="new-zone-panel">
  
              <div className="new-zone-panel-header">
  
                <div>
  
                  <span>
                    선택된 영역
                  </span>
  
                  <strong>
                    새 구역 설정
                  </strong>
  
                </div>
  
                <button
                  type="button"
                  onClick={
                    cancelPendingZone
                  }
                >
                  ×
                </button>
  
              </div>
  
  
              <label className="zone-form-field">
  
                <span>
                  구역 이름
                </span>
  
                <input
                  type="text"
                  value={zoneName}
                  onChange={(
                    event
                  ) =>
                    setZoneName(
                      event.target
                        .value
                    )
                  }
                  placeholder="예: 조립 작업구역"
                />
  
              </label>
  
  
              <label className="zone-form-field">
  
                <span>
                  공간 유형
                </span>
  
                <select
                  value={zoneType}
                  onChange={(
                    event
                  ) =>
                    setZoneType(
                      event.target
                        .value
                    )
                  }
                >
  
                  {ZONE_TYPES.map(
                    (type) => (
                      <option
                        key={
                          type.value
                        }
                        value={
                          type.value
                        }
                      >
                        {type.label}
                      </option>
                    )
                  )}
  
                </select>
  
              </label>
  
  
              <div className="zone-coordinate-info">
  
                <span>
                  지도 좌표
                </span>
  
                <strong>
                  (
                  {
                    pendingBounds.x1
                  }
                  ,{" "}
                  {
                    pendingBounds.y1
                  }
                  )
                  {" → "}
                  (
                  {
                    pendingBounds.x2
                  }
                  ,{" "}
                  {
                    pendingBounds.y2
                  }
                  )
                </strong>
  
              </div>
  
  
              <div className="new-zone-actions">
  
                <button
                  type="button"
                  className="zone-cancel-button"
                  onClick={
                    cancelPendingZone
                  }
                >
                  취소
                </button>
  
                <button
                  type="button"
                  className="zone-register-button"
                  onClick={
                    addZone
                  }
                >
                  구역 등록
                </button>
  
              </div>
  
            </section>
          )}
  
  
          {/* ================================= */}
          {/* REGISTERED ZONES */}
          {/* ================================= */}
  
          <section className="registered-zones">
  
            <div className="registered-zones-header">
  
              <strong>
                설정된 구역
              </strong>
  
              <span>
                {zones.length}개
              </span>
  
            </div>
  
  
            {zones.length === 0 ? (
              <div className="no-zones">
  
                <strong>
                  아직 설정된 구역이 없습니다.
                </strong>
  
                <p>
                  위 지도에서 원하는
                  영역을 드래그해주세요.
                </p>
  
              </div>
            ) : (
              <div className="zone-list">
  
                {zones.map(
                  (zone) => (
                    <div
                      key={
                        zone.id
                      }
                      className={
                        selectedZoneId ===
                        zone.id
                          ? "zone-list-item selected"
                          : "zone-list-item"
                      }
                    >
  
                      <button
                        type="button"
                        className="zone-list-main"
                        onClick={() =>
                          setSelectedZoneId(
                            zone.id
                          )
                        }
                      >
  
                        <span
                          className={
                            `zone-type-dot ${getZoneClass(
                              zone.type
                            )}`
                          }
                        />
  
                        <div>
  
                          <strong>
                            {
                              zone.name
                            }
                          </strong>
  
                          <span>
                            {getZoneTypeLabel(
                              zone.type
                            )}
                          </span>
  
                        </div>
  
                      </button>
  
  
                      <button
                        type="button"
                        className="zone-delete-button"
                        onClick={() =>
                          deleteZone(
                            zone.id
                          )
                        }
                      >
                        삭제
                      </button>
  
                    </div>
                  )
                )}
  
              </div>
            )}
  
          </section>
  
        </main>
  
  
        {/* ================================= */}
        {/* BOTTOM */}
        {/* ================================= */}
  
        <div className="zone-setup-bottom">
  
          <button
            type="button"
            className="zone-next-button"
            onClick={
              completeZoneSetup
            }
            disabled={
              saving ||
              zones.length === 0
            }
          >
            {saving
              ? "저장 중..."
              : "다음: 사물 설정 →"}
          </button>
  
        </div>
  
      </div>
    );
  }
  
  export default MapZoneSetup;