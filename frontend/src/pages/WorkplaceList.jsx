function WorkplaceList({ workplaces, onAdd, onSelect }) {
  return (
    <div className="screen">
      <header className="top-header">
        <h1>Safety Robot</h1>
      </header>

      <main className="content">
        <div className="workplace-list">
          {workplaces.map((workplace) => (
            <button
              className="workplace-item"
              key={workplace.id}
              onClick={() => onSelect(workplace)}
            >
              <span className="workplace-name">
                {workplace.name}
              </span>

              <span className="last-patrol">
                {workplace.lastPatrol
                  ? `마지막 순찰 ${workplace.lastPatrol}`
                  : "순찰 없음"}
              </span>

              <span className="arrow">›</span>
            </button>
          ))}
        </div>
      </main>

      <div className="bottom-area">
        <button className="primary-button" onClick={onAdd}>
          + 작업장 추가하기
        </button>
      </div>
    </div>
  );
}

export default WorkplaceList;
