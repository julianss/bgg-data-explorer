<script>
  import { onMount, tick } from 'svelte'
  import * as echarts from 'echarts'
  import { fetchJSON } from '../lib/api.js'

  let overview = null
  let mechanics = []
  let categories = []
  let loading = true
  let error = null

  // trend chart state
  let mode = 'mechanics' // or 'categories'
  let normalize = false
  let selectedItems = []
  let trendData = []
  let trendChartEl
  let trendChart
  let chartLoading = false

  // picker state
  let searchText = ''
  let showDropdown = false

  // co-occurrence state
  let ranges = {}
  let filters = {
    min_year: null,
    max_year: null,
    min_weight: null,
    max_weight: null,
    min_rating: null,
    min_users_rated: null,
    top_n: 25
  }
  let coData = null
  let coLoading = false
  let heatmapEl
  let heatmapChart

  // drill-down state
  let drillGames = null
  let drillTitle = ''
  let drillLoading = false

  // pie chart state
  let pieEl
  let pieChart
  let pieN = 15
  let pieSortMetric = 'game_count' // 'game_count' | 'avg_rating' | 'avg_weight' | 'avg_playtime'

  // mechanic details state
  let selectedMechanicId = ''
  let mechStats = null
  let mechStatsLoading = false
  let miniChartEl
  let miniChart
  let mechSearchText = ''
  let mechDropdownOpen = false

  // Rank maps: mechanic id -> rank (1-based) for each metric
  let ranks = { game_count: {}, avg_rating: {}, avg_weight: {}, avg_playtime: {} }

  function computeRanks() {
    for (const key of ['game_count', 'avg_rating', 'avg_weight', 'avg_playtime']) {
      const sorted = [...mechanics].sort((a, b) => (b[key] || 0) - (a[key] || 0))
      const map = {}
      sorted.forEach((m, i) => map[m.id] = i + 1)
      ranks[key] = map
    }
    ranks = ranks // trigger reactivity
  }

  $: filteredMechanics = mechSearchText
    ? mechanics.filter(m => m.name.toLowerCase().includes(mechSearchText.toLowerCase()))
    : mechanics

  function decodeEntities(str) {
    if (!str) return ''
    const el = document.createElement('textarea')
    el.innerHTML = str
    return el.value
  }

  $: itemList = mode === 'mechanics' ? mechanics : categories
  $: filtered = searchText
    ? itemList.filter(m =>
        m.name.toLowerCase().includes(searchText.toLowerCase()) &&
        !selectedItems.find(s => s.id === m.id)
      )
    : itemList.filter(m => !selectedItems.find(s => s.id === m.id))

  onMount(async () => {
    try {
      const [ov, mechs, cats, r, cooc] = await Promise.all([
        fetchJSON('/api/trends/overview'),
        fetchJSON('/api/mechanics'),
        fetchJSON('/api/categories'),
        fetchJSON('/api/filters/ranges'),
        fetchJSON('/api/mechanic-cooccurrence', filters)
      ])
      overview = ov
      mechanics = mechs
      computeRanks()
      categories = cats
      ranges = r
      coData = cooc

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
      renderTrendChart()
      renderBarChart()
      renderHeatmap()
    }
  })

  // --- Trend chart ---

  function addToTrendChart(mechanic) {
    if (mode !== 'mechanics') {
      mode = 'mechanics'
    }
    if (!selectedItems.find(s => s.id === mechanic.id)) {
      selectedItems = [...selectedItems, { id: mechanic.id, name: mechanic.name }]
      loadTrends()
    }
  }

  async function loadTrends() {
    if (!selectedItems.length) {
      trendData = []
      renderTrendChart()
      return
    }
    chartLoading = true
    try {
      const ids = selectedItems.map(s => s.id).join(',')
      const endpoint = mode === 'mechanics' ? '/api/trends/mechanics' : '/api/trends/categories'
      const paramKey = mode === 'mechanics' ? 'mechanic_ids' : 'category_ids'
      trendData = await fetchJSON(endpoint, { [paramKey]: ids, normalize: normalize ? 'true' : 'false' })
      renderTrendChart()
    } catch (e) {
      error = e.message
    } finally {
      chartLoading = false
    }
  }

  function renderTrendChart() {
    if (!trendChartEl) return

    if (!trendChart) {
      trendChart = echarts.init(trendChartEl, 'dark')
      window.addEventListener('resize', () => trendChart?.resize())
    }

    if (!trendData.length) {
      trendChart.clear()
      return
    }

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

    trendChart.setOption({
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

    trendChart.resize()
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
    renderTrendChart()
  }

  // --- Bar chart ---

  const metricLabels = {
    game_count: 'Games',
    avg_rating: 'Avg Rating',
    avg_weight: 'Avg Complexity',
    avg_playtime: 'Avg Playtime'
  }

  const metricUnits = {
    game_count: ' games',
    avg_rating: '',
    avg_weight: '/5',
    avg_playtime: ' min'
  }

  // sorted mechanics list for the scrollable pane
  $: sortedMechanics = [...mechanics].sort((a, b) => (b[pieSortMetric] || 0) - (a[pieSortMetric] || 0))

  function renderBarChart() {
    if (!pieEl || !mechanics.length) return

    if (!pieChart) {
      pieChart = echarts.init(pieEl, 'dark')
      pieChart.on('click', handleBarClick)
      window.addEventListener('resize', () => pieChart?.resize())
    }

    const sorted = [...mechanics].sort((a, b) => (b[pieSortMetric] || 0) - (a[pieSortMetric] || 0))
    const topN = sorted.slice(0, pieN)
    const unit = metricUnits[pieSortMetric]
    const names = topN.map(m => m.name).reverse()
    const values = topN.map(m => m[pieSortMetric] || 0).reverse()

    pieChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const p = params[0]
          const val = pieSortMetric === 'game_count' ? p.value.toLocaleString() : p.value
          return `${p.name}: ${val}${unit}`
        }
      },
      grid: { left: 140, right: 30, top: 10, bottom: 20 },
      xAxis: {
        type: 'value',
        axisLabel: { color: '#aaa' }
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: { color: '#aaa', fontSize: 11 }
      },
      series: [{
        type: 'bar',
        data: values,
        itemStyle: { color: '#e94560', borderRadius: [0, 4, 4, 0] },
        emphasis: { itemStyle: { color: '#ff6b81' } }
      }]
    }, true)
    pieChart.resize()
  }

  function handleBarClick(params) {
    if (!params.name) return
    const mech = mechanics.find(m => m.name === params.name)
    if (mech) {
      selectedMechanicId = mech.id
      mechSearchText = mech.name
      loadMechanicStats()
    }
  }

  function selectMechanicFromList(mech) {
    selectedMechanicId = mech.id
    mechSearchText = mech.name
    loadMechanicStats()
  }

  // --- Mechanic details ---

  async function loadMechanicStats() {
    if (!selectedMechanicId) { mechStats = null; return }
    mechStatsLoading = true
    try {
      mechStats = await fetchJSON(`/api/mechanic-stats/${selectedMechanicId}`)
    } catch (e) {
      error = e.message
      mechStats = null
    } finally {
      mechStatsLoading = false
    }
    await tick()
    renderMiniChart()
  }

  function handleMechanicDropdownChange() {
    loadMechanicStats()
  }

  function clearMechanicSelection() {
    selectedMechanicId = ''
    mechSearchText = ''
    mechStats = null
  }

  function addSelectedMechanicToTrend() {
    if (!selectedMechanicId) return
    const mech = mechanics.find(m => String(m.id) === String(selectedMechanicId))
    if (mech) addToTrendChart(mech)
  }

  function handleCoMechClick(cm) {
    const mech = mechanics.find(m => m.name === cm.name)
    if (mech) addToTrendChart(mech)
  }

  function renderMiniChart() {
    if (!miniChartEl || !mechStats?.yearly?.length) return

    if (miniChart) {
      miniChart.dispose()
    }
    miniChart = echarts.init(miniChartEl, 'dark')
    window.addEventListener('resize', () => miniChart?.resize())

    miniChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: mechStats.yearly.map(y => y.year), axisLabel: { color: '#aaa', fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: '#aaa', fontSize: 10 } },
      series: [{
        type: 'bar',
        data: mechStats.yearly.map(y => y.cnt),
        itemStyle: { color: '#e94560', borderRadius: [3, 3, 0, 0] }
      }]
    }, true)
    miniChart.resize()
  }

  // --- Co-occurrence heatmap ---

  async function loadCoData() {
    coLoading = true
    error = null
    try {
      coData = await fetchJSON('/api/mechanic-cooccurrence', filters)
    } catch (e) {
      error = e.message
    } finally {
      coLoading = false
    }
    await tick()
    renderHeatmap()
  }

  function renderHeatmap() {
    if (!heatmapEl || !coData || !coData.mechanics.length) return

    if (!heatmapChart) {
      heatmapChart = echarts.init(heatmapEl, 'dark')
      heatmapChart.on('click', handleCellClick)
      window.addEventListener('resize', () => heatmapChart?.resize())
    }

    const names = coData.mechanics.map(m => m.name)
    const n = names.length

    let heatData = []
    let maxVal = 0
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i === j) {
          heatData.push([j, i, '-'])
          continue
        }
        const v = coData.matrix[i][j]
        if (v > maxVal) maxVal = v
        heatData.push([j, i, v])
      }
    }

    heatmapChart.setOption({
      tooltip: {
        formatter: (p) => {
          if (p.data[2] === '-') return null
          const x = names[p.data[0]]
          const y = names[p.data[1]]
          return `${y} + ${x}: ${p.data[2]} games`
        }
      },
      grid: {
        left: 180,
        right: 20,
        top: 20,
        bottom: 180
      },
      xAxis: {
        type: 'category',
        data: names,
        axisLabel: { rotate: 45, fontSize: 10, color: '#aaa' },
        splitArea: { show: true }
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: { fontSize: 10, color: '#aaa' },
        splitArea: { show: true }
      },
      visualMap: {
        min: 0,
        max: maxVal || 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: {
          color: ['#1a1a2e', '#533483', '#e94560']
        },
        textStyle: { color: '#aaa' }
      },
      series: [{
        type: 'heatmap',
        data: heatData,
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }
        }
      }]
    }, true)

    heatmapChart.resize()
  }

  async function handleCellClick(params) {
    if (!params.data) return
    const [xi, yi] = [params.data[0], params.data[1]]
    const m1 = coData.mechanics[yi]
    const m2 = coData.mechanics[xi]
    drillTitle = m1.id === m2.id
      ? `Games with "${m1.name}"`
      : `Games with "${m1.name}" + "${m2.name}"`
    drillLoading = true
    drillGames = []
    try {
      drillGames = await fetchJSON('/api/mechanic-pair-games', { m1: m1.id, m2: m2.id })
    } catch (e) {
      drillGames = null
      error = e.message
    } finally {
      drillLoading = false
    }
  }

  function closeDrill() {
    drillGames = null
  }
