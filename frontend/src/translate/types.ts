export interface ProviderConfig {
  endpoint: string
  model: string
  deepl_plan: 'free' | 'pro'
  api_version: 'v1' | 'v1beta'
  response_mode: 'prompt_json' | 'json_object' | 'json_schema'
  max_chars: number
  max_output_tokens: number
}
export interface Policy {
  id: string
  name: string
  target_language: string
  fields: string[]
  kinds: string[]
  mode: 'source_only' | 'translate'
  fallback_languages: string[]
  chinese_conversion: boolean
  prefer_official: boolean
}
export interface TranslationConfig {
  version: number
  enabled: boolean
  global_hook: boolean
  active_provider: string
  provider_configs: Record<string, ProviderConfig>
  policies: Policy[]
  default_policy: string
  timeout: number
  concurrency: number
  source_hours: number
  missing_days: number
  cache_days: number
  history_days: number
}
export interface Settings {
  revision: string
  config: TranslationConfig
  providers: Record<string, string>
  fields: Record<string, string>
  secret_set: Record<string, boolean>
  hook_conflicts: string[]
  cache: Record<string, number>
  busy: boolean
}
export interface Call {
  id: number
  created: number
  provider: string
  status: string
  summary: string
}
export interface Page {
  items: Call[]
  total: number
  page: number
  page_size: number
}
export interface FieldResult {
  status: string
  before?: string
  text?: string
  source_text?: string
  source_language?: string
  origin?: string
  message?: string
  error_code?: string
  cache_hit?: boolean
}
export interface PreviewResult {
  fields: Record<string, FieldResult>
  pending_fields: string[]
  changed_fields: string[]
  nfo: string
  record_id: number
}
export interface PreviewInput {
  identity: {
    kind: string
    tmdb_id: number | null
    season: number | null
    episode: number | null
    episode_group: string | null
    title: string
    original_language: string | null
  }
  nfo: string
  policy_id: string
  overwrite: boolean
  force: boolean
}
