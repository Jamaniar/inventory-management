<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" role="dialog" aria-modal="true" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" :aria-label="t('common.close')" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Item summary -->
            <div class="item-summary">
              <div class="item-name">{{ translateProductName(backlogItem.item_name) }}</div>
              <div class="item-meta">
                <span class="item-sku">{{ t('purchaseOrder.sku') }}: {{ backlogItem.item_sku }}</span>
                <span class="item-shortage">{{ t('purchaseOrder.shortage') }}: {{ shortage }} {{ t('purchaseOrder.units') }}</span>
              </div>
            </div>

            <!-- View mode -->
            <template v-if="mode === 'view'">
              <div v-if="loading" class="state-message">{{ t('common.loading') }}</div>
              <div v-else-if="loadError" class="form-error">{{ loadError }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div v-for="field in viewFields" :key="field.key" class="info-item" :class="{ wide: field.wide }">
                  <div class="info-label">{{ field.label }}</div>
                  <div class="info-value" :class="field.cls">{{ field.value }}</div>
                </div>
              </div>
            </template>

            <!-- Create mode -->
            <form v-else id="po-form" class="po-form" novalidate @submit.prevent="submit">
              <div class="form-group">
                <label for="po-supplier">{{ t('purchaseOrder.supplier') }}</label>
                <input id="po-supplier" v-model="form.supplier_name" type="text" class="form-input" :disabled="saving" />
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                  <input id="po-quantity" v-model="form.quantity" type="number" min="1" step="1" class="form-input" :disabled="saving" />
                </div>
                <div class="form-group">
                  <label for="po-cost">{{ t('purchaseOrder.unitCost') }}</label>
                  <input id="po-cost" v-model="form.unit_cost" type="number" min="0" step="0.01" class="form-input" :disabled="saving" />
                </div>
              </div>
              <div class="form-group">
                <label for="po-date">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input id="po-date" v-model="form.expected_delivery_date" type="date" class="form-input" :disabled="saving" />
              </div>
              <div class="form-group">
                <label for="po-notes">{{ t('purchaseOrder.notes') }}</label>
                <textarea id="po-notes" v-model="form.notes" rows="3" class="form-input" :disabled="saving"></textarea>
              </div>
              <div v-if="formError" class="form-error" role="alert">{{ formError }}</div>
            </form>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="close">{{ t('common.close') }}</button>
            <button v-if="mode !== 'view'" type="submit" form="po-form" class="btn-primary" :disabled="saving">
              {{ saving ? t('purchaseOrder.saving') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const { t, translateProductName, currentLocale } = useI18n()

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: { type: String, default: 'create' }
})

const emit = defineEmits(['close', 'po-created'])

const form = reactive({
  supplier_name: '',
  quantity: 1,
  unit_cost: 0,
  expected_delivery_date: '',
  notes: ''
})
const saving = ref(false)
const formError = ref(null)
const loading = ref(false)
const loadError = ref(null)
const purchaseOrder = ref(null)

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return Math.max(0, props.backlogItem.quantity_needed - props.backlogItem.quantity_available)
})

const close = () => emit('close')

// Returns a localized date, or the raw string if it cannot be parsed
const formatDate = (value) => {
  if (!value) return t('purchaseOrder.notAvailable')
  // Date-only strings (YYYY-MM-DD) are parsed as UTC by Date, which shifts the day
  // in negative-offset timezones; parse them as local dates instead.
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value))
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  if (isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
    year: 'numeric', month: 'long', day: 'numeric'
  })
}

