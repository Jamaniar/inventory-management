<template>
  <div class="app">
    <header class="top-nav">
      <div class="nav-container">
        <div class="logo">
          <h1>{{ t('nav.companyName') }}</h1>
          <span class="subtitle">{{ t('nav.subtitle') }}</span>
        </div>
        <nav class="nav-tabs">
          <router-link to="/" :class="{ active: $route.path === '/' }">
            {{ t('nav.overview') }}
          </router-link>
          <router-link to="/inventory" :class="{ active: $route.path === '/inventory' }">
            {{ t('nav.inventory') }}
          </router-link>
          <router-link to="/orders" :class="{ active: $route.path === '/orders' }">
            {{ t('nav.orders') }}
          </router-link>
          <router-link to="/spending" :class="{ active: $route.path === '/spending' }">
            {{ t('nav.finance') }}
          </router-link>
          <router-link to="/demand" :class="{ active: $route.path === '/demand' }">
            {{ t('nav.demandForecast') }}
          </router-link>
          <router-link to="/restocking" :class="{ active: $route.path === '/restocking' }">
            {{ t('nav.restocking') }}
          </router-link>
          <router-link to="/reports" :class="{ active: $route.path === '/reports' }">
            Reports
          </router-link>
        </nav>
        <LanguageSwitcher />
        <ProfileMenu
          @show-profile-details="showProfileDetails = true"
          @show-tasks="showTasks = true"
        />
      </div>
    </header>
    <FilterBar />
    <main class="main-content">
      <router-view />
    </main>

    <ProfileDetailsModal
      :is-open="showProfileDetails"
      @close="showProfileDetails = false"
    />

    <TasksModal
      :is-open="showTasks"
      :tasks="tasks"
      @close="showTasks = false"
      @add-task="addTask"
      @delete-task="deleteTask"
      @toggle-task="toggleTask"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { api } from './api'
import { useAuth } from './composables/useAuth'
import { useI18n } from './composables/useI18n'
import FilterBar from './components/FilterBar.vue'
import ProfileMenu from './components/ProfileMenu.vue'
import ProfileDetailsModal from './components/ProfileDetailsModal.vue'
import TasksModal from './components/TasksModal.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

export default {
  name: 'App',
  components: {
    FilterBar,
    ProfileMenu,
    ProfileDetailsModal,
    TasksModal,
    LanguageSwitcher
  },
  setup() {
    const { currentUser } = useAuth()
    const { t } = useI18n()
    const showProfileDetails = ref(false)
    const showTasks = ref(false)
    const apiTasks = ref([])

    // Merge mock tasks from currentUser with API tasks
    const tasks = computed(() => {
      return [...currentUser.value.tasks, ...apiTasks.value]
    })

    const loadTasks = async () => {
      try {
        apiTasks.value = await api.getTasks()
      } catch (err) {
        console.error('Failed to load tasks:', err)
      }
    }

    const addTask = async (taskData) => {
      try {
        const newTask = await api.createTask(taskData)
        // Add new task to the beginning of the array
        apiTasks.value.unshift(newTask)
      } catch (err) {
        console.error('Failed to add task:', err)
      }
    }

    const deleteTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const isMockTask = currentUser.value.tasks.some(t => t.id === taskId)

        if (isMockTask) {
          // Remove from mock tasks
          const index = currentUser.value.tasks.findIndex(t => t.id === taskId)
          if (index !== -1) {
            currentUser.value.tasks.splice(index, 1)
          }
        } else {
          // Remove from API tasks
          await api.deleteTask(taskId)
          apiTasks.value = apiTasks.value.filter(t => t.id !== taskId)
        }
      } catch (err) {
        console.error('Failed to delete task:', err)
      }
    }

    const toggleTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const mockTask = currentUser.value.tasks.find(t => t.id === taskId)

        if (mockTask) {
          // Toggle mock task status
          mockTask.status = mockTask.status === 'pending' ? 'completed' : 'pending'
        } else {
          // Toggle API task
          const updatedTask = await api.toggleTask(taskId)
          const index = apiTasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            apiTasks.value[index] = updatedTask
          }
        }
      } catch (err) {
        console.error('Failed to toggle task:', err)
      }
    }

    onMounted(loadTasks)

    return {
      t,
      showProfileDetails,
      showTasks,
      tasks,
      addTask,
      deleteTask,
      toggleTask
    }
  }
}
</script>

