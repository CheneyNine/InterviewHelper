type RadarChartProps = {
  scores: Record<string, number | null>;
};

const dimensions = [
  { key: "visible_expression", label: "神情与镜头表现", shortLabel: "镜头表现" },
  { key: "content_and_fluency", label: "回答内容与流畅程度", shortLabel: "内容流畅" },
  { key: "tone_and_voice", label: "语气与声音表现", shortLabel: "语气声音" },
  { key: "answer_structure", label: "回答结构与题目呈现", shortLabel: "回答结构" },
  { key: "relevance", label: "题目相关性", shortLabel: "题目相关" },
  { key: "technical_depth", label: "专业准确性与技术深度", shortLabel: "技术深度" },
  { key: "evidence_and_contribution", label: "证据与个人贡献", shortLabel: "证据贡献" },
  { key: "role_fit", label: "岗位匹配度与业务理解", shortLabel: "岗位匹配" },
] as const;

const width = 520;
const height = 430;
const centerX = width / 2;
const centerY = height / 2;
const radius = 132;
const labelRadius = 174;

function polarPoint(index: number, pointRadius: number) {
  const angle = (Math.PI * 2 * index) / dimensions.length - Math.PI / 2;
  return {
    x: centerX + Math.cos(angle) * pointRadius,
    y: centerY + Math.sin(angle) * pointRadius,
  };
}

function polygonPoints(pointRadius: number) {
  return dimensions
    .map((_, index) => {
      const point = polarPoint(index, pointRadius);
      return point.x + "," + point.y;
    })
    .join(" ");
}

export function RadarChart({ scores }: RadarChartProps) {
  const values = dimensions.map(({ key }) => {
    const value = scores[key];
    return value == null ? null : Math.min(1, Math.max(0, value));
  });
  const dataPoints = values
    .map((value, index) => {
      const point = polarPoint(index, radius * (value ?? 0));
      return point.x + "," + point.y;
    })
    .join(" ");
  const hasZeroScore = values.some((value) => value === 0);

  return (
    <div className="radar-section">
      <div className="radar-heading">
        <span>能力画像</span>
        <h2>八维度总览</h2>
      </div>
      <div className="radar-layout">
        <svg
          className="radar-chart"
          viewBox={"0 0 " + width + " " + height}
          role="img"
          aria-labelledby="radar-title radar-description"
        >
          <title id="radar-title">面试表现八维雷达图</title>
          <desc id="radar-description">
            展示神情、内容流畅度、声音、结构、相关性、技术深度、证据贡献和岗位匹配度。
          </desc>

          {[0.2, 0.4, 0.6, 0.8, 1].map((level) => (
            <polygon
              className="radar-grid"
              key={level}
              points={polygonPoints(radius * level)}
            />
          ))}
          {dimensions.map((_, index) => {
            const point = polarPoint(index, radius);
            return (
              <line
                className="radar-axis"
                key={dimensions[index].key}
                x1={centerX}
                y1={centerY}
                x2={point.x}
                y2={point.y}
              />
            );
          })}

          <polygon className="radar-area" points={dataPoints} />
          {values.map((value, index) => {
            if (value == null || value === 0) return null;
            const point = polarPoint(index, radius * value);
            return (
              <circle
                className="radar-point"
                key={dimensions[index].key}
                cx={point.x}
                cy={point.y}
                r="4.5"
              >
                <title>{dimensions[index].label + " " + Math.round(value * 100) + "分"}</title>
              </circle>
            );
          })}
          {hasZeroScore && <circle className="radar-point radar-point-zero" cx={centerX} cy={centerY} r="4.5" />}

          {dimensions.map((dimension, index) => {
            const point = polarPoint(index, labelRadius);
            const anchor = Math.abs(point.x - centerX) < 12
              ? "middle"
              : point.x > centerX
                ? "start"
                : "end";
            return (
              <text
                className="radar-label"
                key={dimension.key}
                x={point.x}
                y={point.y}
                textAnchor={anchor}
                dominantBaseline="middle"
              >
                {dimension.shortLabel}
              </text>
            );
          })}
        </svg>

        <div className="radar-legend" aria-label="八维度分数">
          {dimensions.map((dimension, index) => {
            const value = values[index];
            return (
              <div className="radar-legend-row" key={dimension.key}>
                <span className="radar-legend-marker" />
                <span>{dimension.label}</span>
                <strong className={value == null ? "is-unavailable" : ""}>
                  {value == null ? "暂无" : Math.round(value * 100) + "分"}
                </strong>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}