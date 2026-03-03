<script>
  import MechanicExplorer from './views/MechanicExplorer.svelte'
  import MarketOpportunity from './views/MarketOpportunity.svelte'
  import TrendDashboard from './views/TrendDashboard.svelte'

  let activeTab = 'trends'

  const tabs = [
    { id: 'trends', label: 'Trend Dashboard' },
    { id: 'opportunity', label: 'Market Opportunities' },
    { id: 'mechanics', label: 'Mechanic Explorer' },
  ]
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

{#if activeTab === 'mechanics'}
  <MechanicExplorer />
{:else if activeTab === 'opportunity'}
  <MarketOpportunity />
{:else if activeTab === 'trends'}
  <TrendDashboard />
{/if}

<footer>
  <div class="data-notice">Data based on a BGG snapshot from February 28, 2026 — not live data.</div>
  Created by <a href="https://solojulian.dev" target="_blank" rel="noopener">Julian</a> &amp; Claude
</footer>
