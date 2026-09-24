function PatrolDetail({
  workplace,
  patrolId,
  onBack,
}) {
  /*
   * ==========================================
   * 선택된 Patrol 찾기
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
   * Semantic Zone Type
   * ==========================================
   */

  const getZoneTypeName = (
    type
  ) => {
    switch (type) {
      case "work_area":
        return "작업구역";

      case "passage":
        return "통로";

      case "storage":
        return "창고";

      case "empty_area":
        return "빈공간";

      case "hazard_area":
        return "위험구역";

      case "restricted_area":
        return "접근제한구역";

      default:
        return "미지정";
    }
  };

  /*
   * ==========================================
   * Object Type
   * ==========================================
   */

  const getObjectTypeName = (
    type
  ) => {
    switch (type) {
      case "water_bottle":
        return "물병";

      case "box":
        return "상자";

      case "pallet":
        return "팔레트";

      case "person":
        return "사람";

      default:
        return (
          type || "미지정"
        );
    }
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
                {patrol.changeCount ||
                  0}
              </strong>

            </div>

            <div>

              <span>
                위험 이벤트
              </span>

              <strong>
                {patrol.riskEventCount ||
                  0}
              </strong>

            </div>

          </div>

        </section>

        {/* ========================= */}
        {/* EVENT TITLE */}
        {/* ========================= */}

        <h3 className="event-title">
          탐지 결과
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
          (event, index) => (
            <section
              className="event-card"
              key={
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
                  className={
                    event.riskLevel ===
                    "HIGH"
                      ? "risk-high"
                      : "risk-normal"
                  }
                >
                  {event.riskLevel ||
                    "NORMAL"}
                </div>

              </div>

              {/* ================= */}
              {/* IMAGE */}
              {/* ================= */}

              {event.image ? (
                <img
                  className="event-image"
                  src={
                    event.image
                  }
                  alt="변화 탐지"
                />
              ) : (
                <div className="event-image">

                  <span>
                    📷
                  </span>

                  <strong>
                    변화 탐지 이미지
                  </strong>

                  <small>
                    실제 로봇 연동 후
                    캡처 이미지가
                    표시됩니다.
                  </small>

                </div>
              )}

              {/* ================= */}
              {/* INFORMATION */}
              {/* ================= */}

              <div className="event-information">

                {/* 탐지 객체 */}

                <div>

                  <span>
                    탐지 객체
                  </span>

                  <strong>
                    {event.objectName ||
                      "미지정"}
                  </strong>

                </div>

                {/* 객체 유형 */}

                <div>

                  <span>
                    객체 유형
                  </span>

                  <strong>
                    {getObjectTypeName(
                      event.objectType
                    )}
                  </strong>

                </div>

                {/* Semantic Zone */}

                <div>

                  <span>
                    발생 구역
                  </span>

                  <strong>
                    {event.zone ||
                      "구역 외부"}
                  </strong>

                </div>

                {/* Zone Type */}

                <div>

                  <span>
                    공간 유형
                  </span>

                  <strong>
                    {getZoneTypeName(
                      event.zoneType
                    )}
                  </strong>

                </div>

                {/* Position */}

                <div>

                  <span>
                    위치
                  </span>

                  <strong>
                    X{" "}
                    {event.position?.x ??
                      "-"}
                    {" / "}
                    Y{" "}
                    {event.position?.y ??
                      "-"}
                  </strong>

                </div>

                {/* Distance */}

                {event.distanceToCobot !=
                  null && (
                  <div>

                    <span>
                      협동로봇 거리
                    </span>

                    <strong>
                      {
                        event.distanceToCobot
                      }
                      m
                    </strong>

                  </div>
                )}

                {/* Risk Score */}

                <div>

                  <span>
                    위험 점수
                  </span>

                  <strong>
                    {event.riskScore ??
                      0}
                    점
                  </strong>

                </div>

                {/* Risk Level */}

                <div>

                  <span>
                    위험 등급
                  </span>

                  <strong>
                    {event.riskLevel ||
                      "NORMAL"}
                  </strong>

                </div>

                {/* Policy */}

                <div>

                  <span>
                    적용 정책
                  </span>

                  <strong>
                    {event.policyName ||
                      "해당 없음"}
                  </strong>

                </div>

              </div>

              {/* ================= */}
              {/* ROBOT ACTION */}
              {/* ================= */}

              {event.action ===
                "COBOT_STOP" && (
                <div className="cobot-stop-box">

                  <strong>
                    협동로봇 STOP
                  </strong>

                  <span>
                    위험요소가 탐지되어
                    협동로봇 정지 정책이
                    적용되었습니다.
                  </span>

                </div>
              )}

              {!event.action && (
                <div className="event-normal-box">

                  <strong>
                    추가 제어 없음
                  </strong>

                  <span>
                    현재 적용된 제어
                    명령이 없습니다.
                  </span>

                </div>
              )}

            </section>
          )
        )}

      </main>

    </div>
  );
}

export default PatrolDetail;