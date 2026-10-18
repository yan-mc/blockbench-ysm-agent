// 零依赖 WebSocket JSON-RPC 冒烟测试
// 运行：node prototype/dsh-plugin/ws-smoke-test.mjs
// 覆盖：握手鉴权、hello、ping、错误 token、事件推送、并发请求。

import assert from 'node:assert/strict'
import { createWsServer } from './ws-server.js'

const TOKEN = 'test-token-' + Math.random().toString(36).slice(2)
const seenEvents = []
let callCount = 0

const server = createWsServer({
  token: TOKEN,
  logger: { info() {}, warn: console.warn },
  defaultTimeoutMs: 5000,
  methods: {
    'system.hello': (params) => ({
      protocol: 'bb-agent/1',
      server: { name: 'bb-agent-runtime', version: '0.1.0-test', blockbench: '5.2.2' },
      session: { project_id: 'smoke', revision: 0, state: 'idle' },
    }),
    'system.ping': (params, ctx) => {
      ctx.conn.sendEvent('event.heartbeat', { revision: 0, queue_len: 0, mem_mb: 1, gpu_ok: true })
      return { t: params.t ?? null, server_time: Date.now() }
    },
    'model.apply_patch': async (params) => {
      callCount++
      await new Promise((r) => setTimeout(r, 20))
      return { ok: true, revision: 1, changed: [{ kind: 'cube', id: 'cu_test', op: 'add' }], warnings: [] }
    },
  },
})

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url, ['bb-agent.v1'])
    ws.onopen = () => resolve(ws)
    ws.onerror = (e) => reject(new Error('ws error'))
  })
}

function rpc(ws, method, params = {}, id = Math.random().toString(36).slice(2)) {
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.method) { seenEvents.push(msg); return }
      if (msg.id !== id) return
      ws.removeEventListener('message', onMessage)
      if (msg.error) reject(Object.assign(new Error(msg.error.message), { rpc: msg.error }))
      else resolve(msg.result)
    }
    ws.addEventListener('message', onMessage)
    ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params, _meta: { trace_id: 'smoke' } }))
  })
}

const { port } = await server.listen(0)
const url = `ws://127.0.0.1:${port}/bb-agent/v1`
console.log('listening', url)

// 1) 错 token 必须被拒
{
  const ws = await connect(url)
  await assert.rejects(() => rpc(ws, 'system.hello', { protocol: 'bb-agent/1', auth: { token: 'wrong' } }),
    (error) => error.rpc?.code === -32001)
  ws.close()
  console.log('✓ bad token rejected')
}

// 2) 正确 hello
const ws = await connect(url)
ws.addEventListener('message', (event) => {
  const msg = JSON.parse(event.data)
  if (msg.method && msg.id !== undefined) {
    // 模拟 Blockbench 侧处理服务端请求
    if (msg.method === 'project.get_scene') {
      ws.send(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result: { revision: 1, counts: { bones: 1, cubes: 1 } } }))
    } else {
      ws.send(JSON.stringify({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: 'not found' } }))
    }
  }
})
const hello = await rpc(ws, 'system.hello', {
  protocol: 'bb-agent/1',
  auth: { token: TOKEN },
  client: { name: 'smoke', version: '0.1.0' },
})
assert.equal(hello.protocol, 'bb-agent/1')
assert.equal(hello.server.blockbench, '5.2.2')
console.log('✓ hello ok')

// 3) 服务端 -> 客户端请求/响应
const scene = await server.request('project.get_scene', { scope: 'summary' }, { timeoutMs: 3000 })
assert.equal(scene.counts.bones, 1)
console.log('✓ server->client request ok')

// 3) ping + 事件
const pong = await rpc(ws, 'system.ping', { t: 123 })
assert.equal(pong.t, 123)
await new Promise((r) => setTimeout(r, 50))
assert.ok(seenEvents.some((e) => e.method === 'event.heartbeat'), 'heartbeat event missing')
console.log('✓ ping + event ok')

// 4) 并发请求（服务端串行处理，均应成功）
const results = await Promise.all([
  rpc(ws, 'model.apply_patch', { ops: [{ op: 'add_bone' }] }),
  rpc(ws, 'model.apply_patch', { ops: [{ op: 'add_cube' }] }),
  rpc(ws, 'model.apply_patch', { ops: [{ op: 'delete' }] }),
])
assert.equal(results.length, 3)
assert.equal(callCount, 3)
console.log('✓ concurrent requests ok')

// 5) 未知方法
await assert.rejects(() => rpc(ws, 'nope.method', {}), (error) => error.rpc?.code === -32601)
console.log('✓ unknown method rejected')

ws.close()
await server.close()
console.log('\nALL SMOKE TESTS PASSED')
