<template>
  <div class="message-container message-assistant">
    <div class="message-bubble">
      <div class="d-flex align-center">
        <span class="thinking-text mr-2">Thinking</span>
        <span class="dots">
          <span class="dot">.</span>
          <span class="dot">.</span>
          <span class="dot">.</span>
        </span>
      </div>
      <div v-if="showTimeout" class="timeout-message mt-1">
        This is taking longer than usual...
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      showTimeout: false,
      timeoutTimer: null,
    };
  },
  mounted() {
    this.timeoutTimer = setTimeout(() => {
      this.showTimeout = true;
    }, 30000);
  },
  beforeDestroy() {
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
    }
  },
};
</script>

<style scoped>
.message-container {
  display: flex;
  margin-bottom: 12px;
  max-width: 85%;
}

.message-assistant {
  justify-content: flex-start;
  margin-left: 8px;
  margin-right: auto;
}

.message-bubble {
  padding: 10px 15px;
  border-radius: 18px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  word-wrap: break-word;
  position: relative;
  background-color: #f1f1f1;
  color: #333;
  border-bottom-left-radius: 4px;
  display: inline-block;
}

.thinking-text {
  font-weight: 500;
  font-size: 1em;
  line-height: 1.4;
}

.dots {
  display: inline-flex;
}

.dot {
  opacity: 0;
  animation: dotFade 1.4s infinite;
  margin-left: 1px;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dotFade {
  0%,
  100% {
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
}

.timeout-message {
  font-size: 0.8em;
  opacity: 0.8;
  animation: fadeIn 0.5s ease-in;
  color: #555;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 0.8;
  }
}
</style>
