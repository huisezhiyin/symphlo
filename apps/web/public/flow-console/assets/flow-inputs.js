const inputNamePattern = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const supportedTypes = new Set(["string", "number", "integer", "boolean", "object", "array"]);
const maxInputBytes = 64 * 1024;

export function flowInputDefinitions(flow) {
  const rawInputs = flow && flow.inputs != null ? flow.inputs : {};
  if (!rawInputs || Array.isArray(rawInputs) || typeof rawInputs !== "object") {
    throw new Error("Flow inputs 必须是 object");
  }
  return Object.entries(rawInputs).map(([key, rawSpec]) => {
    if (!inputNamePattern.test(key)) throw new Error(`无效的 Flow input 名称：${key}`);
    if (!rawSpec || Array.isArray(rawSpec) || typeof rawSpec !== "object") {
      throw new Error(`Flow input ${key} 的定义必须是 object`);
    }
    const type = rawSpec.type || "string";
    if (!supportedTypes.has(type)) throw new Error(`Flow input ${key} 使用了不支持的类型：${type}`);
    return {
      key,
      type,
      required: rawSpec.required === true,
      hasDefault: Object.prototype.hasOwnProperty.call(rawSpec, "default") && rawSpec.default !== null,
      defaultValue: rawSpec.default,
      label: String(rawSpec.title || rawSpec.label || humanizeInputName(key)),
      description: typeof rawSpec.description === "string" ? rawSpec.description : "",
    };
  });
}

export function flowInputControlValue(definition) {
  if (!definition.hasDefault) return "";
  if (definition.type === "object" || definition.type === "array") {
    return JSON.stringify(definition.defaultValue, null, 2);
  }
  if (definition.type === "boolean") return definition.defaultValue ? "true" : "false";
  return String(definition.defaultValue);
}

export function parseFlowInputValues(flow, rawValues) {
  const definitions = flowInputDefinitions(flow);
  const values = {};
  for (const definition of definitions) {
    const hasRaw = Object.prototype.hasOwnProperty.call(rawValues, definition.key);
    let raw = hasRaw ? rawValues[definition.key] : undefined;
    if ((raw === undefined || raw === "") && definition.hasDefault) raw = definition.defaultValue;
    if (raw === undefined || raw === "") {
      if (definition.required) throw new Error(`请填写必填项：${definition.label}`);
      continue;
    }
    values[definition.key] = parseValue(definition, raw);
  }
  let encoded;
  try {
    encoded = new TextEncoder().encode(JSON.stringify(values));
  } catch (error) {
    throw new Error(`Flow inputs 不是有效 JSON：${error.message || String(error)}`);
  }
  if (encoded.length > maxInputBytes) {
    throw new Error(`Flow inputs 超过 ${maxInputBytes} bytes`);
  }
  return values;
}

function parseValue(definition, raw) {
  if (definition.type === "string") {
    const value = String(raw);
    if (definition.required && !value.trim()) throw new Error(`请填写必填项：${definition.label}`);
    return value;
  }
  if (definition.type === "number" || definition.type === "integer") {
    const value = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isFinite(value)) throw new Error(`${definition.label} 必须是有效数字`);
    if (definition.type === "integer" && !Number.isInteger(value)) {
      throw new Error(`${definition.label} 必须是整数`);
    }
    return value;
  }
  if (definition.type === "boolean") {
    if (typeof raw === "boolean") return raw;
    if (raw === "true") return true;
    if (raw === "false") return false;
    throw new Error(`${definition.label} 必须是 true 或 false`);
  }
  let value = raw;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch (_) {
      throw new Error(`${definition.label} 必须是有效 JSON`);
    }
  }
  if (definition.type === "array" && !Array.isArray(value)) {
    throw new Error(`${definition.label} 必须是 JSON array`);
  }
  if (
    definition.type === "object"
    && (!value || Array.isArray(value) || typeof value !== "object")
  ) {
    throw new Error(`${definition.label} 必须是 JSON object`);
  }
  return value;
}

function humanizeInputName(key) {
  return key.replace(/[-_]+/g, " ").replace(/^./, (value) => value.toUpperCase());
}
