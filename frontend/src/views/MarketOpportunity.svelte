<script>
  import { onMount, tick } from 'svelte'
  import * as echarts from 'echarts'
  import { fetchJSON } from '../lib/api.js'

  let filters = {
    min_users_rated: 100,
    min_year: null,
    min_games: 3
  }

  let data = []
  let loading = false
  let error = null
  let chartEl
  let chart

  let chartItemCount = 100

  let sortKey = 'opportunity_score'
  let sortDir = -1
  let showTop = 50

  // drill-down
  let drillGames = null
  let drillTitle = ''
  let drillLoading = false

  $: sorted = [...data].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey]
    if (typeof av === 'string') return av.localeCompare(bv) * sortDir
    return (av - bv) * sortDir
  }).slice(0, showTop)

  onMount(() => loadData())

  async function loadData() {
    loading = true
    error = null
    try {
      data = await fetchJSON('/api/opportunity-matrix', filters)
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
    await tick()
    renderChart()
  }

  function renderChart() {
    if (!chartEl || !data.length) return

    if (!chart) {
      chart = echarts.init(chartEl, 'dark')
      chart.on('click', handleTreemapClick)
      window.addEventListener('resize', () => chart?.resize())
    }

    // Top 100 by opportunity score for the treemap
    const top = [...data].sort((a, b) => b.opportunity_score - a.opportunity_score).slice(0, 100)
    chartItemCount = top.length

    // Group by category for a two-level treemap
    const byCategory = {}
    for (const d of top) {
      if (!byCategory[d.category_name]) {
        byCategory[d.category_name] = []
      }
      byCategory[d.category_name].push(d)
    }

    const treeData = Object.entries(byCategory).map(([catName, items]) => ({
      name: catName,
      children: items.map(d => ({
        name: d.mechanic_name,
        value: d.opportunity_score,
        raw: d,
        itemStyle: {
          color: ratingColor(d.avg_rating)
        }
      }))
    }))

    chart.setOption({
      tooltip: {
        formatter: (p) => {
          const d = p.data.raw
          if (!d) return p.name
          return `<b>${d.mechanic_name}</b> + <b>${d.category_name}</b><br>
            Games: ${d.game_count}<br>
            Avg rating: ${d.avg_rating}<br>
            Avg voters: ${d.avg_users_rated?.toLocaleString()}<br>
            Opportunity score: ${d.opportunity_score}`
        }
      },
      series: [{
        type: 'treemap',
        data: treeData,
        width: '100%',
        height: '100%',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        levels: [
          {
            // Level 0: invisible root
            itemStyle: {
              borderWidth: 0,
              gapWidth: 2
            }
          },
          {
            // Level 1: Category groups
            itemStyle: {
              borderColor: '#0a0a1a',
              borderWidth: 4,
              gapWidth: 4
            },
            upperLabel: {
              show: true,
              height: 30,
              color: '#fff',
              fontSize: 14,
              fontWeight: 'bold',
              backgroundColor: '#0f3460',
              padding: [6, 10]
            }
          },
          {
            // Level 2: Mechanic leaves
            itemStyle: {
              borderColor: 'rgba(26,26,46,0.8)',
              borderWidth: 1,
              gapWidth: 1
            },
            label: {
              show: true,
              formatter: (p) => {
                const d = p.data.raw
                if (!d) return p.name
                return `{title|${d.mechanic_name}}\n{small|${d.game_count} games · ★${d.avg_rating}}`
              },
              rich: {
                title: { fontSize: 11, color: '#fff', fontWeight: 'bold', lineHeight: 16 },
                small: { fontSize: 9, color: 'rgba(255,255,255,0.6)', lineHeight: 14 }
              },
              color: '#fff'
            }
          }
        ]
      }]
    }, true)

    chart.resize()
  }

  function ratingColor(rating) {
    // Map rating 6..8.5 to a hue range: low=cool purple, high=warm pink/red
    const t = Math.max(0, Math.min(1, (rating - 6) / 2.5))
    const h = 270 - t * 50  // 270 (purple) → 220 (blue) at low, but let's make it more useful
    // Use a perceptual gradient: low ratings = muted blue-purple, high = vivid magenta-pink
    const r = Math.round(80 + t * 175)
    const g = Math.round(50 + (1 - t) * 80)
    const b = Math.round(180 - t * 40)
    return `rgb(${r}, ${g}, ${b})`
  }

  function handleTreemapClick(params) {
    const d = params.data?.raw
    if (!d) return
    drillDown(d)
  }

  async function drillDown(d) {
    drillTitle = `${d.mechanic_name} + ${d.category_name}`
    drillLoading = true
    drillGames = []
    try {
      drillGames = await fetchJSON('/api/opportunity-games', {
        mechanic_id: d.mechanic_id,
        category_id: d.category_id
      })
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

  function toggleSort(key) {
    if (sortKey === key) {
      sortDir *= -1
    } else {
      sortKey = key
      sortDir = key === 'mechanic_name' || key === 'category_name' ? 1 : -1
    }
  }
</script>

<div class="card">
  <div class="filters">
    <div class="filter-group">
      <label>Min users rated</label>
      <input type="number" bind:value={filters.min_users_rated}>
    </div>
    <div class="filter-group">
      <label>Min year</label>
      <input type="number" bind:value={filters.min_year}>
    </div>
    <div class="filter-group">
      <label>Min games in combo</label>
      <input type="number" bind:value={filters.min_games}>
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
  <div class="loading">Loading opportunity data...</div>
{/if}

{#if data.length}
  <div class="card" style="padding: 0.5rem;">
    <p style="color: var(--text-dim); font-size: 0.8rem; margin-bottom: 0.5rem;">
      Grouped by category. Size = opportunity score, brighter pink = higher avg rating. Click a cell for game list.
    </p>
    <div class="chart-scroll">
      <div bind:this={chartEl} style="width: {Math.max(1200, chartItemCount * 18)}px; height: {Math.max(800, chartItemCount * 12)}px; flex-shrink: 0;"></div>
    </div>
  </div>

  <div class="card">
    <div class="flex-between" style="margin-bottom: 0.75rem;">
      <h2>Top Opportunities</h2>
      <div class="filter-group">
        <label>Show top</label>
        <select bind:value={showTop}>
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
          <option value={200}>200</option>
        </select>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th on:click={() => toggleSort('mechanic_name')}>Mechanic</th>
          <th on:click={() => toggleSort('category_name')}>Category</th>
          <th on:click={() => toggleSort('game_count')}>Games</th>
          <th on:click={() => toggleSort('avg_rating')}>Avg Rating</th>
          <th on:click={() => toggleSort('avg_users_rated')}>Avg Voters</th>
          <th on:click={() => toggleSort('opportunity_score')}>Opportunity</th>
        </tr>
      </thead>
      <tbody>
        {#each sorted as row}
          <tr on:click={() => drillDown(row)} style="cursor: pointer;">
            <td>{row.mechanic_name}</td>
            <td>{row.category_name}</td>
            <td>{row.game_count}</td>
            <td>{row.avg_rating}</td>
            <td>{row.avg_users_rated?.toLocaleString()}</td>
            <td><strong>{row.opportunity_score}</strong></td>
          </tr>
        {/each}
      </tbody>
    </table>
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

<style>
  .chart-scroll {
    overflow: auto;
    max-height: 75vh;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding-bottom: 20px;
    padding-right: 20px;
  }
</style>
