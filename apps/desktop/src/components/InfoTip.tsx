export function InfoTip({ text }: { text: string }) {
  return (
    <span className="info-tip" tabIndex={0} role="tooltip" aria-label={text}>
      <span className="info-tip-icon" aria-hidden="true">
        ℹ
      </span>
      <span className="info-tip-bubble">{text}</span>
    </span>
  );
}
