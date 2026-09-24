import {
  useEffect,
  useState,
} from "react";

const policyOptions = [
  {
    key: "noObjects",
    title: "사물 배치 금지",
    description:
      "해당 구역에 새로운 사물이 배치되면 위험으로 판단합니다.",
  },
  {
    key: "noBottle",
    title: "물병 금지",
    description:
      "해당 구역에서 물병이 탐지되면 위험으로 판단합니다.",
  },
  {
    key: "noBox",
    title: "상자 금지",
    description:
      "해당 구역에서 상자가 탐지되면 위험으로 판단합니다.",
  },
];

const DEFAULT_POLICY = {
  noObjects: false,
  noBottle: false,
  noBox: false,
};

const ZONE_TYPE_NAMES = {
  work_area: "작업구역",
  passage: "통로",
  storage: "창고",
  empty_area: "빈공간",
  hazard_area: "위험구역",
  restricted_area: "접근제한구역",
};

function SafetyPolicy({
  workplace,
  onSave,
  onBack,
}) {
  const zones =
    workplace?.map?.zones || [];

  /*
   * ==========================================
   * Semantic Zone 기준 정책 생성
   *
   * {
   *   "1": {
   *     noObjects: false,
   *     noBottle: false,
   *     noBox: false
   *   }
   * }
   * ==========================================
   */

  const createInitialPolicies = () => {
    const savedPolicies =
      workplace?.policies || {};

    const result = {};

    zones.forEach((zone) => {
      const zoneKey =
        String(zone.id);

      result[zoneKey] = {
        ...DEFAULT_POLICY,
        ...(savedPolicies[
          zoneKey
        ] || {}),
      };
    });

    return result;
  };

  const [
    localPolicies,
    setLocalPolicies,
  ] = useState(
    createInitialPolicies
  );

  /*
   * workplace가 변경되면
   * 정책 화면도 다시 구성
   */

  useEffect(() => {
    setLocalPolicies(
      createInitialPolicies()
    );
  }, [workplace]);

  /*
   * ==========================================
   * 공간 유형 이름
   * ==========================================
   */

  const getZoneTypeName = (
    type
  ) => {
    return (
      ZONE_TYPE_NAMES[type] ||
      "미지정"
    );
  };

  /*
   * ==========================================
   * 정책 ON / OFF
   * ==========================================
   */

  const togglePolicy = (
    zoneId,
    policyKey
  ) => {
    const zoneKey =
      String(zoneId);

    setLocalPolicies(
      (prev) => ({
        ...prev,

        [zoneKey]: {
          ...DEFAULT_POLICY,
          ...(prev[
            zoneKey
          ] || {}),

          [policyKey]:
            !(
              prev[
                zoneKey
              ]?.[
                policyKey
              ] || false
            ),
        },
      })
    );
  };

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
          안전정책
        </h2>

      </header>

      {/* ========================= */}
      {/* CONTENT */}
      {/* ========================= */}

      <main className="policy-content">

        <div className="policy-intro">

          <h1>
            구역별 안전정책
          </h1>

          <p>
            지도에서 설정한 실제
            작업장 구역마다 적용할
            안전 규칙을 설정해주세요.
          </p>

        </div>

        {/* ========================= */}
        {/* 구역 없음 */}
        {/* ========================= */}

        {zones.length === 0 && (
          <div className="empty-dashboard">

            <strong>
              설정된 구역이 없습니다.
            </strong>

            <p>
              먼저 작업장 지도를
              제작하고 구역을
              설정해주세요.
            </p>

          </div>
        )}

        {/* ========================= */}
        {/* Semantic Zone Policies */}
        {/* ========================= */}

        {zones.map((zone) => {
          const zoneKey =
            String(zone.id);

          const zonePolicies =
            localPolicies[
              zoneKey
            ] ||
            DEFAULT_POLICY;

          return (
            <section
              className="zone-policy-card"
              key={zone.id}
            >

              {/* ================= */}
              {/* ZONE HEADER */}
              {/* ================= */}

              <div className="zone-policy-header">

                <div
                  className={
                    `zone-name-badge zone-policy-type-${zone.type}`
                  }
                >
                  {zone.id}
                </div>

                <div>

                  <strong>
                    {zone.name}
                  </strong>

                  <p>
                    {getZoneTypeName(
                      zone.type
                    )}
                    {" · "}
                    적용할 정책을
                    선택해주세요.
                  </p>

                </div>

              </div>

              {/* ================= */}
              {/* POLICY LIST */}
              {/* ================= */}

              <div className="policy-list">

                {policyOptions.map(
                  (policy) => (
                    <label
                      className="policy-item"
                      key={
                        policy.key
                      }
                    >

                      <div className="policy-text">

                        <strong>
                          {
                            policy.title
                          }
                        </strong>

                        <span>
                          {
                            policy.description
                          }
                        </span>

                      </div>

                      <input
                        type="checkbox"
                        checked={
                          zonePolicies[
                            policy.key
                          ] ||
                          false
                        }
                        onChange={() =>
                          togglePolicy(
                            zone.id,
                            policy.key
                          )
                        }
                      />

                      <span className="custom-checkbox">
                        ✓
                      </span>

                    </label>
                  )
                )}

              </div>

            </section>
          );
        })}

      </main>

      {/* ========================= */}
      {/* BOTTOM */}
      {/* ========================= */}

      <div className="bottom-area">

        <button
          className="primary-button"
          onClick={() =>
            onSave(
              localPolicies
            )
          }
          disabled={
            zones.length === 0
          }
        >
          안전정책 저장
        </button>

      </div>

    </div>
  );
}

export default SafetyPolicy;