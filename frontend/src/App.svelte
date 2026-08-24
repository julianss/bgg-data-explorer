<script>
  import { onMount } from 'svelte'
  import { fetchJSON } from './lib/api.js'
  import MechanicDashboard from './views/MechanicDashboard.svelte'
  import MarketOpportunity from './views/MarketOpportunity.svelte'
  import About from './views/About.svelte'
  import GameSearch from './views/GameSearch.svelte'

  let activeTab = 'dashboard'
  let snapshotDate = ''
  let showAbout = false

  const tabs = [
    { id: 'dashboard', label: 'Mechanics Explorer' },
    { id: 'opportunity', label: 'Market Opportunities' },
    { id: 'search', label: 'Game Search' },
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
  <nav class="tabs">
    {#each tabs as tab}
      <button
        class:active={activeTab === tab.id}
        on:click={() => activeTab = tab.id}
      >
        {tab.label}
      </button>
    {/each}
  </nav>
  <button class="info-btn" on:click={() => showAbout = !showAbout} title="About">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="16" x2="12" y2="12"/>
      <line x1="12" y1="8" x2="12.01" y2="8"/>
    </svg>
  </button>
</header>

<div class:hidden={activeTab !== 'dashboard'}>
  <MechanicDashboard />
</div>

<div class:hidden={activeTab !== 'opportunity'}>
  <MarketOpportunity />
</div>

<div class:hidden={activeTab !== 'search'}>
  <GameSearch />
</div>

{#if showAbout}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="about-overlay" on:click={() => showAbout = false}>
    <div class="about-modal" on:click|stopPropagation>
      <button class="about-close" on:click={() => showAbout = false}>&times;</button>
      <About />
    </div>
  </div>
{/if}

<footer>
  <a href="https://boardgamegeek.com" target="_blank" rel="noopener" class="bgg-logo-link">
    <img src="{import.meta.env.BASE_URL}bgg-logo.png" alt="Powered by BoardGameGeek" class="bgg-logo" />
  </a>
  {#if snapshotDate}
    <div class="data-notice">Data based on a BGG snapshot from {snapshotDate} — not live data.</div>
  {/if}
  <div class="tech-stack">Built with <a href="https://svelte.dev" target="_blank" rel="noopener">Svelte</a>, <a href="https://flask.palletsprojects.com" target="_blank" rel="noopener">Flask</a>, and <a href="https://echarts.apache.org" target="_blank" rel="noopener">Apache ECharts</a></div>
  <div>Created by <a href="https://solojulian.dev" target="_blank" rel="noopener">Julian</a> &amp; Claude · <a href="https://github.com/julianss/bgg-data-explorer" target="_blank" rel="noopener">GitHub</a></div>
</footer>
