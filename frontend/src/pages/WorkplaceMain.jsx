import {
  useEffect,
  useState,
} from "react";

import ChangeDetectionPhoto
  from "./ChangeDetectionPhoto";

import PixelGridMap
  from "../PixelGridMap";


const API_URL =
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
    robotEvents,
    setRobotEvents,
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

  const [
    robotPosition,
    setRobotPosition,
  ] = useState({
    x: 1.0,
    y: 1.0,
  });


  const mapStatus =
    workplace.map?.status ||
    "empty";

  const mapObjects =
    workplace.map?.objects ||
    [];

  const mapZones =
    workplace.map?.zones ||
    [];


  const selectedMapObject =
    mapObjects.find(
      (object) =>
        object.id ===
        selectedMapObjectId
    ) || null;


  /*
   * ==========================================
   * Timer & 실제 로봇 위치 연동
   * ==========================================
   */

  useEffect(() => {
    if (
      patrolStatus !== "running" &&
      patrolStatus !== "returning"
    ) {
      return;
    }


    const timer =
      setInterval(
        () => {
          setElapsedTime(
            (prev) =>
              prev + 1
          );
        },
        1000
      );


    const moveInterval =
      setInterval(
        async () => {
          if (
            patrolStatus !==
            "running"
          ) {
            return;
          }

          try {
            const response =
              await fetch(
                `${API_URL}/workplaces/${workplace.id}/robot/position`
              );

            if (
              response.ok
            ) {
              const position =
                await response.json();

              setRobotPosition({
                x:
                  position.x,

                y:
                  position.y,
              });
            }
          } catch (error) {
            console.error(
              "위치 연동 실패:",
              error
            );
          }
        },
        500
      );


    return () => {
      clearInterval(
        timer
      );

      clearInterval(
        moveInterval
      );
    };
  }, [
    patrolStatus,
    workplace.id,
  ]);


  /*
   * ==========================================
   * 실제 순찰 상태 연동
   * ==========================================
   */

  useEffect(() => {
    if (
      !currentPatrolId ||
      (
        patrolStatus !== "running" &&
        patrolStatus !== "returning"
      )
    ) {
      return;
    }

    let active = true;

    const loadPatrolStatus =
      async () => {
        try {
          const response =
            await fetch(
              `${API_URL}/workplaces/${workplace.id}/patrols/${currentPatrolId}`
            );

          if (!response.ok) {
            return;
          }

          const patrol =
            await response.json();

          if (!active) {
            return;
          }

          if (
            patrol.status ===
            "completed"
          ) {
            setPatrolStatus(
              "completed"
            );

            if (
              typeof patrol.duration
              === "number"
            ) {
              setElapsedTime(
                patrol.duration
              );
            }

            setCurrentPatrolId(
              null
            );

            if (onSavePatrol) {
              onSavePatrol(
                patrol
              );
            }

            return;
          }

          if (
            patrol.status ===
            "returning"
          ) {
            setPatrolStatus(
              "returning"
            );
          }
        } catch (error) {
          console.error(
            "순찰 상태 연동 실패:",
            error
          );
        }
      };

    loadPatrolStatus();

    const interval =
      setInterval(
        loadPatrolStatus,
        1000
      );

    return () => {
      active = false;

      clearInterval(
        interval
      );
    };
  }, [
    currentPatrolId,
    patrolStatus,
    workplace.id,
    onSavePatrol,
  ]);


  /*
   * ==========================================
   * 실제 Robot Event 연동
   * ==========================================
   */

  useEffect(() => {
    let active = true;


    const loadRobotEvents =
      async () => {
        try {
          const response =
            await fetch(
              `${API_URL}/api/robot-events/hazards?workplace_id=${encodeURIComponent(
                workplace.id
              )}`,
              {
                cache:
                  "no-store",
              }
            );


          if (!response.ok) {
            throw new Error(
              `HTTP ${response.status}`
            );
          }


          const data =
            await response.json();


          if (!active) {
            return;
          }


          setRobotEvents(
            Array.isArray(
              data.hazards
            )
              ? data.hazards
              : []
          );
        } catch (error) {
          console.error(
            "Robot Event 로딩 실패:",
            error
          );
        }
      };


    loadRobotEvents();


    const timer =
      setInterval(
        loadRobotEvents,
        2000
      );


    return () => {
      active = false;

      clearInterval(
        timer
      );
    };
  }, [workplace.id]);


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
    if (!dateString) {
      return "-";
    }


    return new Date(
      dateString
    ).toLocaleString(
      "ko-KR"
    );
  };


  /*
   * ==========================================
   * Object
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
   * ==========================================
   * Semantic Zone
   * ==========================================
   */

  const getZoneTypeName = (
    type
  ) => {
    const found =
      ZONE_TYPES.find(
        (zoneType) =>
          zoneType.value ===
          type
      );


    return found
      ? found.label
      : "미지정";
  };


  const getZoneClass = (
    type
  ) => {
    return (
      `zone-type-${type}`
    );
  };


  /*
   * ==========================================
   * Zone Bounds → 화면 위치
   * ==========================================
   */

  const convertZoneBounds = (
    bounds
  ) => {
    if (!bounds) {
      return {};
    }


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
          (
            maxX -
            minX
          ) /
          MAP_SIZE
        ) * 100}%`,

      height:
        `${(
          (
            maxY -
            minY
          ) /
          MAP_SIZE
        ) * 100}%`,
    };
  };


  /*
   * ==========================================
   * Object Position → 화면 위치
   * ==========================================
   */

  const convertMapPosition = (
    position
  ) => {
    const x =
      position?.x ?? 0;

    const y =
      position?.y ?? 0;


    return {
      left:
        `${(
          x /
          MAP_SIZE
        ) * 100}%`,

      top:
        `${(
          1 -
          y /
            MAP_SIZE
        ) * 100}%`,
    };
  };


  /*
   * ==========================================
   * 좌표 → Semantic Zone
   * ==========================================
   */

  const findZoneByPosition = (
    position
  ) => {
    if (!position) {
      return null;
    }


    const x =
      position.x;

    const y =
      position.y;


    return (
      mapZones.find(
        (zone) => {
          const bounds =
            zone.bounds;


          if (!bounds) {
            return false;
          }


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


          return (
            x >= minX &&
            x <= maxX &&
            y >= minY &&
            y <= maxY
          );
        }
      ) || null
    );
  };


  /*
   * ==========================================
   * Popover Direction
   * ==========================================
   */

  const shouldOpenBelow = (
    object
  ) => {
    return (
      (
        object?.position?.y ??
        0
      ) >= 3
    );
  };


  /*
   * ==========================================
   * Mapping
   * ==========================================
   */

  const createMap =
    () => {
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
        setProcessing(
          true
        );

        setSelectedMapObjectId(
          null
        );


        const response =
          await fetch(
            `${API_URL}/workplaces/${workplace.id}/patrols/start`,
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
              "순찰 시작 실패"
          );
        }


        const patrol =
          await response.json();


        setCurrentPatrolId(
          patrol.id
        );

        setElapsedTime(
          0
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
        setProcessing(
          true
        );

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


        /*
         * 현재는 Mock 복귀
         *
         * 추후 Nav2가 실제 Home Pose에
         * 도착했다는 신호를 받으면
         * completePatrol() 호출
         */

        setTimeout(
          () => {
            completePatrol(
              currentPatrolId
            );
          },
          3000
        );
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

        setElapsedTime(
          0
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


  /*
   * ==========================================
   * 실제 변화 통계
   * ==========================================
   */

  const currentChangeCount =
    robotEvents.length;


  const currentRiskCount =
    robotEvents.filter(
      (event) =>
        event.risk_level ===
          "MEDIUM" ||
        event.risk_level ===
          "HIGH"
    ).length;


  return (
    <div className="screen">

      {/* ================================= */}
      {/* HEADER */}
      {/* ================================= */}

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

        {/* ================================= */}
        {/* MAP */}
        {/* ================================= */}

        <section className="map-section">

          <button
            className="policy-button"
            onClick={
              onOpenPolicy
            }
          >
            안전정책
          </button>


          {/* ============================= */}
          {/* EMPTY */}
          {/* ============================= */}

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


          {/* ============================= */}
          {/* CREATING */}
          {/* ============================= */}

          {mapStatus ===
            "creating" && (
            <div className="mapping-status">

              <div className="mapping-spinner" />

              <strong>
                지도를 제작하고
                있습니다.
              </strong>

              <p>
                현재는 하드웨어 없이
                Mock Mapping을 실행하고
                있습니다.
              </p>

              <span className="status-badge">
                Mapping...
              </span>

            </div>
          )}


          {/* ============================= */}
          {/* READY */}
          {/* ============================= */}

          {mapStatus ===
            "ready" && (
            <div
              className="map-container"
              style={{
                display:
                  "flex",

                justifyContent:
                  "center",

                alignItems:
                  "center",

                backgroundColor:
                  "#f5f5f5",
              }}
            >

              <div
                style={{
                  position:
                    "relative",

                  width:
                    "744px",

                  height:
                    "660px",
                }}
              >

                <PixelGridMap
                  workplaceId={
                    workplace.id
                  }
                />


                {/* 저장된 구역 표시 */}

                <div
                  style={{
                    position:
                      "absolute",

                    left:
                      0,

                    top:
                      0,

                    width:
                      "100%",

                    height:
                      "100%",

                    pointerEvents:
                      "none",
                  }}
                >

                  {mapZones.map(
                    (zone) => {
                      if (
                        !zone.bounds
                      ) {
                        return null;
                      }


                      const minX =
                        Math.min(
                          zone.bounds.x1,
                          zone.bounds.x2
                        );

                      const maxX =
                        Math.max(
                          zone.bounds.x1,
                          zone.bounds.x2
                        );

                      const minY =
                        Math.min(
                          zone.bounds.y1,
                          zone.bounds.y2
                        );

                      const maxY =
                        Math.max(
                          zone.bounds.y1,
                          zone.bounds.y2
                        );


                      return (
                        <div
                          key={
                            zone.id
                          }
                          style={{
                            position:
                              "absolute",

                            left:
                              `${(
                                minX /
                                124
                              ) * 100}%`,

                            top:
                              `${(
                                (
                                  110 -
                                  maxY
                                ) /
                                110
                              ) * 100}%`,

                            width:
                              `${(
                                (
                                  maxX -
                                  minX
                                ) /
                                124
                              ) * 100}%`,

                            height:
                              `${(
                                (
                                  maxY -
                                  minY
                                ) /
                                110
                              ) * 100}%`,

                            border:
                              "2px solid rgba(0, 150, 255, 0.9)",

                            backgroundColor:
                              "rgba(0, 150, 255, 0.15)",

                            boxSizing:
                              "border-box",

                            display:
                              "flex",

                            alignItems:
                              "center",

                            justifyContent:
                              "center",

                            color:
                              "#0066aa",

                            fontWeight:
                              "bold",

                            fontSize:
                              "14px",

                            pointerEvents:
                              "none",
                          }}
                        >
                          {zone.name}
                        </div>
                      );
                    }
                  )}

                </div>

              </div>

            </div>
          )}

        </section>


        {/* ================================= */}
        {/* DASHBOARD */}
        {/* ================================= */}

        <section className="dashboard-section">

          <h3>
            Dashboard
          </h3>


          {/* ============================= */}
          {/* RUNNING */}
          {/* ============================= */}

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
                    미확인 변화
                  </span>

                  <strong>
                    {currentChangeCount}
                  </strong>

                </div>


                <div>

                  <span>
                    확인 필요
                  </span>

                  <strong>
                    {currentRiskCount}
                  </strong>

                </div>

              </div>


              <ChangeDetectionPhoto
                workplaceId={
                  workplace.id
                }
              />

            </div>
          )}


          {/* ============================= */}
          {/* RETURNING */}
          {/* ============================= */}

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


          {/* ============================= */}
          {/* HISTORY */}
          {/* ============================= */}

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
                          patrol.changeCount ||
                          0
                        }
                        개 · 확인 필요{" "}
                        {
                          patrol.riskEventCount ||
                          0
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
            (
              !workplace.patrols ||
              workplace
                .patrols
                .length ===
                0
            ) && (
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


      {/* ================================= */}
      {/* BOTTOM */}
      {/* ================================= */}

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