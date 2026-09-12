import { useEffect, useState } from "react";

import { getGenerationParameterSchema } from "../api/providers";
import type {
  CapabilityKey,
  GenerationParameterField,
  GenerationParameterSchema,
  GenerationParameterValue,
} from "../types/provider";

export function useGenerationParameterSchema(modelId: string, capability: CapabilityKey) {
  const [schema, setSchema] = useState<GenerationParameterSchema | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSchema(null);
    setError("");
    setLoading(Boolean(modelId));
    if (!modelId) {
      return () => {
        cancelled = true;
      };
    }
    getGenerationParameterSchema(modelId, capability)
      .then((value) => {
        if (!cancelled) {
          setSchema(value);
          setLoading(false);
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setError(reason.message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [modelId, capability]);

  return { schema, error, loading };
}

export function unsupportedParameterKeys(
  fields: GenerationParameterField[],
  values: Record<string, GenerationParameterValue>,
) {
  return fields
    .filter(
      (field) =>
        field.options.length > 0 &&
        !field.options.some((option) => option.value === values[field.key]),
    )
    .map((field) => field.key);
}
