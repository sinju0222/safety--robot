import { useState } from "react";

const policyOptions = [
  {
    key: "noObjects",
    title: "사물 배치 금지",
    description: "해당 구역에 새로운 사물이 배치되면 위험으로 판단합니다.",
  },
  {
    key: "noBottle",
    title: "물병 금지",
    description: "해당 구역에서 물병이 탐지되면 위험으로 판단합니다.",
  },
  {
    key: "noBox",
    title: "상자 금지",
    description: "해당 구역에서 상자가 탐지되면 위험으로 판단합니다.",
  },
];

function SafetyPolicy({
  policies,
  onSave,
  onBack,
}) {
  const [localPolicies, setLocalPolicies] = useState(policies);

  const togglePolicy = (zone, policyKey) => {
    setLocalPolicies((prev) => ({
      ...prev,

      [zone]: {
        ...prev[zone],

        [policyKey]: !prev[zone][policyKey],
      },
    }));
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

        <h2>안전정책</h2>
      </header>

      <main className="policy-content">
        <div className="policy-intro">
          <h1>구역별 안전정책</h1>

          <p>
            작업장 구역마다 적용할 안전 규칙을
            설정해주세요.
          </p>
        </div>

        {Object.keys(localPolicies).map((zone) => (
          <section
            className="zone-policy-card"
            key={zone}
          >
            <div className="zone-policy-header">
              <div className="zone-name-badge">
                {zone}
              </div>

              <div>
                <strong>{zone}구역</strong>
                <p>적용할 정책을 선택해주세요.</p>
              </div>
            </div>

            <div className="policy-list">
              {policyOptions.map((policy) => (
                <label
                  className="policy-item"
                  key={policy.key}
                >
                  <div className="policy-text">
                    <strong>
                      {policy.title}
                    </strong>

                    <span>
                      {policy.description}
                    </span>
                  </div>

                  <input
                    type="checkbox"
                    checked={
                      localPolicies[zone][policy.key]
                    }
                    onChange={() =>
                      togglePolicy(
                        zone,
                        policy.key
                      )
                    }
                  />

                  <span className="custom-checkbox">
                    ✓
                  </span>
                </label>
              ))}
            </div>
          </section>
        ))}
      </main>

      <div className="bottom-area">
        <button
          className="primary-button"
          onClick={() => onSave(localPolicies)}
        >
          안전정책 저장
        </button>
      </div>
    </div>
  );
}

export default SafetyPolicy;
