<template>
  <a-card title="💬 继续规划与联网查询" class="chat-card">
    <a-space wrap style="margin-bottom: 16px">
      <a-select :value="session?.id" placeholder="恢复历史会话" style="width: 280px"
        :disabled="busy || disabled" @change="selectHistory">
        <a-select-option v-for="item in history" :key="item.id" :value="item.id">{{ item.title }}</a-select-option>
      </a-select>
      <a-button :disabled="busy || disabled" @click="loadHistory">刷新历史</a-button>
      <a-button v-if="!session && canAdopt" :disabled="disabled" :loading="busy" @click="$emit('adopt')">将当前行程保存为会话</a-button>
    </a-space>
    <p v-if="session">行程版本 {{ session.version }} · 修改会同步保存到后端</p>
    <div class="chat-messages" aria-live="polite">
      <div v-for="(item, index) in session?.messages || []" :key="index" :class="['chat-message', item.role]">
        <strong>{{ item.role === 'user' ? '你' : '旅行助手' }}</strong>
        <p>{{ item.content }}</p>
        <small v-if="item.changed_days?.length">已调整：{{ item.changed_days.map(d => `第${d + 1}天`).join('、') }}</small>
        <ul v-if="item.sources.length">
          <li v-for="source in item.sources" :key="source.url">
            <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title || '参考来源' }}</a>
            <small v-if="source.retrieved_at"> · 检索于 {{ new Date(source.retrieved_at).toLocaleString() }}</small>
          </li>
        </ul>
      </div>
    </div>
    <a-textarea v-model:value="input" :rows="3" :maxlength="4000" :disabled="busy || disabled || !session"
      placeholder="例如：第二天改为博物馆；西湖游船几点开放，需要预约吗？" />
    <a-button type="primary" style="margin-top: 12px" :loading="busy" :disabled="disabled || !session || !input.trim()" @click="send">发送</a-button>
    <small class="hint">联网信息提供来源供核实；不代为预约或购票。编辑行程时请先保存或取消编辑。</small>
  </a-card>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { listConversations } from '@/services/api'
import type { Conversation, ConversationSummary } from '@/types/conversation'

const props = defineProps<{ session: Conversation | null; busy: boolean; disabled: boolean; canAdopt: boolean }>()
const emit = defineEmits<{ send: [content: string]; select: [id: string]; adopt: [] }>()
const input = ref('')
const history = ref<ConversationSummary[]>([])
async function loadHistory() {
  try { history.value = await listConversations() }
  catch { message.warning('无法加载历史会话，请检查后端连接。') }
}
function selectHistory(value: unknown) { emit('select', String(value)) }
function send() { emit('send', input.value.trim()) }
watch(() => props.session, session => {
  const lastUser = session?.messages[session.messages.length - 2]
  if (lastUser?.role === 'user' && lastUser.content === input.value.trim()) input.value = ''
})
onMounted(loadHistory)
</script>

<style scoped>
.chat-card { margin: 24px 0; }
.chat-messages { max-height: 420px; overflow-y: auto; margin-bottom: 16px; }
.chat-message { padding: 12px 16px; margin: 10px 0; background: #f5f7fb; border-radius: 12px; }
.chat-message.user { background: #e6f4ff; }
.chat-message p { white-space: pre-wrap; margin: 6px 0; overflow-wrap: anywhere; }
.hint { display: block; color: #777; margin-top: 12px; }
</style>
