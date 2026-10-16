import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { AgentRow, PaneData } from '../types'

// The room's data comes from the local agents board server (board/serve.py,
// started by scripts/install.sh), which reads every session's transcript.
const PANE = 'agents-room'
const TITLE = 'الوكلاء'
const PANE_URL = 'http://127.0.0.1:8795/api/pane?w=440'
const ROOM_PX = 420 // CSS pixels the room takes in the pane
const BOARD_URL = 'http://127.0.0.1:8795/'
const POLL_MS = 2000

const data = atom({ plugin: 'agents-room', key: 'data' } as const, null as PaneData | null)
const failure = atom({ plugin: 'agents-room', key: 'failure' } as const, '')
const isOpen = atom({ plugin: 'agents-room', key: 'isOpen' } as const, false)

const COLOR: Record<AgentRow['status'], string> = {
  waiting: '#f2c45a',
  working: '#5cc8f5',
  done: '#6fdcb0',
  quiet: '#7d8a99',
}

// Desktop Text paragraphs run left to right; an RTL isolate keeps Arabic lines in order.
const rtl = (s: string) => (/^[\s"«(]*[؀-ۿ]/.test(s) ? `⁧${s}⁩` : s)

let lastBody = ''

async function poll($: EngineInterface): Promise<void> {
  if (!(await read($, isOpen))) return
  try {
    const res = await $.http.fetch(PANE_URL)
    if (!res.ok) throw new Error(`board answered ${res.status}`)
    if (res.text === lastBody) return
    lastBody = res.text
    const next = JSON.parse(res.text) as PaneData
    await update($, data, () => next)
    if (await read($, failure)) await update($, failure, () => '')
  } catch (err) {
    const msg = String((err as Error)?.message ?? err).slice(0, 160)
    if ((await read($, failure)) !== msg) await update($, failure, () => msg)
  }
}

async function show($: EngineInterface, focus: boolean): Promise<void> {
  const opened = await $.ui.open(focus ? { id: PANE, title: TITLE, focus: true } : { id: PANE, title: TITLE })
  await update($, isOpen, () => true)
  if (!opened.isPlaced && focus) $.ui.toast('الوكلاء: وسّع النافذة عشان تطلع اللوحة')
  await poll($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'agents-room', description: 'Show every Claude session as a live room of characters' })
    $.clock.every(POLL_MS, () => {
      void poll($)
    })
    void show($, false)
    return next(e)
  })

  on('command.run', { command: 'agents-room' }, async $ => {
    await show($, true)
    return { text: 'Agents room opened.' }
  })

  on('ui.close', async ($, e, next) => {
    if (e.id === PANE) await update($, isOpen, () => false)
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const Svg = 'Svg' in els ? els.Svg : undefined
    const room = await read($, data)
    const broken = await read($, failure)

    const openLink = (link: string) => () => {
      if (link) void $.process.run(['open', link])
    }

    if (!room) {
      return (
        <Box flexDirection="column" gap={1}>
          <Text>{rtl(broken ? 'شاشة الوكلاء واقفة: الخادم ما رد.' : 'يجهز الغرفة…')}</Text>
          {broken ? <Text dimColor>{broken}</Text> : null}
        </Box>
      )
    }

    const c = room.counts
    const groups: Array<[string, AgentRow[]]> = [
      ['ينطرونك', room.agents.filter(a => a.status === 'waiting')],
      ['شغالين الحين', room.agents.filter(a => a.status === 'working')],
      ['خلصوا وهادين', room.agents.filter(a => a.status === 'done' || a.status === 'quiet')],
    ]

    return (
      <Box flexDirection="column" gap={1}>
        {broken ? <Text color="#f2c45a">{rtl(`الاتصال واقف، اللي تشوفه قديم (${broken})`)}</Text> : null}
        {Svg ? (
          <Svg
            key="room"
            source={room.svg}
            alt={`${c.waiting} ينطرونك، ${c.working} شغالين، ${c.done + c.quiet} خلصوا او هادين`}
            width={ROOM_PX}
            height={Math.round((ROOM_PX * (room.svgH || 300)) / (room.svgW || 440))}
            isInteractive
          />
        ) : null}
        <Text bold>{rtl(`${c.waiting} ينطرونك · ${c.working} شغالين · ${c.done + c.quiet} خلصوا او هادين`)}</Text>
        {groups
          .filter(([, rows]) => rows.length > 0)
          .map(([head, rows]) => (
            <Box key={`g-${head}`} flexDirection="column">
              <Text bold color={COLOR[rows[0]?.status ?? 'quiet']}>{rtl(head)}</Text>
              {rows.map(a => (
                <Box key={`a-${a.id}`} flexDirection="column" paddingY={0}>
                  <Box flexDirection="row" gap={1} alignItems="center">
                    {Svg && a.icon ? <Svg key={`icon-${a.id}`} source={a.icon} alt={a.word} width={42} height={40} /> : null}
                    <Button
                      key={`open-${a.id}`}
                      label={a.short}
                      plain
                      dimColor={a.status === 'quiet'}
                      onPress={openLink(a.link)}
                    />
                    <Text color={COLOR[a.status]}>{rtl(`${a.word} · ${a.ago}`)}</Text>
                  </Box>
                  {a.line ? (
                    <Text dimColor wrap="truncate-end">
                      {rtl(a.line)}
                    </Text>
                  ) : null}
                </Box>
              ))}
            </Box>
          ))}
        <Box flexDirection="row" gap={1}>
          <Button key="full" label="افتح الشاشة الكاملة" onPress={openLink(BOARD_URL)} />
        </Box>
      </Box>
    )
  })
}