<style>
:root {
  /* Surfaces */
  --bg: #f3f4f8;
  --surface: #ffffff;
  --surface-muted: #f8f9fc;
  --surface-sunken: #eef0f6;
  --ink: #0b1020;            /* top bar */
  --ink-border: #1f2740;
  --overlay: rgba(11, 16, 32, 0.55);

  /* Borders */
  --border: #e2e5ee;
  --border-strong: #c9cedc;

  /* Text. secondary #475569 = 7.6:1 on white, muted #64748b = 4.8:1 (both AA) */
  --text: #0b1020;
  --text-body: #1e293b;
  --text-secondary: #475569;
  --text-muted: #64748b;
  --text-faint: #94a3b8;     /* decorative only (icons, rules), never body text */
  --on-accent: #ffffff;

  /* Brand */
  --accent: #4f46e5;
  --accent-hover: #4338ca;
  --accent-bright: #818cf8;
  --accent-soft: #eef2ff;
  --accent-border: #c7d2fe;
  --accent-ring: rgba(79, 70, 229, 0.22);

  /* Status: solid (fills/charts), fg (text on soft bg, >= 5:1), soft (backgrounds) */
  --success: #10b981;
  --success-fg: #047857;
  --success-soft: #d1fae5;
  --success-border: #a7f3d0;
  --info: #0ea5e9;
  --info-fg: #075985;
  --info-soft: #e0f2fe;
  --info-border: #bae6fd;
  --warning: #f59e0b;
  --warning-fg: #92400e;
  --warning-soft: #fef3c7;
  --warning-border: #fcd34d;
  --danger: #ef4444;
  --danger-fg: #b91c1c;
  --danger-soft: #fee2e2;
  --danger-border: #fecaca;

  /* Secondary chart series */
  --chart-2: #0891b2;

  /* Shape and depth */
  --radius-sm: 6px;
  --radius: 8px;
  --radius-lg: 12px;
  --shadow-sm: 0 1px 2px rgba(11, 16, 32, 0.06);
  --shadow-md: 0 1px 2px rgba(11, 16, 32, 0.05), 0 4px 12px rgba(11, 16, 32, 0.07);
  --shadow-lg: 0 4px 6px rgba(11, 16, 32, 0.05), 0 24px 56px rgba(11, 16, 32, 0.22);

  /* Spacing scale */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --space-6: 2rem;

  /* Type */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --nav-height: 64px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-sans);
  font-feature-settings: 'cv11', 'ss01';
  font-variant-numeric: tabular-nums;
  background: var(--bg);
  color: var(--text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

button, input, select, textarea {
  font-family: inherit;
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* Top bar */
.top-nav {
  background: var(--ink);
  border-bottom: 1px solid var(--ink-border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-container {
  max-width: 1600px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  padding: 0 var(--space-6);
  height: var(--nav-height);
}

.nav-container > .nav-tabs {
  margin-left: auto;
  margin-right: var(--space-4);
}

.nav-container > .language-switcher {
  margin-right: var(--space-3);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Brand mark drawn in CSS so no asset is needed */
.logo h1::before {
  content: '';
  display: inline-block;
  width: 0.75rem;
  height: 0.75rem;
  margin-right: 0.625rem;
  border-radius: 3px;
  background: linear-gradient(135deg, var(--accent-bright), var(--accent));
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.25);
}

.logo h1 {
  font-size: 1.125rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.subtitle {
  font-size: 0.75rem;
  color: #a5b0c8;
  font-weight: 500;
  padding-left: 0.75rem;
  border-left: 1px solid var(--ink-border);
  white-space: nowrap;
}

.nav-tabs {
  display: flex;
  gap: 0.125rem;
  height: 100%;
}

.nav-tabs a {
  display: flex;
  align-items: center;
  padding: 0 0.875rem;
  color: #b4bdd2;
  text-decoration: none;
  font-weight: 500;
  font-size: 0.875rem;
  transition: color 0.15s ease, background-color 0.15s ease;
  position: relative;
  white-space: nowrap;
}

.nav-tabs a:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
}

.nav-tabs a:focus-visible {
  outline-offset: -2px;
  outline-color: var(--accent-bright);
}

.nav-tabs a.active {
  color: #ffffff;
  font-weight: 600;
}

.nav-tabs a.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0.875rem;
  right: 0.875rem;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--accent-bright);
}

.main-content {
  flex: 1;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6) 3rem;
}

.page-header {
  margin-bottom: var(--space-5);
}

.page-header h2 {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--text);
  margin-bottom: 0.25rem;
  letter-spacing: -0.035em;
  line-height: 1.2;
}

