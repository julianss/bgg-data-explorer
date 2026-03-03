<script>
  import { onMount, tick } from 'svelte'
  import * as echarts from 'echarts'
  import { fetchJSON } from '../lib/api.js'

  let overview = null
  let mechanics = []
  let categories = []
  let loading = true
  let error = null

  // chart state
  let mode = 'mechanics' // or 'categories'
  let normalize = false
  let selectedItems = []
  let trendData = []
  let chartEl
  let chart
  let chartLoading = false

  // picker state
  let searchText = ''
  let showDropdown = false

  $: itemList = mode === 'mechanics' ? mechanics : categories
  $: filtered = searchText
    ? itemList.filter(m =>
        m.name.toLowerCase().includes(searchText.toLowerCase()) &&
        !selectedItems.find(s => s.id === m.id)
      ).slice(0, 20)
    : []

  onMount(async () => {
    try {
      const [ov, mechs, cats] = await Promise.all([
        fetchJSON('/api/trends/overview'),
        fetchJSON('/api/mechanics'),
        fetchJSON('/api/categories')
      ])
      overview = ov
      mechanics = mechs
      categories = cats

      // Pre-select top 3 rising mechanics
      if (ov.rising?.length) {
        selectedItems = ov.rising.slice(0, 3).map(r => ({ id: r.id, name: r.name }))
        await loadTrends()
      }
    } catch (e) {
      error = e.message
    } finally {
      loading = false
      await tick()
      renderChart()
    }
  })

  async function loadTrends() {
    if (!selectedItems.length) {
      trendData = []
      renderChart()
      return
    }
    chartLoading = true
    try {
      const ids = selectedItems.map(s => s.id).join(',')
      const endpoint = mode === 'mechanics' ? '/api/trends/mechanics' : '/api/trends/categories'
      const paramKey = mode === 'mechanics' ? 'mechanic_ids' : 'category_ids'
      trendData = await fetchJSON(endpoint, { [paramKey]: ids, normalize: normalize ? 'true' : 'false' })
      renderChart()
    } catch (e) {
      error = e.message
    } finally {
      chartLoading = false
    }
  }

  function renderChart() {
    if (!chartEl) return

    if (!chart) {
      chart = echarts.init(chartEl, 'dark')
      window.addEventListener('resize', () => chart?.resize())
    }

    if (!trendData.length) {
      chart.clear()
      return
    }

    // Group data by item
    const nameKey = mode === 'mechanics' ? 'mechanic_name' : 'category_name'
    const grouped = {}
    for (const r of trendData) {
      const name = r[nameKey]
      if (!grouped[name]) grouped[name] = []
      grouped[name].push([r.year, r.value])
    }

    const series = Object.entries(grouped).map(([name, points]) => ({
      name,
      type: 'line',
      smooth: true,
      data: points,
      emphasis: { focus: 'series' }
    }))

    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: {
        data: Object.keys(grouped),
        textStyle: { color: '#aaa' },
        top: 0
      },
      grid: { left: 50, right: 20, top: 40, bottom: 40 },
      xAxis: {
        type: 'value',
        min: 'dataMin',
        max: 'dataMax',
        axisLabel: { color: '#aaa', formatter: (v) => String(v) }
      },
      yAxis: {
        type: 'value',
        name: normalize ? '% of games' : 'Game count',
        nameTextStyle: { color: '#aaa' },
        axisLabel: { color: '#aaa' }
      },
      series
    }, true)

    chart.resize()
  }

  function addItem(item) {
    selectedItems = [...selectedItems, { id: item.id, name: item.name }]
    searchText = ''
    showDropdown = false
    loadTrends()
  }

  function removeItem(id) {
    selectedItems = selectedItems.filter(s => s.id !== id)
    loadTrends()
  }

  function switchMode(newMode) {
    if (mode === newMode) return
    mode = newMode
    selectedItems = []
    trendData = []
    renderChart()
  }

  function toggleNormalize() {
    normalize = !normalize
    loadTrends()
  }

  function addMoverToChart(mover) {
    if (mode !== 'mechanics') {
      mode = 'mechanics'
    }
    if (!selectedItems.find(s => s.id === mover.id)) {
      selectedItems = [...selectedItems, { id: mover.id, name: mover.name }]
      loadTrends()
    }
  }
</script>

{#if loading}
  <div class="loading">Loading dashboard...</div>
{:else if error}
  <div class="error">{error}</div>
{:else}

  {#if overview}
    <div class="card">
      <h2 class="rising">Rising Mechanics (2020-2025 vs 2015-2019)</h2>
      <div class="mover-cards">
        {#each overview.rising as mover}
          <div class="mover-card" on:click={() => addMoverToChart(mover)}>
            <div class="name">{mover.name}</div>
            <div class="change rising">+{mover.share_change.toFixed(2)}%</div>
          </div>
        {/each}
      </div>
    </div>
    <div class="card">
      <h2 class="falling">Declining Mechanics</h2>
      <div class="mover-cards">
        {#each overview.falling as mover}
          <div class="mover-card" on:click={() => addMoverToChart(mover)}>
            <div class="name">{mover.name}</div>
            <div class="change falling">{mover.share_change.toFixed(2)}%</div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="card">
    <div class="flex-between" style="margin-bottom: 0.75rem;">
      <h2>Trends Over Time</h2>
      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <div class="toggle-group">
          <button class:active={mode === 'mechanics'} on:click={() => switchMode('mechanics')}>Mechanics</button>
          <button class:active={mode === 'categories'} on:click={() => switchMode('categories')}>Categories</button>
        </div>
        <div class="toggle-group">
          <button class:active={!normalize} on:click={() => { normalize = false; loadTrends() }}>Count</button>
          <button class:active={normalize} on:click={() => { normalize = true; loadTrends() }}>% share</button>
        </div>
      </div>
    </div>

    <div style="display: flex; gap: 1rem; align-items: start; margin-bottom: 0.75rem;">
      <div class="tag-picker">
        <input
          type="text"
          bind:value={searchText}
          on:focus={() => showDropdown = true}
          on:blur={() => setTimeout(() => showDropdown = false, 200)}
          placeholder="Search {mode}..."
        >
        {#if showDropdown && filtered.length}
          <div class="dropdown">
            {#each filtered as item}
              <div on:mousedown={() => addItem(item)}>{item.name} ({item.game_count})</div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    {#if selectedItems.length}
      <div class="selected-tags">
        {#each selectedItems as item}
          <span class="chip" on:click={() => removeItem(item.id)}>
            {item.name} x
          </span>
        {/each}
      </div>
    {/if}

    <div bind:this={chartEl} style="width: 100%; height: 400px; margin-top: 0.5rem;"></div>

    {#if chartLoading}
      <div class="loading">Updating chart...</div>
    {/if}
  </div>
{/if}
