function PatrolDetail({
  patrol,
  onBack,
}) {
  const formatTime = (seconds) => {
    const minutes = Math.floor(
      seconds / 60
    );

    const remainSeconds =
      seconds % 60;

    return `${String(minutes).padStart(
      2,
      "0"
    )}:${String(
      remainSeconds
    ).padStart(2, "0")}`;
  };

  const formatDate = (date) => {
    return new Date(
      date
    ).toLocaleString("ko-KR");
  };

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
                {patrol.changeCount}
              </strong>
            </div>

            <div>
              <span>
                위험 이벤트
              </span>

              <strong>
                {
                  patrol.riskEventCount
                }
              </strong>
            </div>

          </div>

        </section>

        <h3 className="event-title">
          탐지 결과
        </h3>

        {patrol.events.length ===
          0 && (
          <div className="empty-dashboard">
            탐지된 변화가 없습니다.
          </div>
        )}

        {patrol.events.map(
          (event, index) => (
            <section
              className="event-card"
              key={event.id}
            >

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
                  {event.riskLevel}
                </div>

              </div>

              {/* 나중에 실제 캡처 이미지 */}
              <div className="event-image">
                변화 탐지 이미지
              </div>

              <div className="event-information">

                <div>
                  <span>
                    탐지 객체
                  </span>

                  <strong>
                    {
                      event.objectName
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    구역
                  </span>

                  <strong>
                    {event.zone}구역
                  </strong>
                </div>

                <div>
                  <span>
                    위치
                  </span>

                  <strong>
                    (
                    {
                      event.position.x
                    }
                    ,{" "}
                    {
                      event.position.y
                    }
                    )
                  </strong>
                </div>

                {event.distanceToCobot !==
                  undefined && (
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

              {event.action ===
                "COBOT_STOP" && (
                <div className="cobot-stop-box">

                  <strong>
                    협동로봇 STOP
                  </strong>

                  <span>
                    {
                      event.actionText
                    }
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
