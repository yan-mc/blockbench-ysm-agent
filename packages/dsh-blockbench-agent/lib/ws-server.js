// BB-Agent 传输层：零依赖 WebSocket JSON-RPC 服务端（RFC 6455 最小实现）
// 运行位置：dsh Host 插件（Node 22+/24）。对应 docs/02 §2.4 Binding A。
//
// 设计边界（刻意保持最小）：
// - 只支持文本帧、ping/pong/close；不支持分片、扩展、二进制帧。
// - 连接后首包必须是 system.hello（携带 token）；之后才允许其他方法。
// - 单连接一次只处理一条请求（按到达顺序串行），足够本地 Agent 场景。
// - 生产实现建议直接使用 `ws`；本文件用于“零第三方依赖”的可测试骨架。
//
// 冒烟测试：prototype/dsh-plugin/ws-smoke-test.mjs

import http from 'node:http'
import { createHash, timingSafeEqual } from 'node:crypto'

const WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
const MAX_MESSAGE = 8 * 1024 * 1024

export class RpcError extends Error {
  constructor(code, message, data = undefined) {
    super(message)
    this.code = code
    this.data = data
  }
}

function errPayload(error) {
  if (error instanceof RpcError) {
    return { code: error.code, message: error.message, data: error.data }
  }
  return { code: -32603, message: 'internal error', data: { message: String(error?.message ?? error) } }
}

function safeEqual(a, b) {
  const x = Buffer.from(String(a)); const y = Buffer.from(String(b))
  return x.length === y.length && timingSafeEqual(x, y)
}

function encodeFrame(payloadBuffer, opcode = 0x1) {
  const len = payloadBuffer.length
  let header
  if (len < 126) {
    header = Buffer.allocUnsafe(2); header[1] = len
  } else if (len < 65536) {
    header = Buffer.allocUnsafe(4); header[1] = 126; header.writeUInt16BE(len, 2)
  } else {
    header = Buffer.allocUnsafe(10); header[1] = 127; header.writeBigUInt64BE(BigInt(len), 2)
  }
  header[0] = 0x80 | opcode
  return Buffer.concat([header, payloadBuffer])
}

function sendJson(socket, value, trace = '') {
  try {
    socket.write(encodeFrame(Buffer.from(JSON.stringify(value), 'utf8')))
  } catch (error) {
    console.warn?.('[bb-ws] send failed', trace, error?.message)
  }
}

