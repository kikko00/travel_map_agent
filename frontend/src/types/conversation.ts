import type { TripFormData, TripPlan } from './index'

export interface SearchSource {
  title: string
  url: string
  snippet: string
  retrieved_at?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources: SearchSource[]
  changed_days?: number[]
}

export interface ConversationSummary {
  id: string
  title: string
  version: number
  updated_at: string
}

export interface Conversation extends ConversationSummary {
  created_at: string
  trip_request: TripFormData
  plan: TripPlan
  messages: ChatMessage[]
  constraints: string[]
}
