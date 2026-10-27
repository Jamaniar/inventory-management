<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error && !recommendations" class="error">{{ error }}</div>
    <div v-else-if="recommendations">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
          <strong class="budget-readout">{{ formatCurrency(budget, currentCurrency) }}</strong>
        </div>
        <div class="budget-control">
          <input
            type="range"
            class="budget-slider"
            min="0"
            :max="maxBudget"
            step="500"
            v-model.number="budget"
            :aria-label="t('restocking.budgetLabel')"
            @input="onBudgetInput"
          />
          <div class="budget-scale">
            <span>{{ formatCurrency(0, currentCurrency) }}</span>
            <span>{{ formatCurrency(maxBudget, currentCurrency) }}</span>
          </div>
        </div>
      </div>

      <div v-if="error" class="error">{{ error }}</div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ recommendations.items.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.totalUnits') }}</div>
          <div class="stat-value">{{ recommendations.total_units.toLocaleString() }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ formatCurrency(recommendations.total_cost, currentCurrency) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ formatCurrency(recommendations.remaining_budget, currentCurrency) }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <button
            class="place-order-btn"
            :disabled="recommendations.items.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="submitError" class="error">{{ submitError }}</div>
        <div v-if="placedOrder" class="order-confirmation">
          <strong>{{ t('restocking.orderPlaced') }}</strong>
          <span>{{ t('restocking.orderNumber') }}: {{ placedOrder.order_number }}</span>
          <span>{{ t('restocking.total') }}: {{ formatCurrency(placedOrder.total_cost, currentCurrency) }}</span>
          <span>{{ t('restocking.expectedDelivery') }}: {{ formatDate(placedOrder.expected_delivery) }}</span>
          <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
        </div>

        <div v-if="recommendations.items.length === 0" class="empty-state">
          {{ t('restocking.empty') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations.items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>
                  <span :class="['badge', getTrendClass(item.trend)]">{{ t(`trends.${item.trend}`) }}</span>
                </td>
                <td>{{ item.quantity.toLocaleString() }}</td>
                <td>{{ formatCurrencyWithDecimals(item.unit_cost, currentCurrency, 2) }}</td>
                <td><strong>{{ formatCurrencyWithDecimals(item.line_total, currentCurrency, 2) }}</strong></td>
                <td>{{ t('restocking.days', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const submitError = ref(null)
    const placedOrder = ref(null)
    const recommendations = ref(null)
    const budget = ref(0)
    const maxBudget = ref(0)

    let debounceTimer = null
    // Ignore responses from superseded requests (slider moves faster than the API)
    let requestSeq = 0

    const fetchRecommendations = async () => {
      const seq = ++requestSeq
      try {
        const data = await api.getRestockRecommendations(budget.value)
        if (seq !== requestSeq) return
        recommendations.value = data
        error.value = null
      } catch (err) {
        if (seq !== requestSeq) return
        error.value = t('restocking.loadError') + err.message
      }
    }

    // The max budget is only known from the API, so an initial call is needed
    // before the slider can be rendered; then re-fetch at ~25% of max.
    const loadInitial = async () => {
      try {
        loading.value = true
        const initial = await api.getRestockRecommendations(0)
        // Round up to a whole slider step; a range input can't land on a max that isn't
        // a multiple of step, which would make the full restock set unreachable
        maxBudget.value = Math.ceil(initial.max_budget / 500) * 500
        budget.value = Math.round((initial.max_budget * 0.25) / 500) * 500
        recommendations.value = initial
        await fetchRecommendations()
      } catch (err) {
        error.value = t('restocking.loadError') + err.message
      } finally {
        loading.value = false
      }
    }

    // Debounce so dragging the slider doesn't fire a request per step
    const onBudgetInput = () => {
      placedOrder.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(fetchRecommendations, 250)
    }

    const placeOrder = async () => {
      if (!recommendations.value || recommendations.value.items.length === 0) return
      submitting.value = true
      submitError.value = null
      placedOrder.value = null
      try {
        placedOrder.value = await api.createRestockOrder({
          items: recommendations.value.items.map(i => ({ sku: i.sku, quantity: i.quantity }))
        })
      } catch (err) {
        const detail = err.response?.data?.detail
        submitError.value = t('restocking.submitError') + (typeof detail === 'string' ? detail : err.message)
      } finally {
        submitting.value = false
      }
    }

    const getTrendClass = (trend) => (trend === 'increasing' ? 'success' : 'info')

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return '-'
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    onMounted(loadInitial)
    onUnmounted(() => clearTimeout(debounceTimer))

    return {
      t,
      currentCurrency,
      loading,
      error,
      submitting,
      submitError,
      placedOrder,
      recommendations,
      budget,
      maxBudget,
      onBudgetInput,
      placeOrder,
      getTrendClass,
      formatDate,
      formatCurrency,
      formatCurrencyWithDecimals,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-readout {
  font-size: 1.25rem;
  color: var(--text);
}

.budget-control {
  padding: 0.5rem 0;
}

.budget-slider {
  width: 100%;
  accent-color: var(--accent);
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: var(--text-secondary);
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  background: var(--text);
  color: var(--on-accent);
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: var(--text-body);
}

.place-order-btn:disabled {
  background: var(--border-strong);
  cursor: not-allowed;
}

.order-confirmation {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  background: var(--success-soft);
  border: 1px solid var(--success-border);
  border-radius: 8px;
  color: var(--text);
  font-size: 0.875rem;
}

.order-confirmation a {
  color: var(--accent);
  font-weight: 500;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary);
}
</style>
