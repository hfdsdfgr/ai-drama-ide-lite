import type {
  GenerationParameterField,
  GenerationParameterValue,
} from "../types/provider";

export function GenerationParameterFields({
  fields,
  values,
  onChange,
  disabled = false,
}: {
  fields: GenerationParameterField[];
  values: Record<string, GenerationParameterValue>;
  onChange: (key: string, value: GenerationParameterValue) => void;
  disabled?: boolean;
}) {
  return fields.map((field) => {
    const value = values[field.key] ?? field.default ?? "";
    if (field.control === "boolean") {
      return (
        <label className="parameter-boolean" key={field.key}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            disabled={disabled}
            onChange={(event) => onChange(field.key, event.target.checked)}
          />
          {field.label}
          {field.help && <small>{field.help}</small>}
        </label>
      );
    }
    if (field.control === "select") {
      const supported = field.options.some((option) => option.value === value);
      return (
        <label key={field.key}>
          {field.label}
          <select
            value={String(value)}
            disabled={disabled}
            aria-invalid={!supported}
            onChange={(event) =>
              onChange(field.key, parseValue(field, event.target.value))
            }
          >
            {!supported && (
              <option value={String(value)}>当前值 {String(value)}（不支持）</option>
            )}
            {field.options.map((option) => (
              <option key={String(option.value)} value={String(option.value)}>
                {option.label}
              </option>
            ))}
          </select>
          {field.help && <small>{field.help}</small>}
        </label>
      );
    }
    return (
      <label key={field.key}>
        {field.label}
        <input
          type={
            field.control === "integer" || field.control === "number" ? "number" : "text"
          }
          value={String(value)}
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
          step={field.step ?? undefined}
          disabled={disabled}
          onChange={(event) => onChange(field.key, parseValue(field, event.target.value))}
        />
        {field.help && <small>{field.help}</small>}
      </label>
    );
  });
}

function parseValue(field: GenerationParameterField, value: string) {
  if (field.value_type === "integer") return Number.parseInt(value, 10);
  if (field.value_type === "number") return Number(value);
  return value;
}
