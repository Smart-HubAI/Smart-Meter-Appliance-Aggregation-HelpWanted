export default function EnergyScoreRing({ score, size = 56 }) {
  return (
    <div
      className="energy-score-ring"
      style={{ "--score": score, width: size, height: size }}
      data-score={score}
    />
  );
}
