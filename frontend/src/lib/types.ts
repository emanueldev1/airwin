export type DeviceKind = "Apple TV" | "HomePod" | "Mac" | "TV con AirPlay" | "Altavoz AirPlay"

export interface Device {
  id: string
  name: string
  address: string
  model: string
  kind: DeviceKind
  protocols: string[]
  needsPairing: string[]
  paired: string[]
  pairable: { id: string; label: string }[]
  canAudio: boolean
  canVideo: boolean
  canRemote: boolean
}

export interface Settings {
  receiver_name: string
  receiver_fullscreen: boolean
  receiver_pin: string
  receiver_resolution: string
  receiver_fps: number
  receiver_audio_only: boolean
  uxplay_path: string
  ffmpeg_path: string
  media_port: number
  cast_fps: number
  cast_encoder: string
  cast_bitrate: string
  theme?: "dark" | "light" | "system"
}

export interface AppState {
  app: string
  version: string
  platform: string
  scanning: boolean
  devices: Device[]
  audio: { active: string[]; source: string | null }
  video: { active: string[]; screen: string[] }
  receiver: { running: boolean }
  settings: Settings
  deps: { uxplay: string | null; ffmpeg: string | null; bonjour: string | null }
  installing: string[]
  encoders: Record<string, string>
  canPickFiles: boolean
}

export interface LogLine {
  level: string
  time: number
  message: string
}

export interface Monitor {
  name: string
  rect: [number, number, number, number]
  primary: boolean
}

export interface NowPlaying {
  title: string | null
  artist: string | null
  album: string | null
  state: string | null
  position: number | null
  total: number | null
  app: string | null
}
