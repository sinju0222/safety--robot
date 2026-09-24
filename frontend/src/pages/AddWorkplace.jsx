import { useState } from "react";

function AddWorkplace({ onBack, onCreate }) {
  const [name, setName] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();

    const trimmedName = name.trim();

    if (!trimmedName) {
      return;
    }

    onCreate(trimmedName);
  };

  return (
    <div className="screen">
      <header className="page-header">
        <button className="back-button" onClick={onBack}>
          ‹
        </button>

        <h2>작업장 추가</h2>
      </header>

      <main className="form-content">
        <div className="form-title">
          <h1>작업장 이름을<br />설정해주세요.</h1>
          <p>
            작업장을 구분할 수 있는 이름을 입력해주세요.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="input-label">
            작업장 이름
          </label>

          <input
            className="text-input"
            type="text"
            placeholder="예: 제1 작업장"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />

          <button
            className="primary-button form-submit"
            type="submit"
            disabled={!name.trim()}
          >
            다음
          </button>
        </form>
      </main>
    </div>
  );
}

export default AddWorkplace;
