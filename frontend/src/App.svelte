<script>
  import { onMount } from 'svelte'
  import { fetchJSON } from './lib/api.js'
  import MechanicDashboard from './views/MechanicDashboard.svelte'
  import MarketOpportunity from './views/MarketOpportunity.svelte'

  let activeTab = 'dashboard'
  let snapshotDate = ''

  const tabs = [
    { id: 'dashboard', label: 'Mechanics Explorer' },
    { id: 'opportunity', label: 'Market Opportunities' },
  ]

  onMount(async () => {
    try {
      const meta = await fetchJSON('/api/meta')
      if (meta.snapshot_date) {
        const d = new Date(meta.snapshot_date + 'T00:00:00')
        snapshotDate = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
      }
    } catch (e) {}
  })
</script>

<header>
  <h1>BGG Data Explorer</h1>
  <a href="https://boardgamegeek.com" target="_blank" rel="noopener">
    <img src="{import.meta.env.BASE_URL}bgg-logo.png" alt="Powered by BoardGameGeek" class="bgg-logo" />
  </a>
</header>

<div class="tabs">
  {#each tabs as tab}
    <button
      class:active={activeTab === tab.id}
      on:click={() => activeTab = tab.id}
    >
      {tab.label}
    </button>
  {/each}
</div>

{#if activeTab === 'dashboard'}
  <MechanicDashboard />
{:else if activeTab === 'opportunity'}
  <MarketOpportunity />
{/if}

<footer>
  {#if snapshotDate}
    <div class="data-notice">Data based on a BGG snapshot from {snapshotDate} — not live data.</div>
  {/if}
  Created by <a href="https://solojulian.dev" target="_blank" rel="noopener">Julian</a> &amp; Claude · <a href="https://github.com/julianss/bgg-data-explorer" target="_blank" rel="noopener">GitHub</a>
</footer>
