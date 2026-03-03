<script>
  import { onMount, tick } from 'svelte'
  import * as echarts from 'echarts'
  import { fetchJSON } from '../lib/api.js'

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

  let data = null
  let loading = false
  let error = null
  let chartEl
  let chart

  // drill-down state
  let drillGames = null
  let drillTitle = ''
  let drillLoading = false

  onMount(async () => {
    try {
      ranges = await fetchJSON('/api/filters/ranges')
    } catch (e) {
      // ignore
    }
    await loadData()
  })

  async function loadData() {
    loading = true
    error = null
    try {
      data = await fetchJSON('/api/mechanic-cooccurrence', filters)
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
    await tick()
    renderChart()
  }

  function renderChart() {
    if (!chartEl || !data || !data.mechanics.length) return

    if (!chart) {
      chart = echarts.init(chartEl, 'dark')
      chart.on('click', handleCellClick)
      window.addEventListener('resize', () => chart?.resize())
    }

    const names = data.mechanics.map(m => m.name)
    const n = names.length

    // Build heatmap data: [x, y, value]
    let heatData = []
    let maxVal = 0
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const v = data.matrix[i][j]
        if (v > maxVal && i !== j) maxVal = v
        heatData.push([j, i, v])
      }
    }

    chart.setOption({
      tooltip: {
        formatter: (p) => {
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

    chart.resize()
  }

  async function handleCellClick(params) {
    if (!params.data) return
    const [xi, yi] = [params.data[0], params.data[1]]
    const m1 = data.mechanics[yi]
    const m2 = data.mechanics[xi]
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

<div class="card">
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
    <button class="btn" on:click={loadData} disabled={loading}>
      {loading ? 'Loading...' : 'Apply'}
    </button>
  </div>
</div>

{#if error}
  <div class="error">{error}</div>
{/if}

{#if loading}
  <div class="loading">Loading co-occurrence data...</div>
{/if}

{#if data}
  <div class="card" style="padding: 0.5rem;">
    <div bind:this={chartEl} style="width: 100%; height: {Math.max(500, (data.mechanics?.length || 25) * 24)}px;"></div>
  </div>
{/if}

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
