import {
  useEffect,
  useState,
} from "react";

const API_URL =
  "http://127.0.0.1:8000";

function WorkplaceMain({
  workplace,
  onBack,
  onOpenPolicy,
  onStartMapping,
  onSavePatrol,
  onOpenPatrol,
}) {
  const [
    patrolStatus,
    setPatrolStatus,
  ] = useState("idle");

  const [
    elapsedTime,
    setElapsedTime,
  ] = useState(0);

  const [
    currentEvents,
    setCurrentEvents,
  ] = useState([]);

  const [
    currentPatrolId,
    setCurrentPatrolId,
  ] = useState(null);

  const [
    processing,
    setProcessing,
  ] = useState(false);

  const [
    selectedMapObjectId,
    setSelectedMapObjectId,
  ] = useState(null);

  const mapStatus =
    workplace.map?.status ||
    "empty";

  const mapObjects =
    workplace.map?.objects ||
    [];

  const selectedMapObject =
    mapObjects.find(
      (object) =>
        object.id ===
        selectedMapObjectId
    );

  /*
   * ==========================================
   * Timer
   * ==========================================
   */

  useEffect(() => {
    if (
      patrolStatus !==
        "running" &&
      patrolStatus !==
        "returning"
    ) {
      return;
    }

    const timer =
      setInterval(() => {
        setElapsedTime(
          (prev) => prev + 1
        );
      }, 1000);

    return () =>
      clearInterval(timer);
  }, [patrolStatus]);

  /*
   * ==========================================
   * Formatting
   * ==========================================
   */

  const formatTime = (
    seconds
  ) => {
    const minutes =
      Math.floor(
        seconds / 60
      );

    const remainSeconds =
      seconds % 60;

    return `${String(
      minutes
    ).padStart(
      2,
      "0"
    )}:${String(
      remainSeconds
    ).padStart(
      2,
      "0"
    )}`;
  };

  const formatDate = (
    dateString
  ) => {
    return new Date(
      dateString
    ).toLocaleString(
      "ko-KR"
    );
  };

  /*
   * ==========================================
   * Map Object
   * ==========================================
   */

  const getObjectIcon = (
    type
  ) => {
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

  const getObjectTypeName = (
    type
  ) => {
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
   * Mock Map:
   * 6m × 6m
   */

  const convertMapPosition = (
    position
  ) => {
    const MAP_SIZE = 6;

    const x =
      position?.x ?? 0;

    const y =
      position?.y ?? 0;

    const left =
      Math.max(
        8,
        Math.min(
          92,
          (x / MAP_SIZE) *
            100
        )
      ) + "%";

    const top =
      Math.max(
        10,
        Math.min(
          90,
          100 -
            (y /
              MAP_SIZE) *
              100
        )
      ) + "%";

    return {
      left,
      top,
    };
  };

  /*
   * SLAM Y 값이 크면
   * 화면 상단에 위치하므로
   * 말풍선을 아래쪽으로 표시
   */

  const shouldOpenBelow = (
    object
  ) => {
    return (
      (object?.position?.y ??
        0) >= 3
    );
  };

  /*
   * ==========================================
   * Mapping
   * ==========================================
   */

  const createMap = () => {
    setSelectedMapObjectId(
      null
    );

    onStartMapping();
  };

  /*
   * ==========================================
   * Patrol Start
   * ==========================================
   */

  const startPatrol =
    async () => {
      if (
        mapStatus !== "ready"
      ) {
        alert(
          "먼저 작업장 지도를 제작해주세요."
        );

        return;
      }

      if (processing) {
        return;
      }

      try {
        setProcessing(true);

        setSelectedMapObjectId(
          null
        );

        const response =
          await fetch(
            `${API_URL}/workplaces/${workplace.id}/patrols/start`,
            {
              method: "POST",
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "순찰 시작 실패"
          );
        }

        const patrol =
          await response.json();

        setCurrentPatrolId(
          patrol.id
        );

        setElapsedTime(0);

        setCurrentEvents(
          []
        );

        setPatrolStatus(
          "running"
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "순찰을 시작할 수 없습니다."
        );
      } finally {
        setProcessing(
          false
        );
      }
    };

  /*
   * ==========================================
   * Demo Event
   * ==========================================
   */

  const createDemoEvent =
    async () => {
      if (
        patrolStatus !==
          "running" ||
        !currentPatrolId ||
        processing
      ) {
        return;
      }

      try {
        setProcessing(true);

        const eventNumber =
          currentEvents.length +
          1;

        let requestData;

        if (
          eventNumber % 2 ===
          1
        ) {
          requestData = {
            objectType:
              "water_bottle",

            objectName:
              "물병",

            zone: "A",

            x: 2.4,

            y: 3.1,

            distanceToCobot:
              null,
          };
        } else {
          requestData = {
            objectType:
              "box",

            objectName:
              "상자",

            zone: "A",

            x: 3.1,

            y: 2.6,

            distanceToCobot:
              0.72,
          };
        }

        const response =
          await fetch(
            `${API_URL}/workplaces/${workplace.id}/patrols/${currentPatrolId}/events`,
            {
              method:
                "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify(
                  requestData
                ),
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "변화 이벤트 처리 실패"
          );
        }

        const event =
          await response.json();

        setCurrentEvents(
          (prev) => [
            event,
            ...prev,
          ]
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "변화 이벤트 처리 중 오류가 발생했습니다."
        );
      } finally {
        setProcessing(
          false
        );
      }
    };

  /*
   * ==========================================
   * Return Home
   * ==========================================
   */

  const finishPatrol =
    async () => {
      if (
        patrolStatus !==
          "running" ||
        !currentPatrolId ||
        processing
      ) {
        return;
      }

      try {
        setProcessing(true);

        setSelectedMapObjectId(
          null
        );

        const response =
          await fetch(
            `${API_URL}/workplaces/${workplace.id}/patrols/${currentPatrolId}/return-home`,
            {
              method:
                "POST",
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "원점 복귀 요청 실패"
          );
        }

        setPatrolStatus(
          "returning"
        );

        setProcessing(
          false
        );

        setTimeout(() => {
          completePatrol(
            currentPatrolId
          );
        }, 3000);
      } catch (error) {
        console.error(
          error
        );

        setProcessing(
          false
        );

        alert(
          error.message ||
            "순찰 종료 중 오류가 발생했습니다."
        );
      }
    };

  /*
   * ==========================================
   * Patrol Complete
   * ==========================================
   */

  const completePatrol =
    async (
      patrolId
    ) => {
      try {
        setProcessing(
          true
        );

        const response =
          await fetch(
            `${API_URL}/workplaces/${workplace.id}/patrols/${patrolId}/complete`,
            {
              method:
                "POST",
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "순찰 완료 처리 실패"
          );
        }

        const completedPatrol =
          await response.json();

        onSavePatrol(
          completedPatrol
        );

        setPatrolStatus(
          "idle"
        );

        setElapsedTime(0);

        setCurrentEvents(
          []
        );

        setCurrentPatrolId(
          null
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "순찰 완료 처리 중 오류가 발생했습니다."
        );
      } finally {
        setProcessing(
          false
        );
      }
    };

  const currentRiskCount =
    currentEvents.filter(
      (event) =>
        event.riskLevel ===
        "HIGH"
    ).length;

  return (
    <div className="screen">

      {/* HEADER */}

      <header className="page-header">

        <button
          className="back-button"
          onClick={onBack}
        >
          ‹
        </button>

        <h2>
          {workplace.name}
        </h2>

      </header>

      <main className="main-dashboard">

        {/* ===================== */}
        {/* MAP */}
        {/* ===================== */}

        <section className="map-section">

          <button
            className="policy-button"
            onClick={
              onOpenPolicy
            }
          >
            안전정책
          </button>

          {/* EMPTY */}

          {mapStatus ===
            "empty" && (
            <div className="empty-map">

              <div className="map-icon">
                ⌖
              </div>

              <strong>
                아직 생성된 지도가
                없습니다.
              </strong>

              <p>
                로봇을 이용해
                작업장 지도를 먼저
                생성해주세요.
              </p>

              <button
                className="map-create-button"
                onClick={
                  createMap
                }
              >
                지도 제작하기
              </button>

            </div>
          )}

          {/* CREATING */}

          {mapStatus ===
            "creating" && (
            <div className="mapping-status">

              <div className="mapping-spinner" />

              <strong>
                지도를 제작하고
                있습니다.
              </strong>

              <p>
                현재는 하드웨어
                없이 Mock Mapping을
                실행하고 있습니다.
              </p>

              <span className="status-badge">
                Mapping...
              </span>

            </div>
          )}

          {/* READY */}

          {mapStatus ===
            "ready" && (
            <div className="map-container">

              <div
                className="map-placeholder"
                onClick={() =>
                  setSelectedMapObjectId(
                    null
                  )
                }
              >

                {/* ZONES */}

                <span className="zone zone-a">
                  A
                </span>

                <span className="zone zone-b">
                  B
                </span>

                <span className="zone zone-c">
                  C
                </span>

                {/* WALLS */}

                <div className="wall wall-1" />

                <div className="wall wall-2" />

                <div className="wall wall-3" />

                {/* ================= */}
                {/* BASELINE OBJECTS */}
                {/* ================= */}

                {mapObjects.map(
                  (object) => {
                    const position =
                      convertMapPosition(
                        object.position
                      );

                    const isSelected =
                      selectedMapObjectId ===
                      object.id;

                    const openBelow =
                      shouldOpenBelow(
                        object
                      );

                    return (
                      <div
                        key={
                          object.id
                        }
                        className="baseline-object-wrapper"
                        style={
                          position
                        }
                        onClick={(
                          event
                        ) =>
                          event.stopPropagation()
                        }
                      >

                        <button
                          type="button"
                          className={
                            isSelected
                              ? "baseline-object-marker selected"
                              : "baseline-object-marker"
                          }
                          onClick={() =>
                            setSelectedMapObjectId(
                              isSelected
                                ? null
                                : object.id
                            )
                          }
                        >

                          <span className="baseline-object-icon">
                            {getObjectIcon(
                              object.type
                            )}
                          </span>

                          <span className="baseline-object-name">
                            {
                              object.name
                            }
                          </span>

                        </button>

                        {/* POPOVER */}

                        {isSelected &&
                          selectedMapObject && (
                          <div
                            className={
                              openBelow
                                ? "baseline-object-popover baseline-popover-below"
                                : "baseline-object-popover baseline-popover-above"
                            }
                          >

                            <div className="baseline-popover-arrow" />

                            <div className="baseline-popover-header">

                              <strong>
                                {
                                  selectedMapObject.name
                                }
                              </strong>

                              <button
                                type="button"
                                onClick={() =>
                                  setSelectedMapObjectId(
                                    null
                                  )
                                }
                              >
                                ×
                              </button>

                            </div>

                            <div className="baseline-info-row">

                              <span>
                                종류
                              </span>

                              <strong>
                                {getObjectTypeName(
                                  selectedMapObject.type
                                )}
                              </strong>

                            </div>

                            <div className="baseline-info-row">

                              <span>
                                탐지
                              </span>

                              <strong>
                                {
                                  selectedMapObject.detectedClass
                                }
                              </strong>

                            </div>

                            <div className="baseline-info-row">

                              <span>
                                구역
                              </span>

                              <strong>
                                {
                                  selectedMapObject.zone
                                }
                              </strong>

                            </div>

                            <div className="baseline-info-row">

                              <span>
                                위치
                              </span>

                              <strong>
                                X{" "}
                                {
                                  selectedMapObject
                                    .position
                                    .x
                                }
                                {" / "}
                                Y{" "}
                                {
                                  selectedMapObject
                                    .position
                                    .y
                                }
                              </strong>

                            </div>

                            <div className="baseline-info-row">

                              <span>
                                상태
                              </span>

                              <strong>
                                기준 사물
                              </strong>

                            </div>

                          </div>
                        )}

                      </div>
                    );
                  }
                )}

                {/* ROBOT */}

                <span
                  className={
                    patrolStatus ===
                    "returning"
                      ? "robot-marker robot-returning"
                      : "robot-marker"
                  }
                >
                  ●
                </span>

                {/* HOME */}

                <span className="home-marker">
                  H
                </span>

                <span className="map-label">
                  작업장 지도
                </span>

                {patrolStatus ===
                  "returning" && (
                  <div className="map-return-status">
                    ↩ Home 복귀 중
                  </div>
                )}

              </div>

            </div>
          )}

        </section>

        {/* ===================== */}
        {/* DASHBOARD */}
        {/* ===================== */}

        <section className="dashboard-section">

          <h3>
            Dashboard
          </h3>

          {/* RUNNING */}

          {patrolStatus ===
            "running" && (
            <div className="patrol-running-card">

              <div className="patrol-running-header">

                <div className="live-indicator">

                  <span className="live-dot" />

                  순찰 중...

                </div>

                <span className="patrol-live">
                  LIVE
                </span>

              </div>

              <div className="patrol-time">
                {formatTime(
                  elapsedTime
                )}
              </div>

              <div className="patrol-stats">

                <div>

                  <span>
                    탐지된 변화
                  </span>

                  <strong>
                    {
                      currentEvents.length
                    }
                  </strong>

                </div>

                <div>

                  <span>
                    위험 이벤트
                  </span>

                  <strong>
                    {
                      currentRiskCount
                    }
                  </strong>

                </div>

              </div>

              {currentEvents.length >
                0 && (
                <div className="latest-event">

                  <span>
                    최근 탐지
                  </span>

                  <strong>
                    {
                      currentEvents[0]
                        .zone
                    }
                    구역 ·{" "}
                    {
                      currentEvents[0]
                        .objectName
                    }
                  </strong>

                  <div
                    className={
                      currentEvents[0]
                        .riskLevel ===
                      "HIGH"
                        ? "risk-high"
                        : "risk-normal"
                    }
                  >
                    {
                      currentEvents[0]
                        .riskLevel
                    }
                  </div>

                  {currentEvents[0]
                    .policyName && (
                    <div>
                      {
                        currentEvents[0]
                          .policyName
                      }
                    </div>
                  )}

                  {currentEvents[0]
                    .action ===
                    "COBOT_STOP" && (
                    <div className="stop-command">
                      협동로봇 작업 중단
                    </div>
                  )}

                </div>
              )}

              <button
                className="demo-event-button"
                onClick={
                  createDemoEvent
                }
                disabled={
                  processing
                }
              >
                {processing
                  ? "처리 중..."
                  : "+ 데모 변화 발생"}
              </button>

            </div>
          )}

          {/* RETURNING */}

          {patrolStatus ===
            "returning" && (
            <div className="returning-card">

              <div className="returning-icon">
                ↩
              </div>

              <strong>
                원점으로 복귀 중...
              </strong>

              <p>
                순찰을 종료하고
                로봇이 시작 위치로
                이동하고 있습니다.
              </p>

              <div className="returning-home">

                <span>
                  목적지
                </span>

                <strong>
                  Home Position
                </strong>

              </div>

              <div className="returning-time">

                전체 순찰시간

                <strong>
                  {formatTime(
                    elapsedTime
                  )}
                </strong>

              </div>

            </div>
          )}

          {/* HISTORY */}

          {workplace.patrols
            ?.length > 0 && (
            <div className="patrol-history">

              <h4>
                순찰 기록
              </h4>

              {workplace.patrols.map(
                (patrol) => (
                  <button
                    className="patrol-history-item"
                    key={
                      patrol.id
                    }
                    onClick={() =>
                      onOpenPatrol(
                        patrol.id
                      )
                    }
                  >

                    <div>

                      <strong>
                        {formatDate(
                          patrol.startedAt
                        )}
                      </strong>

                      <span>
                        탐지된 변화{" "}
                        {
                          patrol.changeCount
                        }
                        개 · 위험{" "}
                        {
                          patrol.riskEventCount
                        }
                        개
                      </span>

                    </div>

                    <div className="history-right">

                      <span>
                        {formatTime(
                          patrol.duration
                        )}
                      </span>

                      <b>
                        ›
                      </b>

                    </div>

                  </button>
                )
              )}

            </div>
          )}

          {patrolStatus ===
            "idle" &&
            (!workplace.patrols ||
              workplace
                .patrols
                .length ===
                0) && (
              <div className="empty-dashboard">

                <strong>
                  순찰 기록이 없습니다.
                </strong>

                <p>
                  순찰을 시작하면
                  결과가 여기에
                  표시됩니다.
                </p>

              </div>
            )}

        </section>

      </main>

      {/* ===================== */}
      {/* BOTTOM */}
      {/* ===================== */}

      <div className="bottom-area">

        {patrolStatus ===
          "running" && (
          <button
            className="finish-patrol-button"
            onClick={
              finishPatrol
            }
            disabled={
              processing
            }
          >
            ■ 순찰 종료 및 복귀
          </button>
        )}

        {patrolStatus ===
          "returning" && (
          <button
            className="returning-button"
            disabled
          >
            ↩ 원점 복귀 중...
          </button>
        )}

        {patrolStatus ===
          "idle" && (
          <button
            className="patrol-button"
            onClick={
              startPatrol
            }
            disabled={
              processing
            }
          >
            {processing
              ? "순찰 시작 중..."
              : "▶ 순찰 시작"}
          </button>
        )}

      </div>

    </div>
  );
}

export default WorkplaceMain;