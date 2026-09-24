import { useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function MapObjectSetup({
  workplace,
  onComplete,
}) {
  const [objects, setObjects] = useState(
    workplace.map?.objects || []
  );

  const [selectedId, setSelectedId] =
    useState(null);

  const [saving, setSaving] =
    useState(false);

  const selectedObject = objects.find(
    (object) => object.id === selectedId
  );

  /*
   * ==========================================
   * 객체 정보 수정
   * ==========================================
   */

  const updateObject = (
    field,
    value
  ) => {
    setObjects((prev) =>
      prev.map((object) =>
        object.id === selectedId
          ? {
              ...object,
              [field]: value,
            }
          : object
      )
    );
  };

  /*
   * ==========================================
   * 객체 종류별 아이콘
   * ==========================================
   */

  const getMarkerIcon = (type) => {
    switch (type) {
      case "cobot":
        return "🤖";

      case "storage":
        return "📦";

      case "equipment":
        return "⚙️";

      default:
        return "●";
    }
  };

  /*
   * ==========================================
   * 객체 종류 이름
   * ==========================================
   */

  const getTypeName = (type) => {
    switch (type) {
      case "cobot":
        return "협동로봇";

      case "storage":
        return "적재물";

      case "equipment":
        return "고정설비 / 작업대";

      default:
        return "기타";
    }
  };

  /*
   * ==========================================
   * SLAM 좌표 → 화면 좌표
   *
   * 현재 Mock 공간:
   * 6m × 6m
   *
   * 추후 실제 SLAM Map Metadata 기반으로 교체
   * ==========================================
   */

  const convertPosition = (
    position
  ) => {
    const MAP_SIZE = 6;

    const x = position?.x ?? 0;
    const y = position?.y ?? 0;

    const left =
      Math.max(
        8,
        Math.min(
          92,
          (x / MAP_SIZE) * 100
        )
      ) + "%";

    const top =
      Math.max(
        10,
        Math.min(
          90,
          100 -
            (y / MAP_SIZE) * 100
        )
      ) + "%";

    return {
      left,
      top,
    };
  };

  /*
   * ==========================================
   * 말풍선 방향
   *
   * SLAM Y 값이 크면 화면 상단에 위치
   * → 아래 방향으로 말풍선
   *
   * 화면 아래쪽이면
   * → 위 방향으로 말풍선
   * ==========================================
   */

  const shouldOpenBelow = (
    object
  ) => {
    return (
      (object?.position?.y ?? 0) >= 3
    );
  };

  /*
   * ==========================================
   * 지도 적용
   * ==========================================
   */

  const applyMap = async () => {
    if (saving) {
      return;
    }

    /*
     * 이름이 비어 있는 객체 검사
     */

    const invalidObject =
      objects.find(
        (object) =>
          !object.name ||
          object.name.trim() === ""
      );

    if (invalidObject) {
      alert(
        "모든 사물의 이름을 입력해주세요."
      );

      return;
    }

    try {
      setSaving(true);

      /*
       * 1.
       * 관리자 수정 객체 저장
       */

      const objectResponse =
        await fetch(
          `${API_BASE}/workplaces/${workplace.id}/map/objects`,
          {
            method: "PUT",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify(
              objects
            ),
          }
        );

      if (!objectResponse.ok) {
        const error =
          await objectResponse.json();

        throw new Error(
          error.detail ||
            "객체 저장에 실패했습니다."
        );
      }

      /*
       * 2.
       * 지도 최종 완료
       */

      const completeResponse =
        await fetch(
          `${API_BASE}/workplaces/${workplace.id}/map/complete`,
          {
            method: "POST",
          }
        );

      if (!completeResponse.ok) {
        const error =
          await completeResponse.json();

        throw new Error(
          error.detail ||
            "지도 적용에 실패했습니다."
        );
      }

      const result =
        await completeResponse.json();

      /*
       * App.jsx로 최종 Map 전달
       */

      onComplete(
        result.map
      );
    } catch (error) {
      console.error(error);

      alert(
        error.message ||
          "지도 적용 중 오류가 발생했습니다."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="screen">

      {/* ========================= */}
      {/* HEADER */}
      {/* ========================= */}

      <header className="map-setup-header">

        <span className="map-setup-step">
          초기 환경 설정
        </span>

        <h2>
          탐지된 사물 확인
        </h2>

        <p>
          지도에서 사물을 선택하고
          이름과 종류를 설정해주세요.
        </p>

      </header>

      {/* ========================= */}
      {/* CONTENT */}
      {/* ========================= */}

      <main className="map-object-setup-page">

        {/* ===================== */}
        {/* MAP */}
        {/* ===================== */}

        <section className="setup-map-section">

          <div
            className="setup-object-map"
            onClick={() =>
              setSelectedId(null)
            }
          >

            {/* Grid */}

            <div className="setup-grid" />

            {/* Zone */}

            <span className="setup-zone setup-zone-a">
              A
            </span>

            <span className="setup-zone setup-zone-b">
              B
            </span>

            <span className="setup-zone setup-zone-c">
              C
            </span>

            {/* Mock Walls */}

            <div className="setup-wall setup-wall-1" />

            <div className="setup-wall setup-wall-2" />

            <div className="setup-wall setup-wall-3" />

            {/* Home */}

            <span className="setup-home-marker">
              H
            </span>

            {/* ================= */}
            {/* Objects */}
            {/* ================= */}

            {objects.map(
              (object) => {
                const markerPosition =
                  convertPosition(
                    object.position
                  );

                const isSelected =
                  selectedId ===
                  object.id;

                const openBelow =
                  shouldOpenBelow(
                    object
                  );

                return (
                  <div
                    key={object.id}
                    className="setup-object-wrapper"
                    style={
                      markerPosition
                    }
                    onClick={(
                      event
                    ) =>
                      event.stopPropagation()
                    }
                  >

                    {/* Marker */}

                    <button
                      type="button"
                      className={
                        isSelected
                          ? "setup-object-marker selected"
                          : "setup-object-marker"
                      }
                      onClick={() =>
                        setSelectedId(
                          isSelected
                            ? null
                            : object.id
                        )
                      }
                    >

                      <span className="setup-object-icon">
                        {getMarkerIcon(
                          object.type
                        )}
                      </span>

                      <span className="setup-object-name">
                        {object.name}
                      </span>

                    </button>

                    {/* ================= */}
                    {/* Popover */}
                    {/* ================= */}

                    {isSelected &&
                      selectedObject && (
                      <div
                        className={
                          openBelow
                            ? "setup-object-popover setup-popover-below"
                            : "setup-object-popover setup-popover-above"
                        }
                      >

                        <div className="setup-popover-arrow" />

                        <div className="setup-popover-header">

                          <strong>
                            사물 정보 설정
                          </strong>

                          <button
                            type="button"
                            onClick={() =>
                              setSelectedId(
                                null
                              )
                            }
                          >
                            ×
                          </button>

                        </div>

                        {/* 이름 */}

                        <label className="setup-field">

                          <span>
                            이름
                          </span>

                          <input
                            type="text"
                            value={
                              selectedObject.name
                            }
                            onChange={(
                              event
                            ) =>
                              updateObject(
                                "name",
                                event
                                  .target
                                  .value
                              )
                            }
                            placeholder="사물 이름"
                          />

                        </label>

                        {/* 종류 */}

                        <label className="setup-field">

                          <span>
                            종류
                          </span>

                          <select
                            value={
                              selectedObject.type
                            }
                            onChange={(
                              event
                            ) =>
                              updateObject(
                                "type",
                                event
                                  .target
                                  .value
                              )
                            }
                          >

                            <option value="cobot">
                              협동로봇
                            </option>

                            <option value="storage">
                              적재물
                            </option>

                            <option value="equipment">
                              고정설비 / 작업대
                            </option>

                            <option value="other">
                              기타
                            </option>

                          </select>

                        </label>

                        {/* 탐지 */}

                        <div className="setup-info-row">

                          <span>
                            탐지
                          </span>

                          <strong>
                            {
                              selectedObject.detectedClass
                            }
                          </strong>

                        </div>

                        {/* 구역 */}

                        <div className="setup-info-row">

                          <span>
                            구역
                          </span>

                          <strong>
                            {
                              selectedObject.zone
                            }
                          </strong>

                        </div>

                        {/* 위치 */}

                        <div className="setup-info-row">

                          <span>
                            위치
                          </span>

                          <strong>
                            X{" "}
                            {
                              selectedObject
                                .position.x
                            }
                            {" / "}
                            Y{" "}
                            {
                              selectedObject
                                .position.y
                            }
                          </strong>

                        </div>

                        {/* 현재 종류 */}

                        <div className="setup-info-row">

                          <span>
                            설정
                          </span>

                          <strong>
                            {getTypeName(
                              selectedObject.type
                            )}
                          </strong>

                        </div>

                        <button
                          type="button"
                          className="setup-confirm-button"
                          onClick={() =>
                            setSelectedId(
                              null
                            )
                          }
                        >
                          확인
                        </button>

                      </div>
                    )}

                  </div>
                );
              }
            )}

            <span className="setup-map-label">
              작업장 지도
            </span>

          </div>

        </section>

        {/* ===================== */}
        {/* SUMMARY */}
        {/* ===================== */}

        <section className="setup-summary">

          <div className="setup-summary-top">

            <strong>
              탐지된 사물
            </strong>

            <span>
              {objects.length}개
            </span>

          </div>

          <p>
            각 마커를 눌러 실제 작업장에서
            사용하는 이름과 종류를
            지정해주세요.
          </p>

        </section>

      </main>

      {/* ========================= */}
      {/* BOTTOM */}
      {/* ========================= */}

      <div className="map-setup-bottom">

        <button
          type="button"
          className="map-setup-apply-button"
          onClick={applyMap}
          disabled={saving}
        >
          {saving
            ? "적용 중..."
            : "지도에 적용"}
        </button>

      </div>

    </div>
  );
}

export default MapObjectSetup;