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

  // mechanic details state
  let selectedMechanicId = ''
  let mechStats = null
  let mechStatsLoading = false
  let miniChartEl
  let miniChart

  $: itemList = mode === 'mechanics' ? mechanics : categories
  $: filtered = searchText
    ? itemList.filter(m =>
        m.name.toLowerCase().includes(searchText.toLowerCase()) &&
        !selectedItems.find(s => s.id === m.id)
      ).slice(0, 20)
    : []

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
      renderPieChart()
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

  // --- Pie chart ---

  function renderPieChart() {
    if (!pieEl || !mechanics.length) return

    if (!pieChart) {
      pieChart = echarts.init(pieEl, 'dark')
      pieChart.on('click', handlePieClick)
      window.addEventListener('resize', () => pieChart?.resize())
    }

    const topN = mechanics.slice(0, pieN)
    const otherCount = mechanics.slice(pieN).reduce((s, m) => s + m.game_count, 0)
    const pieData = topN.map(m => ({ name: m.name, value: m.game_count }))
    if (otherCount > 0) pieData.push({ name: 'Other', value: otherCount })

    pieChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (p) => `${p.name}: ${p.value.toLocaleString()} games (${p.percent}%)`
      },
      legend: {
        type: 'scroll',
        orient: 'vertical',
        right: 10,
        top: 20,
        bottom: 20,
        textStyle: { color: '#aaa', fontSize: 11 }
      },
      series: [{
        type: 'pie',
        radius: ['30%', '65%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#1a1a2e', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#fff' }
        },
        data: pieData
      }]
    }, true)
    pieChart.resize()
  }

  function handlePieClick(params) {
    if (!params.name || params.name === 'Other') return
    const mech = mechanics.find(m => m.name === params.name)
    if (mech) {
      selectedMechanicId = mech.id
      loadMechanicStats()
      addToTrendChart(mech)
    }
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
    if (selectedMechanicId) {
      const mech = mechanics.find(m => String(m.id) === String(selectedMechanicId))
      if (mech) addToTrendChart(mech)
    }
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
        <h3>Mechanic Popularity Share</h3>
        <div class="filter-group" style="margin-left: auto;">
          <label>Top N</label>
          <input type="number" bind:value={pieN} min="5" max="50" style="width: 60px;"
            on:change={() => renderPieChart()}>
        </div>
      </div>
      <div bind:this={pieEl} style="width: 100%; height: 400px;"></div>
    </div>

    <div class="card">
      <div class="card-header">
        <h3>Mechanic Details</h3>
      </div>
      <div class="filter-group" style="margin-bottom: 0.75rem;">
        <label>Select a mechanic</label>
        <select bind:value={selectedMechanicId} on:change={handleMechanicDropdownChange} style="width: 100%">
          <option value="">-- Choose --</option>
          {#each mechanics as m}
            <option value={m.id}>{m.name} ({m.game_count})</option>
          {/each}
        </select>
      </div>

      {#if mechStatsLoading}
        <div class="loading">Loading stats...</div>
      {:else if mechStats}
        <div class="stats-grid">
          <div class="stat-box">
            <span class="stat-value">{mechStats.game_count.toLocaleString()}</span>
            <span class="stat-label">Games</span>
          </div>
          <div class="stat-box">
            <span class="stat-value">{mechStats.avg_rating}</span>
            <span class="stat-label">Avg Rating</span>
          </div>
          <div class="stat-box">
            <span class="stat-value">{mechStats.avg_weight}</span>
            <span class="stat-label">Avg Weight</span>
          </div>
          <div class="stat-box">
            <span class="stat-value">{mechStats.avg_playtime} min</span>
            <span class="stat-label">Avg Playtime</span>
          </div>
        </div>

        <h4 style="margin: 0.75rem 0 0.25rem; color: var(--text-dim);">Games per Year</h4>
        <div bind:this={miniChartEl} style="width: 100%; height: 150px;"></div>

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

    <div bind:this={trendChartEl} style="width: 100%; height: 400px; margin-top: 0.5rem;"></div>

    {#if chartLoading}
      <div class="loading">Updating chart...</div>
    {/if}
  </div>

  <!-- Co-occurrence heatmap -->
  <div class="card">
    <h3 style="margin-bottom: 0.75rem;">Mechanic Co-occurrence Matrix</h3>
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

  <!-- Rising/Falling mover cards -->
  {#if overview}
    <div class="card">
      <h2 class="rising">Rising Mechanics (2020-2025 vs 2015-2019)</h2>
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
                <th>Weight</th>
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
