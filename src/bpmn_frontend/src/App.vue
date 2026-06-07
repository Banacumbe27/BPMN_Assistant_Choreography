<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { RouterView } from 'vue-router';
import { isHostedVersion } from './config';
import { REMOTE_SERVICES, warmupServices } from './utils/serviceWarmup';

const buildInitialStatus = (service, ready = !isHostedVersion) => ({
  id: service.id,
  label: service.label,
  url: service.url,
  attempts: 0,
  hasResponded: ready,
  ok: ready,
  statusCode: ready ? 200 : null,
  error: null,
  completed: ready,
  timedOut: false,
});

const initializeStatuses = () =>
  REMOTE_SERVICES.reduce((acc, service) => {
    acc[service.id] = buildInitialStatus(service);
    return acc;
  }, {});

const serviceStatuses = reactive(initializeStatuses());
const warmupTimedOut = ref(false);
const isBlockingWarmup = ref(isHostedVersion);
const isWarmupRunning = ref(isHostedVersion);

const serviceStatusList = computed(() => Object.values(serviceStatuses));
const allServicesResponded = computed(() =>
  serviceStatusList.value.every((status) => status.hasResponded)
);

const overlayVisible = computed(
  () => isHostedVersion && isBlockingWarmup.value && !allServicesResponded.value
);

const warmupTitle = computed(() =>
  warmupTimedOut.value
    ? 'Timed out while waking services'
    : 'Waking up services'
);

const refreshDisabled = computed(() => isWarmupRunning.value);
const refreshLabel = computed(() =>
  isWarmupRunning.value ? 'Refreshing...' : 'Refresh'
);

const getStatusState = (status) => {
  if (status.ok) {
    return 'ready';
  }
  if (status.hasResponded) {
    return 'responded';
  }
  return 'waiting';
};

const getStatusText = (status) => {
  const state = getStatusState(status);
  if (state === 'ready') {
    return 'Ready';
  }
  if (state === 'responded') {
    return 'Responded';
  }
  return 'Waiting';
};

const getStatusClass = (status) => `status-${getStatusState(status)}`;

const resetStatusesForWarmup = () => {
  if (!isHostedVersion) {
    return;
  }
  REMOTE_SERVICES.forEach((service) => {
    serviceStatuses[service.id] = buildInitialStatus(service, false);
  });
};

const handleStatusUpdate = (statusUpdate) => {
  serviceStatuses[statusUpdate.id] = {
    ...serviceStatuses[statusUpdate.id],
    ...statusUpdate,
  };
};

const runWarmup = async ({ block } = { block: false }) => {
  if (!isHostedVersion) {
    return;
  }

  warmupTimedOut.value = false;
  if (block) {
    isBlockingWarmup.value = true;
  }

  isWarmupRunning.value = true;
  resetStatusesForWarmup();

  const { timedOut } = await warmupServices({
    onStatus: handleStatusUpdate,
  });

  warmupTimedOut.value = timedOut;
  isWarmupRunning.value = false;

  if (block) {
    isBlockingWarmup.value = false;
  }
};

const handleRefresh = () => {
  if (refreshDisabled.value || !isHostedVersion) {
    return;
  }
  runWarmup({ block: false });
};

onMounted(() => {
  if (isHostedVersion) {
    runWarmup({ block: true });
  }
});
</script>

<template>
  <div class="app-shell">
    <RouterView />
    <div v-if="overlayVisible" class="service-warmup-overlay">
      <div class="service-warmup-card">
        <div class="service-warmup-header">
          <div class="warmup-title">{{ warmupTitle }}</div>
          <div class="warmup-subtitle">
            Preparing hosted services (can take up to 60 seconds)
          </div>
        </div>
        <div class="service-status-list">
          <div
            v-for="status in serviceStatusList"
            :key="status.id"
            class="service-status-row"
          >
            <div class="status-details">
              <span class="status-dot" :class="getStatusClass(status)" />
              <div class="service-status-label">{{ status.label }}</div>
            </div>
            <div class="service-status-state" :class="getStatusClass(status)">
              {{ getStatusText(status) }}
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="isHostedVersion" class="service-status-panel">
      <div class="panel-header">
        <span class="panel-title">Service status</span>
        <button
          class="refresh-button"
          :disabled="refreshDisabled"
          @click="handleRefresh"
        >
          {{ refreshLabel }}
        </button>
      </div>
      <div class="service-status-list">
        <div
          v-for="status in serviceStatusList"
          :key="status.id"
          class="service-status-row"
        >
          <div class="status-details">
            <span class="status-dot" :class="getStatusClass(status)" />
            <span class="service-status-label">{{ status.label }}</span>
          </div>
          <div class="service-status-state" :class="getStatusClass(status)">
            {{ getStatusText(status) }}
          </div>
        </div>
      </div>
      <div v-if="warmupTimedOut" class="panel-note">
        Latest refresh hit the 90s timeout.
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
}

.service-warmup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 20, 20, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.service-warmup-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px 24px;
  width: min(420px, 86vw);
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.18);
}

.service-warmup-header {
  margin-bottom: 12px;
}

.warmup-title {
  font-weight: 600;
  font-size: 1.05rem;
}

.warmup-subtitle {
  font-size: 0.85rem;
  color: #606060;
}

.service-status-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.service-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.status-details {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #0d47a1;
}

.service-status-state {
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #0d47a1;
}

.service-status-state.status-responded {
  color: #ff6f00;
}

.service-status-state.status-ready {
  color: #1b5e20;
}

.status-dot.status-responded {
  background-color: #ff6f00;
}

.status-dot.status-ready {
  background-color: #1b5e20;
}

.service-status-panel {
  position: fixed;
  bottom: 16px;
  right: 16px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  padding: 14px 16px;
  width: 240px;
  z-index: 2000;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.panel-title {
  font-weight: 600;
  font-size: 0.95rem;
}

.refresh-button {
  border: none;
  background: #0d47a1;
  color: #ffffff;
  border-radius: 16px;
  padding: 4px 10px;
  font-size: 0.8rem;
  cursor: pointer;
}

.refresh-button:disabled {
  background: #9ea7ad;
  cursor: not-allowed;
}

.panel-note {
  margin-top: 8px;
  font-size: 0.75rem;
  color: #b44b00;
}
</style>
