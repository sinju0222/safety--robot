const API_URL =
  "http://127.0.0.1:8000";


function getRiskInfo(
  riskLevel
) {
  switch (riskLevel) {
    case "HIGH":
      return {
        text: "HIGH",
        color: "#b91c1c",
        background: "#fee2e2",
      };

    case "MEDIUM":
      return {
        text: "MEDIUM",
        color: "#c2410c",
        background: "#ffedd5",
      };

    case "LOW":
      return {
        text: "LOW",
        color: "#a16207",
        background: "#fef9c3",
      };

    case "NORMAL":
      return {
        text: "NORMAL",
        color: "#15803d",
        background: "#dcfce7",
      };

    default:
      return {
        text: "UNKNOWN",
        color: "#475569",
        background: "#e2e8f0",
      };
  }
}


function getChangeLabel(
  changeType
) {
  const labels = {
    ADDED: "물체 추가",
    REMOVED: "물체 제거",
    MOVED: "물체 이동",
    STATE_CHANGED: "상태 변화",
    MIXED: "복합 변화",
    NO_CHANGE: "변화 없음",
  };

  return (
    labels[changeType] ||
    changeType ||
    "-"
  );
}


function getHazardLabel(
  hazardType
) {
  const labels = {
    trip_hazard:
      "걸림 위험",

    object_on_path:
      "통행 경로 물체",

    path_obstruction:
      "통행 방해",

    sharp_tool_hazard:
      "날카로운 공구 위험",

    rolling_object_hazard:
      "구름 물체 위험",

    unstable_object:
      "불안정한 물체",

    falling_object_hazard:
      "낙하 위험",
  };

  return (
    labels[hazardType] ||
    hazardType
  );
}


