interface SkeletonProps {
  height?: number;
  count?: number;
}

export default function Skeleton({ height = 72, count = 3 }: SkeletonProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ height, borderRadius: 12 }}
        />
      ))}
    </div>
  );
}
