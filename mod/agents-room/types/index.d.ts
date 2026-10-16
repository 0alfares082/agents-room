export type AgentRow = {
  id: string
  title: string
  short: string
  status: 'waiting' | 'working' | 'done' | 'quiet'
  icon: string
  word: string
  project: string
  link: string
  line: string
  ago: string
}

export type PaneData = {
  generatedAt: string
  counts: { waiting: number; working: number; done: number; quiet: number }
  svg: string
  svgSig: string
  svgW: number
  svgH: number
  agents: AgentRow[]
}

declare module 'claude-code' {
  interface PluginState {
    'agents-room': { data: PaneData | null; failure: string; isOpen: boolean }
  }
}