function PatrolDetail({
  workplace,
  patrolId,
  onBack,
}) {
  /*
   * ==========================================
   * 선택된 Patrol
   * ==========================================
   */

  const patrol =
    workplace?.patrols?.find(
      (item) =>
        item.id === patrolId
    );


  /*
   * ==========================================
   * Formatting
   * ==========================================
   */

  const formatTime = (
    seconds
  ) => {
    const safeSeconds =
      Number(seconds) || 0;

    const minutes =
      Math.floor(
        safeSeconds / 60
      );

    const remainSeconds =
      safeSeconds % 60;

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
    date
  ) => {
    if (!date) {
      return "-";
    }

    return new Date(
      date
    ).toLocaleString(
      "ko-KR"
    );
  };


  /*
   * ==========================================
   * Patrol 없음
   * ==========================================
   */

  if (!patrol) {
    return (
      <div className="screen">

        <header className="page-header">

          <button
            className="back-button"
            onClick={onBack}
          >
            ‹
          </button>

          <h2>
            순찰 결과
          </h2>

        </header>


        <main className="patrol-detail-content">

          <div className="empty-dashboard">

            <strong>
              순찰 결과를 찾을 수 없습니다.
            </strong>

            <p>
              순찰 기록을 다시 선택해주세요.
            </p>

          </div>

        </main>

      </div>
    );
  }


  const events =
    patrol.events || [];


  const riskEventCount =
    events.filter(
      (event) => {
        const level =
          event.risk_level ||
          event.riskLevel;

        return (
          level === "MEDIUM" ||
          level === "HIGH"
        );
      }
    ).length;


  return (
    <div className="screen">

      {/* ========================= */}
      {/* HEADER */}
      {/* ========================= */}

      <header className="page-header">

        <button
          className="back-button"
          onClick={onBack}
        >
          ‹
        </button>

        <h2>
          순찰 결과
        </h2>

      </header>


      <main className="patrol-detail-content">

        {/* ========================= */}
        {/* PATROL SUMMARY */}
        {/* ========================= */}

        <section className="patrol-summary-card">

          <span>
            {formatDate(
              patrol.startedAt
            )}
          </span>

          <h1>
            순찰 완료
          </h1>

          <div className="detail-summary-grid">

            <div>

              <span>
                순찰시간
              </span>

              <strong>
                {formatTime(
                  patrol.duration
                )}
              </strong>

            </div>


            <div>

              <span>
                탐지된 변화
              </span>

              <strong>
                {events.length ||
                  patrol.changeCount ||
                  0}
              </strong>

            </div>


            <div>

              <span>
                확인 필요
              </span>

              <strong>
                {events.length > 0
                  ? riskEventCount
                  : patrol.riskEventCount ||
                    0}
              </strong>

            </div>

          </div>

        </section>


        {/* ========================= */}
        {/* EVENT TITLE */}
        {/* ========================= */}

        <h3 className="event-title">
          AI 변화 분석 결과
        </h3>


        {/* ========================= */}
        {/* NO EVENT */}
        {/* ========================= */}

        {events.length === 0 && (
          <div className="empty-dashboard">

            <strong>
              탐지된 변화가 없습니다.
            </strong>

            <p>
              이번 순찰에서는
              새로운 환경 변화가
              탐지되지 않았습니다.
            </p>

          </div>
        )}


        {/* ========================= */}
        {/* EVENTS */}
        {/* ========================= */}

        {events.map(
          (event, index) => {
            const riskLevel =
              event.risk_level ||
              event.riskLevel ||
              "NORMAL";


            const risk =
              getRiskInfo(
                riskLevel
              );


            const changeType =
              event.change_type ||
              event.changeType ||
              event.analysis
                ?.change
                ?.change_type ||
              "-";


            const situation =
              event.situation ||
              event.reason ||
              event.analysis
                ?.situation
                ?.summary ||
              "상황 분석 결과가 없습니다.";


            const hazardTypes =
              event.hazard_types ||
              event.analysis
                ?.risk_assessment
                ?.hazard_types ||
              [];


            const actions =
              event.recommended_actions ||
              event.analysis
                ?.recommended_actions ||
              [];


            const baselineImageUrl =
              event.baselineImageUrl ||
              null;


            const currentImageUrl =
              event.currentImageUrl ||
              event.imageUrl ||
              event.image ||
              null;


            const x =
              event.x ??
              event.position?.x ??
              "-";


            const y =
              event.y ??
              event.position?.y ??
              "-";


            return (
              <section
                className="event-card"
                key={
                  event.event_id ||
                  event.id ||
                  index
                }
              >

                {/* ================= */}
                {/* EVENT HEADER */}
                {/* ================= */}

                <div className="event-card-header">

                  <span>
                    변화 {index + 1}
                  </span>

                  <div
                    style={{
                      padding:
                        "6px 10px",

                      borderRadius:
                        "7px",

                      color:
                        risk.color,

                      background:
                        risk.background,

                      fontWeight:
                        "700",
                    }}
                  >
                    {risk.text}
                  </div>

                </div>


                {/* ================= */}
                {/* IMAGE COMPARISON */}
                {/* ================= */}

                <div
                  style={{
                    display:
                      "grid",

                    gridTemplateColumns:
                      "1fr 1fr",

                    gap:
                      "10px",

                    marginTop:
                      "18px",

                    marginBottom:
                      "20px",
                  }}
                >

                  <div>

                    <div
                      style={{
                        marginBottom:
                          "7px",

                        fontSize:
                          "13px",

                        color:
                          "#64748b",
                      }}
                    >
                      기준 이미지
                    </div>

                    {baselineImageUrl ? (
                      <img
                        src={
                          baselineImageUrl.startsWith(
                            "http"
                          )
                            ? baselineImageUrl
                            : `${API_URL}${baselineImageUrl}`
                        }
                        alt="기준 이미지"
                        style={{
                          width:
                            "100%",

                          aspectRatio:
                            "4 / 3",

                          objectFit:
                            "cover",

                          borderRadius:
                            "10px",
                        }}
                      />
                    ) : (
                      <div
                        className="event-image"
                      >
                        <span>
                          📷
                        </span>

                        <small>
                          기준 이미지 없음
                        </small>
                      </div>
                    )}

                  </div>


                  <div>

                    <div
                      style={{
                        marginBottom:
                          "7px",

                        fontSize:
                          "13px",

                        color:
                          "#64748b",
                      }}
                    >
                      현재 이미지
                    </div>

                    {currentImageUrl ? (
                      <img
                        src={
                          currentImageUrl.startsWith(
                            "http"
                          )
                            ? currentImageUrl
                            : `${API_URL}${currentImageUrl}`
                        }
                        alt="현재 이미지"
                        style={{
                          width:
                            "100%",

                          aspectRatio:
                            "4 / 3",

                          objectFit:
                            "cover",

                          borderRadius:
                            "10px",
                        }}
                      />
                    ) : (
                      <div
                        className="event-image"
                      >
                        <span>
                          📷
                        </span>

                        <small>
                          현재 이미지 없음
                        </small>
                      </div>
                    )}

                  </div>

                </div>


                {/* ================= */}
                {/* BASIC INFO */}
                {/* ================= */}

                <div className="event-information">

                  <div>

                    <span>
                      변화 유형
                    </span>

                    <strong>
                      {getChangeLabel(
                        changeType
                      )}
                    </strong>

                  </div>


                  <div>

                    <span>
                      위험 등급
                    </span>

                    <strong>
                      {riskLevel}
                    </strong>

                  </div>


                  <div>

                    <span>
                      변화 위치
                    </span>

                    <strong>
                      X {x}
                      {" / "}
                      Y {y}
                    </strong>

                  </div>

                </div>


                {/* ================= */}
                {/* SITUATION */}
                {/* ================= */}

                <div
                  style={{
                    marginTop:
                      "20px",

                    padding:
                      "16px",

                    borderRadius:
                      "10px",

                    background:
                      "#f8fafc",
                  }}
                >

                  <strong>
                    상황 분석
                  </strong>

                  <p
                    style={{
                      margin:
                        "8px 0 0",

                      lineHeight:
                        "1.6",
                    }}
                  >
                    {situation}
                  </p>

                </div>


                {/* ================= */}
                {/* HAZARDS */}
                {/* ================= */}

                <div
                  style={{
                    marginTop:
                      "20px",
                  }}
                >

                  <strong>
                    위험요인
                  </strong>

                  <div
                    style={{
                      display:
                        "flex",

                      flexWrap:
                        "wrap",

                      gap:
                        "7px",

                      marginTop:
                        "9px",
                    }}
                  >

                    {hazardTypes.length >
                    0 ? (
                      hazardTypes.map(
                        (
                          hazard
                        ) => (
                          <span
                            key={
                              hazard
                            }
                            style={{
                              padding:
                                "6px 9px",

                              borderRadius:
                                "7px",

                              background:
                                "#fef2f2",

                              color:
                                "#b91c1c",

                              fontSize:
                                "13px",
                            }}
                          >
                            {getHazardLabel(
                              hazard
                            )}
                          </span>
                        )
                      )
                    ) : (
                      <span>
                        별도 위험요인 없음
                      </span>
                    )}

                  </div>

                </div>


                {/* ================= */}
                {/* RECOMMENDED ACTIONS */}
                {/* ================= */}

                <div
                  style={{
                    marginTop:
                      "20px",

                    padding:
                      "16px",

                    borderRadius:
                      "10px",

                    background:
                      "#eff6ff",
                  }}
                >

                  <strong>
                    권장 안전조치
                  </strong>

                  {actions.length >
                  0 ? (
                    <ol
                      style={{
                        margin:
                          "9px 0 0",

                        paddingLeft:
                          "20px",

                        lineHeight:
                          "1.7",
                      }}
                    >
                      {actions.map(
                        (
                          action,
                          actionIndex
                        ) => (
                          <li
                            key={
                              actionIndex
                            }
                          >
                            {action}
                          </li>
                        )
                      )}
                    </ol>
                  ) : (
                    <p>
                      별도 권장조치 없음
                    </p>
                  )}

                </div>

              </section>
            );
          }
        )}

      </main>

    </div>
  );
}


export default PatrolDetail;