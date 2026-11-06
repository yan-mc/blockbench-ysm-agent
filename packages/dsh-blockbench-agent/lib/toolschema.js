/**
 * 工具 JSON Schema 静态校验。
 *
 * 为什么需要它：DSH 对工具参数 schema 有硬性要求，**只要有一个参数不合法，
 * 整条插件的 fiberPhase 就是 failed** —— 表现是"所有 bb_* 工具消失 + 技能消失"，
 * 而不是单个工具报错。排查成本极高（实测踩过两次）。
 *
 * 而 host-smoke 用的是 stub `defineTool`（`(d) => d`），不做任何 schema 校验，
 * 所以完全拦不住这类错误。这个模块补上那道闸。
 *
 * 规则（来自实测的 DSH 报错）：
 *   - **硬性**：`type: "object"` 必须显式声明 `additionalProperties: true|false`
 *   - 提示级（DSH 接受，但加上更严谨）：`type: "array"` 无 `items`、`enum` 为空
 *
 * 注意：不要把这些"提示级"当错误。实测 DSH 接受无 items 的数组
 * （bb_session_start.resolution 等一大批工具一直这么写且正常工作）。
 */

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v)
}

/**
 * 校验单个 schema 节点。
 * @returns {{errors:string[], warnings:string[]}}
 */
export function lintSchema(node, pathName = 'schema') {
  const errors = []
  const warnings = []
  if (!isPlainObject(node)) {
    if (Array.isArray(node) && !node.length) errors.push(`${pathName}: 空数组 schema`)
    return { errors, warnings }
  }

  const t = node.type

  if (t === 'object') {
    if (node.additionalProperties !== true && node.additionalProperties !== false) {
      errors.push(`${pathName}.additionalProperties must be explicitly true or false`)
    }
  }

  if (t === 'array') {
    if (node.items === undefined) {
      warnings.push(`${pathName}.items missing（DSH 接受，但建议补上）`)
    } else {
      const sub = lintSchema(node.items, `${pathName}.items`)
      errors.push(...sub.errors)
      warnings.push(...sub.warnings)
    }
  }

  if (t === 'object' && isPlainObject(node.properties)) {
    for (const [k, v] of Object.entries(node.properties)) {
      const sub = lintSchema(v, `${pathName}.properties.${k}`)
      errors.push(...sub.errors)
      warnings.push(...sub.warnings)
    }
  }

  if (node.enum !== undefined) {
    if (!Array.isArray(node.enum) || node.enum.length === 0) {
      errors.push(`${pathName}.enum must be a non-empty array`)
    }
  }

  // 参数级 `required: true` 是插件自己的约定；JSON Schema 里的 required 必须是数组
  if (Object.prototype.hasOwnProperty.call(node, 'required') && node.required !== true && node.required !== false) {
    if (!Array.isArray(node.required)) {
      errors.push(`${pathName}.required must be boolean (plugin convention) or array (JSON Schema)`)
    }
  }

  return { errors, warnings }
}

/**
 * 校验一个工具定义（{name, parameters}）的参数部分。
 * @returns {{ok:boolean, errors:object[], warnings:object[]}}
 */
export function lintTool(tool) {
  const errors = []
  const warnings = []
  const name = tool?.name ?? '(unnamed)'
  const params = tool?.parameters
  if (params === undefined) return { ok: true, errors, warnings }
  if (!isPlainObject(params)) {
    return { ok: false, errors: [{ tool: name, message: 'parameters 必须是对象' }], warnings }
  }
  for (const [key, schema] of Object.entries(params)) {
    const r = lintSchema(schema, `parameters.${key}`)
    for (const msg of r.errors) errors.push({ tool: name, message: msg })
    for (const msg of r.warnings) warnings.push({ tool: name, message: msg })
  }
  return { ok: errors.length === 0, errors, warnings }
}

/** 批量校验；返回 {ok, errors, warnings, checked}。 */
export function lintTools(tools) {
  const errors = []
  const warnings = []
  let checked = 0
  for (const t of tools ?? []) {
    checked += 1
    const r = lintTool(t)
    if (!r.ok) errors.push(...r.errors)
    warnings.push(...r.warnings)
  }
  return { ok: errors.length === 0, errors, warnings, checked }
}
