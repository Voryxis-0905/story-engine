

interface StatusPanelProps {
  characterName: string;
  health: number;
  maxHealth: number;
  stamina: number;
  maxStamina: number;
  exp: number;
  level: number;
  realm: string;
}

export function StatusPanel({
  characterName,
  health,
  maxHealth,
  stamina,
  maxStamina,
  exp,
  level,
  realm,
}: StatusPanelProps) {
  return (
    <div className="status-panel">
      <div className="status-header">
        <h2>{characterName}</h2>
        <span className="realm-badge">{realm}</span>
      </div>
      <div className="stat-row">
        <label>HP</label>
        <div className="bar">
          <div className="bar-fill health" style={{ width: `${(health / maxHealth) * 100}%` }} />
        </div>
        <span>{health}/{maxHealth}</span>
      </div>
      <div className="stat-row">
        <label>SP</label>
        <div className="bar">
          <div className="bar-fill stamina" style={{ width: `${(stamina / maxStamina) * 100}%` }} />
        </div>
        <span>{stamina}/{maxStamina}</span>
      </div>
      <div className="stat-row">
        <label>EXP</label>
        <span>{exp}</span>
      </div>
      <div className="stat-row">
        <label>Level</label>
        <span>{level}</span>
      </div>
    </div>
  );
}