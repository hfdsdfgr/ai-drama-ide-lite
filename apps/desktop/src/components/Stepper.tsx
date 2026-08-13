interface StepperProps {
  steps: string[];
  current: number; // 1-based；0 = 未开始
  doneSteps: number; // 已完成的步骤数（0-based 之前全部完成）
}

export function Stepper({ steps, current, doneSteps }: StepperProps) {
  return (
    <ol className="stepper">
      {steps.map((label, i) => {
        const stepNo = i + 1;
        const done = stepNo <= doneSteps;
        const active = stepNo === current && !done;
        return (
          <li
            key={label}
            className={
              done ? "step done" : active ? "step current" : "step"
            }
          >
            <span className="step-dot" aria-hidden="true">
              {done ? "✓" : active ? "●" : "○"}
            </span>
            <span className="step-label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