// Unit cost is stored in USD by the API, so it is always shown as USD (no locale conversion)
const formatUsd = (n) => `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const viewFields = computed(() => {
  const po = purchaseOrder.value
  if (!po) return []
  const total = Number(po.quantity) * Number(po.unit_cost)
  return [
    { key: 'id', label: t('purchaseOrder.poNumber'), value: po.id, cls: 'mono' },
    { key: 'status', label: t('purchaseOrder.status'), value: po.status },
    { key: 'supplier', label: t('purchaseOrder.supplier'), value: po.supplier_name },
    { key: 'quantity', label: t('purchaseOrder.quantity'), value: `${po.quantity} ${t('purchaseOrder.units')}` },
    { key: 'unit', label: t('purchaseOrder.unitCost'), value: formatUsd(po.unit_cost) },
    { key: 'total', label: t('purchaseOrder.totalCost'), value: isNaN(total) ? t('purchaseOrder.notAvailable') : formatUsd(total) },
    { key: 'delivery', label: t('purchaseOrder.expectedDelivery'), value: formatDate(po.expected_delivery_date) },
    { key: 'created', label: t('purchaseOrder.createdDate'), value: formatDate(po.created_date) },
    { key: 'notes', label: t('purchaseOrder.notes'), value: po.notes || t('purchaseOrder.noNotes'), wide: true }
  ]
})

const resetState = () => {
  form.supplier_name = ''
  form.quantity = shortage.value > 0 ? shortage.value : 1
  form.unit_cost = 0
  form.expected_delivery_date = ''
  form.notes = ''
  saving.value = false
  formError.value = null
  loading.value = false
  loadError.value = null
  purchaseOrder.value = null
}

const errorDetail = (err, fallback) => {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return detail.map(d => d.msg).join('; ')
  return fallback
}

const loadPO = async () => {
  loading.value = true
  try {
    const result = await api.getPurchaseOrderByBacklogItem(props.backlogItem.id)
    // Ignore stale responses if the modal was closed or switched meanwhile
    if (!props.isOpen) return
    purchaseOrder.value = result
  } catch (err) {
    if (!props.isOpen) return
    loadError.value = errorDetail(err, t('purchaseOrder.loadFailed'))
  } finally {
    loading.value = false
  }
}

const submit = async () => {
  if (saving.value) return
  formError.value = null

  const quantity = Number(form.quantity)
  const unitCost = Number(form.unit_cost)
  const date = new Date(form.expected_delivery_date)

  if (!form.supplier_name.trim()) { formError.value = t('purchaseOrder.errSupplier'); return }
  if (!Number.isInteger(quantity) || quantity <= 0) { formError.value = t('purchaseOrder.errQuantity'); return }
  if (form.unit_cost === '' || isNaN(unitCost) || unitCost < 0) { formError.value = t('purchaseOrder.errUnitCost'); return }
  if (!form.expected_delivery_date || isNaN(date.getTime())) { formError.value = t('purchaseOrder.errDate'); return }

  saving.value = true
  try {
    const created = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.supplier_name.trim(),
      quantity,
      unit_cost: unitCost,
      expected_delivery_date: form.expected_delivery_date,
      notes: form.notes.trim()
    })
    emit('po-created', created)
    close()
  } catch (err) {
    formError.value = errorDetail(err, t('purchaseOrder.createFailed'))
  } finally {
    saving.value = false
  }
}

// Reset every time the modal opens (or is reused for a different item/mode)
watch(
  () => [props.isOpen, props.backlogItem?.id, props.mode],
  ([open]) => {
    if (!open || !props.backlogItem) return
    resetState()
    if (props.mode === 'view') loadPO()
  },
  { immediate: true }
)

const onKeydown = (e) => {
  if (e.key === 'Escape' && props.isOpen) close()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: var(--surface);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: var(--surface-sunken);
  color: var(--text);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.item-summary {
  padding: 1rem 1.25rem;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 1.5rem;
}

.item-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.5rem;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.item-sku {
  font-family: 'Monaco', 'Courier New', monospace;
}

.item-shortage {
  color: var(--danger-fg);
  font-weight: 600;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-group label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.form-input {
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  font-size: 0.938rem;
  font-family: inherit;
  color: var(--text);
  background: var(--surface);
  resize: vertical;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.form-input:disabled {
  background: var(--surface-sunken);
  cursor: not-allowed;
}

.form-error {
  padding: 0.75rem 1rem;
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-radius: 8px;
  color: var(--danger-fg);
  font-size: 0.875rem;
}

.state-message {
  padding: 1.5rem;
  text-align: center;
  color: var(--text-secondary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  min-width: 0;
}

.info-item.wide {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.info-value {
  font-size: 0.938rem;
  color: var(--text);
  font-weight: 500;
  overflow-wrap: anywhere;
}

.info-value.mono {
  font-family: 'Monaco', 'Courier New', monospace;
  color: var(--accent);
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  color: var(--text-body);
}

.btn-secondary:hover {
  background: var(--border);
  border-color: var(--border-strong);
}

.btn-primary {
  background: var(--accent);
  border: 1px solid var(--accent);
  color: var(--on-accent);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