export function createWsServer({ token, methods, logger = console, defaultTimeoutMs = 120000, onNotification, onConnection }) {
  if (!token) throw new Error('token required')
  const connections = new Set()
  const httpClients = new Set()
  const pending = new Map()
  let nextRequestId = 1
  let active = null
  const readBody = (req) => new Promise((resolve, reject) => {
    const chunks = []
    let size = 0
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > MAX_MESSAGE) { reject(new RpcError(-32600, 'request too large')); req.destroy(); return }
      chunks.push(chunk)
    })
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
    req.on('error', reject)
  })
  const tokenFromRequest = (req) => {
    const auth = String(req.headers.authorization || '')
    if (auth.toLowerCase().startsWith('bearer ')) return auth.slice(7).trim()
    if (req.headers['x-bb-token']) return String(req.headers['x-bb-token'])
    try { return new URL(req.url, 'http://127.0.0.1').searchParams.get('token') || '' } catch { return '' }
  }
  const writeSse = (client, value) => {
    try { client.res.write(`data: ${JSON.stringify(value)}\n\n`) } catch { /* ignore */ }
  }
  const server = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ ok: true, connections: connections.size, http_clients: httpClients.size }))
      return
    }
    if (req.url?.startsWith('/events') && req.method === 'GET') {
      if (!safeEqual(tokenFromRequest(req), token)) {
        res.writeHead(401, { 'content-type': 'text/plain' }); res.end('unauthorized'); return
      }
      res.writeHead(200, {
        'content-type': 'text/event-stream',
        'cache-control': 'no-cache',
        connection: 'keep-alive',
        'x-accel-buffering': 'no',
      })
      res.write('retry: 1500\n\n')
      const client = { kind: 'http', res, authed: true, sendEvent: null, sendMessage: null, ready: false }
      client.sendEvent = (method, params) => writeSse(client, { jsonrpc: '2.0', method, params })
      client.sendMessage = (msg) => writeSse(client, msg)
      httpClients.add(client)
      active = client
      try { onConnection?.(client) } catch (error) { logger.warn?.('[bb-http] onConnection failed', error?.message) }
      req.on('close', () => {
        httpClients.delete(client)
        if (active === client) active = null
        for (const [id, waiter] of pending) {
          clearTimeout(waiter.timer)
          waiter.reject(new RpcError(-32010, 'connection closed', { code: 'DISCONNECTED', recoverable: true }))
          pending.delete(id)
        }
      })
      return
    }
    if (req.url === '/rpc' && req.method === 'POST') {
      if (!safeEqual(tokenFromRequest(req), token)) {
        res.writeHead(401, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ jsonrpc: '2.0', id: null, error: errPayload(new RpcError(-32001, 'unauthorized')) }))
        return
      }
      void (async () => {
        let reqMsg
        try { reqMsg = JSON.parse(await readBody(req)) } catch {
          res.writeHead(400, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ jsonrpc: '2.0', id: null, error: errPayload(new RpcError(-32700, 'parse error')) }))
          return
        }
        // 客户端对服务端请求的响应
        if (reqMsg && reqMsg.id !== undefined && reqMsg.method === undefined) {
          const waiter = pending.get(reqMsg.id)
          if (waiter) {
            pending.delete(reqMsg.id)
            clearTimeout(waiter.timer)
            if (reqMsg.error) waiter.reject(Object.assign(new Error(reqMsg.error.message), { rpc: reqMsg.error }))
            else waiter.resolve(reqMsg.result)
          }
          res.writeHead(204); res.end(); return
        }
        // 客户端通知
        if (reqMsg && reqMsg.method && reqMsg.id === undefined) {
          try { onNotification?.(reqMsg.method, reqMsg.params ?? {}, { kind: 'http' }) } catch (error) { logger.warn?.('[bb-http] notification failed', error?.message) }
          res.writeHead(204); res.end(); return
        }
        const { id = null, method, params = {}, _meta = {} } = reqMsg ?? {}
        const fn = methods[method]
        if (typeof method !== 'string' || !fn) {
          res.writeHead(200, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ jsonrpc: '2.0', id, error: errPayload(new RpcError(-32601, `method not found: ${method}`)) }))
          return
        }
        const deadline = Math.min(defaultTimeoutMs, Number(_meta.deadline_ms) || defaultTimeoutMs)
        try {
          const result = await Promise.race([
            Promise.resolve(fn(params, { traceId: _meta.trace_id, conn: { kind: 'http' }, meta: _meta })),
            new Promise((_, reject) => { const timer = setTimeout(() => reject(new RpcError(-32015, `timeout after ${deadline}ms`)), deadline); timer.unref?.() }),
          ])
          res.writeHead(200, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ jsonrpc: '2.0', id, result }))
        } catch (error) {
          res.writeHead(200, { 'content-type': 'application/json' })
          res.end(JSON.stringify({ jsonrpc: '2.0', id, error: errPayload(error) }))
        }
      })()
      return
    }
    res.writeHead(426, { 'content-type': 'text/plain' })
    res.end('WebSocket upgrade required')
  })

  server.on('upgrade', (req, socket) => {
    if (req.url !== '/bb-agent/v1' || !req.headers['sec-websocket-key']) {
      socket.write('HTTP/1.1 400 Bad Request\r\n\r\n'); socket.destroy(); return
    }
    const accept = createHash('sha1').update(req.headers['sec-websocket-key'] + WS_GUID).digest('base64')
    socket.write([
      'HTTP/1.1 101 Switching Protocols',
      'Upgrade: websocket',
      'Connection: Upgrade',
      `Sec-WebSocket-Accept: ${accept}`,
      'Sec-WebSocket-Protocol: bb-agent.v1',
      '\r\n',
    ].join('\r\n'))

    let authed = false
    let buffer = Buffer.alloc(0)
    let closed = false
    const state = { socket, authed: false, sendEvent: null }

    state.sendEvent = (method, params) => sendJson(socket, { jsonrpc: '2.0', method, params })
    state.sendMessage = (msg) => sendJson(socket, msg)
    connections.add(state)

    const closeWith = (code, reason = '') => {
      if (closed) return
      closed = true
      const payload = Buffer.allocUnsafe(2 + Buffer.byteLength(reason))
      payload.writeUInt16BE(code, 0); payload.write(reason, 2)
      try { socket.write(encodeFrame(payload, 0x8)) } catch { /* ignore */ }
      try { socket.end() } catch { /* ignore */ }
      connections.delete(state)
    }

    async function handleMessage(text) {
      let req
      try { req = JSON.parse(text) } catch {
        sendJson(socket, { jsonrpc: '2.0', id: null, error: errPayload(new RpcError(-32700, 'parse error')) })
        return
      }
      // 1) 客户端对我们发起的请求的响应
      if (req && req.id !== undefined && req.method === undefined) {
        const waiter = pending.get(req.id)
        if (waiter) {
          pending.delete(req.id)
          clearTimeout(waiter.timer)
          if (req.error) waiter.reject(Object.assign(new Error(req.error.message), { rpc: req.error }))
          else waiter.resolve(req.result)
        }
        return
      }
      // 2) 客户端通知（事件）
      if (req && req.id === undefined && typeof req.method === 'string') {
        try { onNotification?.(req.method, req.params ?? {}, state) } catch (error) {
          logger.warn?.('[bb-ws] notification handler failed', error?.message)
        }
        return
      }
      const { id = null, method, params = {}, _meta = {} } = req ?? {}
      if (typeof method !== 'string') {
        sendJson(socket, { jsonrpc: '2.0', id, error: errPayload(new RpcError(-32600, 'invalid request')) })
        return
      }
      if (!authed) {
        if (method !== 'system.hello') {
          sendJson(socket, { jsonrpc: '2.0', id, error: errPayload(new RpcError(-32001, 'unauthorized', { code: 'UNAUTHORIZED' })) })
          closeWith(4001, 'unauthorized')
          return
        }
        const provided = params?.auth?.token
        if (!safeEqual(provided ?? '', token)) {
          sendJson(socket, { jsonrpc: '2.0', id, error: errPayload(new RpcError(-32001, 'bad token', { code: 'UNAUTHORIZED' })) })
          closeWith(4001, 'bad token')
          return
        }
    authed = true
    state.authed = true
    active = state
    try { onConnection?.(state) } catch (error) { logger.warn?.('[bb-ws] onConnection failed', error?.message) }
  }
      const fn = methods[method]
      if (!fn) {
        sendJson(socket, { jsonrpc: '2.0', id, error: errPayload(new RpcError(-32601, `method not found: ${method}`)) })
        return
      }
      const deadline = Math.min(defaultTimeoutMs, Number(_meta.deadline_ms) || defaultTimeoutMs)
      const traceId = _meta.trace_id || createHash('sha1').update(String(Date.now())).digest('hex').slice(0, 12)
      const t0 = Date.now()
      try {
        const result = await Promise.race([
          Promise.resolve(fn(params, { traceId, conn: state, meta: _meta })),
          new Promise((_, reject) => {
            const timer = setTimeout(() => reject(new RpcError(-32015, `timeout after ${deadline}ms`, {
              code: 'TIMEOUT', recoverable: true,
            })), deadline)
            timer.unref?.()
          }),
        ])
        logger.info?.(`[bb-ws] ${method} ok ${Date.now() - t0}ms trace=${traceId}`)
        sendJson(socket, { jsonrpc: '2.0', id, result })
      } catch (error) {
        logger.warn?.(`[bb-ws] ${method} fail ${Date.now() - t0}ms trace=${traceId}: ${error?.message ?? error}`)
        sendJson(socket, { jsonrpc: '2.0', id, error: errPayload(error) })
      }
    }

    socket.on('data', (chunk) => {
      buffer = Buffer.concat([buffer, chunk])
      while (buffer.length >= 2) {
        const b0 = buffer[0], b1 = buffer[1]
        const fin = (b0 & 0x80) !== 0
        const opcode = b0 & 0x0f
        const masked = (b1 & 0x80) !== 0
        let length = b1 & 0x7f
        let offset = 2
        if (length === 126) {
          if (buffer.length < 4) return
          length = buffer.readUInt16BE(2); offset = 4
        } else if (length === 127) {
          if (buffer.length < 10) return
          const big = buffer.readBigUInt64BE(2)
          if (big > BigInt(MAX_MESSAGE)) { closeWith(1009, 'too large'); return }
          length = Number(big); offset = 10
        }
        if (!fin || opcode === 0x0) { closeWith(1003, 'fragmentation unsupported'); return }
        const maskOffset = offset
        if (masked) offset += 4
        if (buffer.length < offset + length) return
        let payload = buffer.subarray(offset, offset + length)
        if (masked) {
          const mask = buffer.subarray(maskOffset, maskOffset + 4)
          const un = Buffer.allocUnsafe(length)
          for (let i = 0; i < length; i++) un[i] = payload[i] ^ mask[i & 3]
          payload = un
        }
        buffer = buffer.subarray(offset + length)
        if (opcode === 0x8) { closeWith(1000); return }
        if (opcode === 0x9) { try { socket.write(encodeFrame(payload, 0xA)) } catch { /* ignore */ } continue }
        if (opcode === 0xA) continue
        if (opcode !== 0x1) { closeWith(1003, 'text only'); return }
        void handleMessage(payload.toString('utf8'))
      }
    })
    socket.on('error', () => closeWith(1006, 'socket error'))
    socket.on('close', () => {
      closed = true
      connections.delete(state)
      if (active === state) active = null
      for (const [id, waiter] of pending) {
        clearTimeout(waiter.timer)
        waiter.reject(new RpcError(-32010, 'connection closed', { code: 'DISCONNECTED', recoverable: true }))
        pending.delete(id)
      }
    })
  })

  return {
    token,
    server,
    listen(port = 0, host = '127.0.0.1') {
      return new Promise((resolve, reject) => {
        server.once('error', reject)
        server.listen(port, host, () => resolve({ port: server.address().port }))
      })
    },
    close() {
      for (const c of connections) { try { c.socket.destroy() } catch { /* ignore */ } }
      for (const c of httpClients) { try { c.res.end() } catch { /* ignore */ } }
      httpClients.clear()
      for (const [, waiter] of pending) { clearTimeout(waiter.timer); waiter.reject(new RpcError(-32800, 'server closed')) }
      pending.clear()
      return new Promise((resolve) => server.close(resolve))
    },
    /** 向已鉴权的 Blockbench 客户端发起 JSON-RPC 请求并等待响应 */
    request(method, params = {}, { timeoutMs = defaultTimeoutMs } = {}) {
      const conn = active
      if (!conn?.authed) {
        return Promise.reject(new RpcError(-32010, 'Blockbench not connected', {
          code: 'PROJECT_NOT_OPEN', hint: 'wait for the runtime to connect or start it',
        }))
      }
      const id = `srv-${nextRequestId++}`
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id)
          reject(new RpcError(-32015, `upstream timeout ${method}`, { code: 'TIMEOUT', recoverable: true }))
        }, timeoutMs)
        timer.unref?.()
        pending.set(id, { resolve, reject, timer, method })
        conn.sendMessage({ jsonrpc: '2.0', id, method, params, _meta: { deadline_ms: timeoutMs } })
      })
    },
    broadcast(method, params) {
      for (const c of connections) c.sendEvent?.(method, params)
      for (const c of httpClients) c.sendEvent?.(method, params)
    },
    get connected() { return !!active?.authed },
    get connectionCount() { return connections.size + httpClients.size },
  }
}