.page-header p {
  color: var(--text-secondary);
  font-size: 0.938rem;
}

/* KPI cards: label above, bold number, status shown as a colored top edge */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  margin-bottom: var(--space-5);
}

.stat-card {
  background: var(--surface);
  padding: 1.125rem 1.25rem 1.25rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  border-top: 3px solid var(--border-strong);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-card.success { border-top-color: var(--success); }
.stat-card.info { border-top-color: var(--accent); }
.stat-card.warning { border-top-color: var(--warning); }
.stat-card.danger { border-top-color: var(--danger); }

.stat-label {
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.5rem;
}

.stat-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.stat-card.warning .stat-value { color: var(--warning-fg); }
.stat-card.success .stat-value { color: var(--success-fg); }
.stat-card.danger .stat-value { color: var(--danger-fg); }
.stat-card.info .stat-value { color: var(--accent); }

.card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  margin-bottom: 1.25rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.875rem;
  border-bottom: 1px solid var(--border);
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.015em;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: var(--surface-muted);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

th {
  text-align: left;
  padding: 0.625rem 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 0.688rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  white-space: nowrap;
}

td {
  padding: 0.75rem 0.875rem;
  border-top: 1px solid var(--surface-sunken);
  color: var(--text-body);
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}

tbody tr {
  transition: background-color 0.12s ease;
}

tbody tr:hover {
  background: var(--accent-soft);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.188rem 0.625rem;
  border-radius: 999px;
  font-size: 0.688rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  line-height: 1.4;
  white-space: nowrap;
}

.badge.success,
.badge.increasing {
  background: var(--success-soft);
  color: var(--success-fg);
}

.badge.warning,
.badge.medium {
  background: var(--warning-soft);
  color: var(--warning-fg);
}

.badge.danger,
.badge.decreasing,
.badge.high {
  background: var(--danger-soft);
  color: var(--danger-fg);
}

.badge.info,
.badge.low {
  background: var(--info-soft);
  color: var(--info-fg);
}

.badge.stable {
  background: var(--accent-soft);
  color: var(--accent-hover);
}

/* Shared button styles (opt-in via class) */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text-body);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.btn:hover:not(:disabled) {
  background: var(--surface-muted);
  border-color: var(--text-faint);
}

.btn.primary,
.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--on-accent);
}

.btn.primary:hover:not(:disabled),
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary);
  font-size: 0.938rem;
}

.error {
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-left: 4px solid var(--danger);
  color: var(--danger-fg);
  padding: 1rem;
  border-radius: var(--radius);
  margin: 1rem 0;
  font-size: 0.938rem;
}
</style>