</script>

{#if loading}
  <div class="loading">Loading dashboard...</div>
{:else if error}
  <div class="error">{error}</div>
{:else}

  <!-- Pie chart + Mechanic details row -->
  <div class="two-col">
    <div class="card">
      <div class="card-header">
        <h3>Top Mechanics By</h3>
        <div class="filter-group" style="margin-left: auto;">
          <label>Top N</label>
          <input type="number" bind:value={pieN} min="5" max="50" style="width: 60px;"
            on:change={() => renderBarChart()}>
        </div>
      </div>
      <div class="toggle-group" style="margin-bottom: 0.5rem;">
        {#each Object.entries(metricLabels) as [key, label]}
          <button class:active={pieSortMetric === key} on:click={() => { pieSortMetric = key; renderBarChart() }}>{label}</button>
        {/each}
      </div>
      <p class="help-text">Top mechanics ranked by the selected metric. Click a bar to see its details.</p>
      <div bind:this={pieEl} style="width: 100%; height: {Math.max(300, pieN * 24)}px;"></div>
      <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">All {mechanics.length} Mechanics</h4>
      <div class="ranked-list">
        {#each sortedMechanics as mech, i}
          <button class="ranked-item" class:active={String(mech.id) === String(selectedMechanicId)} on:click={() => selectMechanicFromList(mech)}>
            <span class="ranked-pos">#{i + 1}</span>
            <span class="ranked-name">{mech.name}</span>
            <span class="ranked-val">{pieSortMetric === 'game_count' ? mech[pieSortMetric].toLocaleString() : mech[pieSortMetric]}{metricUnits[pieSortMetric]}</span>
          </button>
        {/each}
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Mechanic Details</h3>
      </div>
      <div class="filter-group" style="margin-bottom: 0.75rem;">
        <label>Select a mechanic</label>
        <div class="searchable-select">
          <input
            type="text"
            placeholder="Search mechanics..."
            bind:value={mechSearchText}
            on:focus={() => mechDropdownOpen = true}
            on:input={() => mechDropdownOpen = true}
            autocomplete="off"
          />
          {#if mechSearchText}
            <button class="clear-btn" on:click={clearMechanicSelection} title="Clear selection">&times;</button>
          {/if}
          {#if mechDropdownOpen}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div class="searchable-backdrop" on:click={() => mechDropdownOpen = false}></div>
            <div class="searchable-options">
              {#each filteredMechanics as m}
                <button
                  class="searchable-option"
                  class:active={String(m.id) === String(selectedMechanicId)}
                  on:click={() => { selectedMechanicId = m.id; mechSearchText = m.name; mechDropdownOpen = false; handleMechanicDropdownChange() }}
                >{m.name} ({m.game_count})</button>
              {/each}
              {#if filteredMechanics.length === 0}
                <div class="searchable-option dim">No matches</div>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      {#if mechStatsLoading}
        <div class="loading">Loading stats...</div>
      {:else if mechStats}
        <div class="stats-grid">
          <div class="stat-box" title="Total number of games that use this mechanic">
            <span class="stat-value">{mechStats.game_count.toLocaleString()}</span>
            <span class="stat-label">Games</span>
            <span class="stat-rank">#{ranks.game_count[selectedMechanicId] || '?'}</span>
          </div>
          <div class="stat-box" title="Average user rating (out of 10) across all games with this mechanic">
            <span class="stat-value">{mechStats.avg_rating}</span>
            <span class="stat-label">Avg Rating</span>
            <span class="stat-rank">#{ranks.avg_rating[selectedMechanicId] || '?'}</span>
          </div>
          <div class="stat-box" title="Average complexity on a 1-5 scale, rated by BGG users based on how difficult the game is to understand and play">
            <span class="stat-value">{mechStats.avg_weight}</span>
            <span class="stat-label">Avg Complexity</span>
            <span class="stat-rank">#{ranks.avg_weight[selectedMechanicId] || '?'}</span>
          </div>
          <div class="stat-box" title="Average playing time in minutes across all games with this mechanic">
            <span class="stat-value">{mechStats.avg_playtime} min</span>
            <span class="stat-label">Avg Playtime</span>
            <span class="stat-rank">#{ranks.avg_playtime[selectedMechanicId] || '?'}</span>
          </div>
        </div>
        {#if mechStats.description}
          <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">Description</h4>
          <p class="mechanic-description">{decodeEntities(mechStats.description)}</p>
        {/if}

        <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">Games per Year</h4>
        <div bind:this={miniChartEl} style="width: 100%; height: 150px;"></div>
        <button class="btn" style="margin-top: 0.5rem;" on:click={addSelectedMechanicToTrend}>Add to trend graph</button>

        <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">Top Co-occurring Mechanics</h4>
        <div class="co-mechs">
          {#each mechStats.co_mechanics as cm}
            <span class="tag clickable" on:click={() => handleCoMechClick(cm)}>{cm.name} ({cm.cnt})</span>
          {/each}
        </div>

        <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">Top Games</h4>
        <div class="top-games-list">
          {#each mechStats.top_games as game}
            <div class="top-game">
              <a href="https://boardgamegeek.com/boardgame/{game.id}" target="_blank">{game.name}</a>
              <span class="dim">({game.year_published || '?'}) — {game.average?.toFixed(1)}</span>
            </div>
          {/each}
        </div>
      {:else}
        <p style="color: var(--text-dim); padding: 1rem;">Select a mechanic to see its stats.</p>
      {/if}
    </div>
  </div>

  <!-- Trend line chart -->
  <div class="card">
    <div class="flex-between" style="margin-bottom: 0.75rem;">
      <h2>Trends Over Time</h2>
      <p class="help-text" style="margin: 0;">Track how the popularity of specific mechanics or categories has changed year by year. Use "% share" to compare relative popularity regardless of the growing number of games published each year.</p>
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

    <div style="margin-bottom: 0.75rem; max-width: 350px;">
      <div class="searchable-select">
        <input
          type="text"
          placeholder="Search {mode}..."
          bind:value={searchText}
          on:focus={() => showDropdown = true}
          on:input={() => showDropdown = true}
          autocomplete="off"
        />
        {#if searchText}
          <button class="clear-btn" on:click={() => { searchText = ''; showDropdown = false }} title="Clear search">&times;</button>
        {/if}
        {#if showDropdown}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="searchable-backdrop" on:click={() => showDropdown = false}></div>
          <div class="searchable-options">
            {#each filtered as item}
              <button
                class="searchable-option"
                on:click={() => addItem(item)}
              >{item.name} ({item.game_count})</button>
            {/each}
            {#if filtered.length === 0}
              <div class="searchable-option dim">No matches</div>
            {/if}
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

    <div bind:this={trendChartEl} style="width: 100%; height: 400px; margin-top: 0.5rem;"></div>

    {#if chartLoading}
      <div class="loading">Updating chart...</div>
    {/if}
  </div>

  <!-- Rising/Falling mover cards -->
  {#if overview}
    <div class="card">
      <h2 class="rising">Rising Mechanics (2020-2025 vs 2015-2019)</h2>
      <p class="help-text">Mechanics that are being used in a larger share of new games compared to previous years. A higher percentage means the mechanic is becoming more popular among game designers. Click any card to add it to the trend chart above.</p>
      <div class="mover-cards">
        {#each overview.rising as mover}
          <div class="mover-card" on:click={() => addToTrendChart(mover)}>
            <div class="name">{mover.name}</div>
            <div class="change rising">+{mover.share_change.toFixed(2)}%</div>
          </div>
        {/each}
      </div>
    </div>
    <div class="card">
      <h2 class="falling">Declining Mechanics</h2>
      <p class="help-text">Mechanics that are appearing in a smaller share of new games compared to previous years. This doesn't mean they're bad — just that designers are using them less often in recent titles.</p>
      <div class="mover-cards">
        {#each overview.falling as mover}
          <div class="mover-card" on:click={() => addToTrendChart(mover)}>
            <div class="name">{mover.name}</div>
            <div class="change falling">{mover.share_change.toFixed(2)}%</div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Co-occurrence heatmap -->
  <div class="card">
    <h3 style="margin-bottom: 0.25rem;">Mechanic Co-occurrence Matrix</h3>
    <p class="help-text">Shows how often pairs of mechanics appear together in the same game. Brighter cells mean two mechanics are frequently combined. Click any cell to see the actual games that use both mechanics.</p>
    <div class="filters">
      <div class="filter-group">
        <label>Year min</label>
        <input type="number" bind:value={filters.min_year} placeholder={ranges.min_year}>
      </div>
      <div class="filter-group">
        <label>Year max</label>
        <input type="number" bind:value={filters.max_year} placeholder={ranges.max_year}>
      </div>
      <div class="filter-group">
        <label>Weight min</label>
        <input type="number" step="0.1" bind:value={filters.min_weight} placeholder={ranges.min_weight}>
      </div>
      <div class="filter-group">
        <label>Weight max</label>
        <input type="number" step="0.1" bind:value={filters.max_weight} placeholder={ranges.max_weight}>
      </div>
      <div class="filter-group">
        <label>Rating min</label>
        <input type="number" step="0.1" bind:value={filters.min_rating} placeholder="0">
      </div>
      <div class="filter-group">
        <label>Min users</label>
        <input type="number" bind:value={filters.min_users_rated} placeholder="0">
      </div>
      <div class="filter-group">
        <label>Top N</label>
        <input type="number" bind:value={filters.top_n} min="5" max="50">
      </div>
      <button class="btn" on:click={loadCoData} disabled={coLoading}>
        {coLoading ? 'Loading...' : 'Apply'}
      </button>
    </div>

    {#if coLoading}
      <div class="loading">Loading co-occurrence data...</div>
    {/if}

    {#if coData}
      <div bind:this={heatmapEl} style="width: 100%; height: {Math.max(500, (coData.mechanics?.length || 25) * 24)}px;"></div>
    {/if}
  </div>

  <!-- Drill-down modal -->
  {#if drillGames !== null}
    <div class="modal-backdrop" on:click={closeDrill} on:keydown={(e) => e.key === 'Escape' && closeDrill()}>
      <div class="modal" on:click|stopPropagation>
        <button class="close" on:click={closeDrill}>x</button>
        <h2>{drillTitle}</h2>
        {#if drillLoading}
          <div class="loading">Loading games...</div>
        {:else}
          <p style="color: var(--text-dim); margin-bottom: 0.75rem;">{drillGames.length} games</p>
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Name</th>
                <th>Year</th>
                <th>Rating</th>
                <th>Voters</th>
                <th>Complexity</th>
              </tr>
            </thead>
            <tbody>
              {#each drillGames as game}
                <tr>
                  <td>{game.rank || '-'}</td>
                  <td><a href="https://boardgamegeek.com/boardgame/{game.id}" target="_blank">{game.name}</a></td>
                  <td>{game.year_published || '-'}</td>
                  <td>{game.average?.toFixed(1) || '-'}</td>
                  <td>{game.users_rated?.toLocaleString() || '-'}</td>
                  <td>{game.weight?.toFixed(1) || '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
  {/if}
{/if}
