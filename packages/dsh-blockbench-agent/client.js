// DSH Web UI client half: a tiny composer-dock status pill for the Blockbench agent.
// Status data comes from the Host plugin's same-origin GET /bb-agent/status.
window.__ModuleLoader__.load({
  id: '@local/dsh-blockbench-agent',
  factory(require) {
    const React = require('react')
    const h = React.createElement

    function useAgentStatus() {
      const [status, setStatus] = React.useState(null)
      const [error, setError] = React.useState(false)
      React.useEffect(() => {
        let alive = true
        let timer = null
        const poll = async () => {
          try {
            const response = await fetch('/bb-agent/status', { cache: 'no-store' })
            if (!response.ok) throw new Error(`HTTP ${response.status}`)
            const data = await response.json()
            if (alive) { setStatus(data); setError(false) }
          } catch {
            if (alive) setError(true)
          }
          if (alive) timer = setTimeout(poll, 2000)
        }
        poll()
        return () => { alive = false; if (timer) clearTimeout(timer) }
      }, [])
      return { status, error }
    }

    function StatusPill() {
      const { status, error } = useAgentStatus()
      const connected = !!status?.connected && !error
      const gui = !!status?.gui_visible
      const review = status?.review
      const dotColor = error || (status && status.state === 'offline') ? 'var(--dsw-alias-state-error-primary)'
        : gui ? 'var(--dsw-alias-state-warn-primary)'
          : connected ? 'var(--dsw-alias-state-success-primary)'
            : 'var(--dsw-alias-state-idle-primary)'
      const stateLabel = error ? 'offline' : (status?.state ?? 'starting')
      const revision = Number.isFinite(status?.revision) ? `r${status.revision}` : ''
      const verdict = review?.verdict && review.verdict !== 'no_change_expected' ? review.verdict : ''
      const title = status
        ? `Blockbench Agent · ${stateLabel} ${revision}\nworkspace: ${status.runtime?.workspace ?? ''}\npid: ${status.runtime?.child_pid ?? '-'}`
        : 'Blockbench Agent：等待状态…'
      return h('div', {
        title,
        role: 'status',
        'aria-live': 'polite',
        style: {
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '2px 10px', borderRadius: 999, fontSize: 12, lineHeight: '18px',
          color: 'var(--dsw-alias-label-secondary)',
          background: 'var(--dsw-alias-bg-layer-1)',
          border: '1px solid var(--dsw-alias-border-l1)',
          userSelect: 'none', whiteSpace: 'nowrap',
        },
      },
        h('span', {
          'aria-hidden': true,
          style: {
            width: 7, height: 7, borderRadius: '50%', flex: '0 0 auto',
            background: dotColor,
            boxShadow: connected && !gui ? '0 0 0 2px color-mix(in srgb, var(--dsw-alias-state-success-primary) 18%, transparent)' : 'none',
          },
        }),
        h('span', { style: { color: 'var(--dsw-alias-label-primary)', fontWeight: 500 } }, 'Blockbench'),
        h('span', null, `${stateLabel}${revision ? ` · ${revision}` : ''}${gui ? ' · GUI' : ''}${verdict ? ` · ${verdict}` : ''}`),
      )
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'bb-agent-status',
          order: 10,
          label: 'Blockbench',
        }, StatusPill))
      },
    }
  },
})
