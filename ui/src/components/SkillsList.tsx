

interface Skill {
  id: string;
  name: string;
  level: number;
  description: string;
}

interface SkillsListProps {
  skills: Skill[];
}

export function SkillsList({ skills }: SkillsListProps) {
  return (
    <div className="skills-list">
      <h3>Skills</h3>
      <ul>
        {skills.map((skill) => (
          <li key={skill.id}>
            <span className="skill-name">{skill.name}</span>
            <span className="skill-level">Lv.{skill.level}</span>
            <span className="skill-desc">{skill.description}</span>
          </li>
        ))}
        {skills.length === 0 && <div className="empty">No skills</div>}
      </ul>
    </div>
  );
}