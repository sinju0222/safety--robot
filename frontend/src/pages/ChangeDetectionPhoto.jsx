import {
  useEffect,
  useState,
} from "react";


const API_URL =
  "http://127.0.0.1:8000";


function getRiskInfo(
  riskLevel
) {
  switch (riskLevel) {
    case "HIGH":
      return {
        text: "HIGH",
        label: "높음",
        color: "#b91c1c",
        background:
          "#fee2e2",
      };

    case "MEDIUM":
      return {
        text: "MEDIUM",
        label: "주의",
        color: "#c2410c",
        background:
          "#ffedd5",
      };

    case "LOW":
      return {
        text: "LOW",
        label: "낮음",
        color: "#a16207",
        background:
          "#fef9c3",
      };

    case "NORMAL":
      return {
        text: "NORMAL",
        label: "정상",
        color: "#15803d",
        background:
          "#dcfce7",
      };

    default:
      return {
        text: "UNKNOWN",
        label: "분석 대기",
        color: "#475569",
        background:
          "#e2e8f0",
      };
  }
}


function getChangeLabel(
  changeType
) {
  const labels = {
    ADDED:
      "물체 추가",

    REMOVED:
      "물체 제거",

    MOVED:
      "물체 이동",

    STATE_CHANGED:
      "상태 변화",

    MIXED:
      "복합 변화",

    NO_CHANGE:
      "변화 없음",
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


function ChangeDetectionPhoto({
  workplaceId,
}) {
  const [
    hazards,
    setHazards,
  ] = useState([]);

  const [
    selectedId,
    setSelectedId,
  ] = useState(null);

  const [
    ackLoading,
    setAckLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  /*
   * ==========================================
   * Hazard Load
   * ==========================================
   */

  useEffect(() => {
    let active = true;

    const loadHazards =
      async () => {
        try {
          const response =
            await fetch(
              `${API_URL}/api/robot-events/hazards?workplace_id=${encodeURIComponent(
                workplaceId
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

          const nextHazards =
            Array.isArray(
              data.hazards
            )
              ? data.hazards
              : [];

          setHazards(
            nextHazards
          );

          setSelectedId(
            (current) => {
              if (
                current &&
                nextHazards.some(
                  (hazard) =>
                    hazard.event_id ===
                    current
                )
              ) {
                return current;
              }

              return (
                nextHazards[0]
                  ?.event_id ||
                null
              );
            }
          );

          setError("");
        } catch (loadError) {
          console.error(
            "변화 분석 로딩 실패:",
            loadError
          );

          if (active) {
            setError(
              "변화 분석 데이터를 불러올 수 없습니다."
            );
          }
        }
      };


    loadHazards();


    const timer =
      setInterval(
        loadHazards,
        2000
      );


    return () => {
      active = false;

      clearInterval(
        timer
      );
    };
  }, [workplaceId]);


  /*
   * ==========================================
   * Acknowledge
   * ==========================================
   */

  const acknowledge =
    async () => {
      if (
        !selectedId ||
        ackLoading
      ) {
        return;
      }

      try {
        setAckLoading(
          true
        );

        const response =
          await fetch(
            `${API_URL}/api/robot-events/hazards/${encodeURIComponent(
              selectedId
            )}/ack`,
            {
              method:
                "POST",
            }
          );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        const remaining =
          hazards.filter(
            (hazard) =>
              hazard.event_id !==
              selectedId
          );

        setHazards(
          remaining
        );

        setSelectedId(
          remaining[0]
            ?.event_id ||
            null
        );

        setError("");
      } catch (ackError) {
        console.error(
          "변화 확인 처리 실패:",
          ackError
        );

        setError(
          "변화 확인 처리에 실패했습니다."
        );
      } finally {
        setAckLoading(
          false
        );
      }
    };


  /*
   * ==========================================
   * Empty
   * ==========================================
   */

  if (
    hazards.length === 0
  ) {
    return (
      <div
        className="change-photo-card"
      >
        <h4>
          AI 변화 분석
        </h4>

        <p>
          현재 확인이 필요한
          환경 변화가 없습니다.
        </p>

        {error && (
          <p
            style={{
              color:
                "#b91c1c",
            }}
          >
            {error}
          </p>
        )}
      </div>
    );
  }


  /*
   * ==========================================
   * Selected Event
   * ==========================================
   */

  const selected =
    hazards.find(
      (hazard) =>
        hazard.event_id ===
        selectedId
    ) ||
    hazards[0];


  const risk =
    getRiskInfo(
      selected.risk_level
    );


  const actions =
    Array.isArray(
      selected.recommended_actions
    )
      ? selected.recommended_actions
      : [];


  const hazardTypes =
    Array.isArray(
      selected.hazard_types
    )
      ? selected.hazard_types
      : [];


  /*
   * ==========================================
   * Render
   * ==========================================
   */

  return (
    <div
      className="change-photo-card"
    >
      <div
        style={{
          display:
            "flex",

          justifyContent:
            "space-between",

          alignItems:
            "center",

          gap:
            "10px",

          marginBottom:
            "12px",
        }}
      >
        <h4
          style={{
            margin: 0,
          }}
        >
          AI 변화 분석
        </h4>

        <span
          style={{
            padding:
              "5px 9px",

            borderRadius:
              "7px",

            fontSize:
              "12px",

            fontWeight:
              "700",

            color:
              risk.color,

            background:
              risk.background,
          }}
        >
          {risk.text}
        </span>
      </div>


      {hazards.length > 1 && (
        <div
          style={{
            marginBottom:
              "12px",
          }}
        >
          <label
            style={{
              display:
                "block",

              fontSize:
                "12px",

              marginBottom:
                "5px",
            }}
          >
            미확인 변화
          </label>

          <select
            value={
              selected.event_id
            }
            onChange={(event) =>
              setSelectedId(
                event.target.value
              )
            }
            style={{
              width:
                "100%",

              padding:
                "8px",

              borderRadius:
                "7px",

              border:
                "1px solid #d1d5db",
            }}
          >
            {hazards.map(
              (
                hazard,
                index
              ) => (
                <option
                  key={
                    hazard.event_id
                  }
                  value={
                    hazard.event_id
                  }
                >
                  변화{" "}
                  {index + 1}
                  {" · "}
                  {hazard.risk_level ||
                    "분석 대기"}
                  {" · "}
                  {getChangeLabel(
                    hazard.change_type
                  )}
                </option>
              )
            )}
          </select>
        </div>
      )}


      {/* 이미지 비교 */}

      <div
        style={{
          display:
            "grid",

          gridTemplateColumns:
            "1fr 1fr",

          gap:
            "8px",

          marginBottom:
            "14px",
        }}
      >
        <div>
          <div
            style={{
              fontSize:
                "12px",

              marginBottom:
                "5px",

              color:
                "#64748b",
            }}
          >
            기준 이미지
          </div>

          {selected.baselineImageUrl ? (
            <img
              src={
                `${API_URL}` +
                selected.baselineImageUrl
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
                  "8px",
              }}
            />
          ) : (
            <div>
              이미지 없음
            </div>
          )}
        </div>


        <div>
          <div
            style={{
              fontSize:
                "12px",

              marginBottom:
                "5px",

              color:
                "#64748b",
            }}
          >
            현재 이미지
          </div>

          {selected.currentImageUrl ||
          selected.imageUrl ? (
            <img
              src={
                `${API_URL}` +
                (
                  selected.currentImageUrl ||
                  selected.imageUrl
                )
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
                  "8px",
              }}
            />
          ) : (
            <div>
              이미지 없음
            </div>
          )}
        </div>
      </div>


      {/* 기본 정보 */}

      <div
        style={{
          display:
            "flex",

          flexWrap:
            "wrap",

          gap:
            "6px",

          marginBottom:
            "14px",
        }}
      >
        <span
          style={{
            padding:
              "5px 8px",

            borderRadius:
              "6px",

            background:
              risk.background,

            color:
              risk.color,

            fontSize:
              "12px",

            fontWeight:
              "700",
          }}
        >
          위험도{" "}
          {risk.text}
        </span>

        <span
          style={{
            padding:
              "5px 8px",

            borderRadius:
              "6px",

            background:
              "#e0f2fe",

            color:
              "#0369a1",

            fontSize:
              "12px",

            fontWeight:
              "700",
          }}
        >
          {getChangeLabel(
            selected.change_type
          )}
        </span>
      </div>


      {/* 상황 */}

      <div
        style={{
          marginBottom:
            "14px",
        }}
      >
        <strong>
          상황 분석
        </strong>

        <p
          style={{
            margin:
              "6px 0 0",

            lineHeight:
              "1.55",

            fontSize:
              "13px",
          }}
        >
          {selected.situation ||
            selected.reason ||
            "상황 분석 결과가 없습니다."}
        </p>
      </div>


      {/* 위험요인 */}

      <div
        style={{
          marginBottom:
            "14px",
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
              "5px",

            marginTop:
              "7px",
          }}
        >
          {hazardTypes.length >
          0 ? (
            hazardTypes.map(
              (hazard) => (
                <span
                  key={
                    hazard
                  }
                  style={{
                    padding:
                      "5px 7px",

                    borderRadius:
                      "6px",

                    background:
                      "#fef2f2",

                    color:
                      "#b91c1c",

                    fontSize:
                      "12px",
                  }}
                >
                  {getHazardLabel(
                    hazard
                  )}
                </span>
              )
            )
          ) : (
            <span
              style={{
                fontSize:
                  "12px",

                color:
                  "#64748b",
              }}
            >
              별도 위험요인 없음
            </span>
          )}
        </div>
      </div>


      {/* 권장 조치 */}

      <div
        style={{
          padding:
            "11px",

          marginBottom:
            "14px",

          borderRadius:
            "8px",

          background:
            "#f8fafc",
        }}
      >
        <strong>
          권장 안전조치
        </strong>

        {actions.length >
        0 ? (
          <ol
            style={{
              paddingLeft:
                "19px",

              margin:
                "7px 0 0",

              lineHeight:
                "1.55",

              fontSize:
                "13px",
            }}
          >
            {actions.map(
              (
                action,
                index
              ) => (
                <li
                  key={
                    index
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


      {/* 위치 */}

      <div
        style={{
          marginBottom:
            "12px",

          fontSize:
            "12px",

          color:
            "#64748b",
        }}
      >
        변화 위치: X{" "}
        {Number(
          selected.x
        ).toFixed(2)}
        m / Y{" "}
        {Number(
          selected.y
        ).toFixed(2)}
        m
      </div>


      {error && (
        <div
          style={{
            marginBottom:
              "10px",

            color:
              "#b91c1c",

            fontSize:
              "12px",
          }}
        >
          {error}
        </div>
      )}


      <button
        type="button"
        onClick={
          acknowledge
        }
        disabled={
          ackLoading
        }
        style={{
          width:
            "100%",

          padding:
            "10px",

          border:
            "none",

          borderRadius:
            "7px",

          background:
            "#2563eb",

          color:
            "#ffffff",

          fontWeight:
            "700",

          cursor:
            ackLoading
              ? "default"
              : "pointer",

          opacity:
            ackLoading
              ? 0.6
              : 1,
        }}
      >
        {ackLoading
          ? "처리 중..."
          : "변화 확인 완료"}
      </button>
    </div>
  );
}


export default ChangeDetectionPhoto;