<script>
  import { onMount } from 'svelte'
  import { fetchJSON } from '../lib/api.js'

  let mechanics = []
  let categories = []

  // Filter state
  let titleQuery = ''
  let descQuery = ''
  let selectedMechanics = []
  let selectedCategories = []

  // Mechanic picker
  let mechSearchText = ''
  let mechDropdownOpen = false

  // Category picker
  let catSearchText = ''
  let catDropdownOpen = false

  // Results
  let results = null
  let total = 0
  let page = 1
  let pages = 0
  let loading = false

  $: filteredMechs = mechSearchText
    ? mechanics.filter(m => m.name.toLowerCase().includes(mechSearchText.toLowerCase()) && !selectedMechanics.some(s => s.id === m.id))
    : mechanics.filter(m => !selectedMechanics.some(s => s.id === m.id))

  $: filteredCats = catSearchText
    ? categories.filter(c => c.name.toLowerCase().includes(catSearchText.toLowerCase()) && !selectedCategories.some(s => s.id === c.id))
    : categories.filter(c => !selectedCategories.some(s => s.id === c.id))

  $: hasFilters = titleQuery.trim() || descQuery.trim() || selectedMechanics.length > 0 || selectedCategories.length > 0

  onMount(async () => {
    const [mechs, cats] = await Promise.all([
      fetchJSON('/api/mechanics'),
      fetchJSON('/api/categories'),
    ])
    mechanics = mechs
    categories = cats
  })

  async function search(newPage = 1) {
    if (!hasFilters) return
    loading = true
    page = newPage
    try {
      const params = { page }
      if (titleQuery.trim()) params.title = titleQuery.trim()
      if (descQuery.trim()) params.description = descQuery.trim()
      if (selectedMechanics.length) params.mechanic_ids = selectedMechanics.map(m => m.id).join(',')
      if (selectedCategories.length) params.category_ids = selectedCategories.map(c => c.id).join(',')
      const data = await fetchJSON('/api/search-games', params)
      results = data.results
      total = data.total
      pages = data.pages
    } catch (e) {
      results = []
      total = 0
    }
    loading = false
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') search(1)
  }

  function addMechanic(m) {
    selectedMechanics = [...selectedMechanics, m]
    mechSearchText = ''
    mechDropdownOpen = false
  }

  function removeMechanic(m) {
    selectedMechanics = selectedMechanics.filter(s => s.id !== m.id)
  }

  function addCategory(c) {
    selectedCategories = [...selectedCategories, c]
    catSearchText = ''
    catDropdownOpen = false
  }

  function removeCategory(c) {
    selectedCategories = selectedCategories.filter(s => s.id !== c.id)
  }

  function clearAll() {
    titleQuery = ''
    descQuery = ''
    selectedMechanics = []
    selectedCategories = []
    results = null
    total = 0
    page = 1
    pages = 0
  }

  function highlightWords(text, query) {
    if (!query || !text) return escapeHtml(text || '')
    const escaped = escapeHtml(text)
    const words = query.trim().split(/\s+/)
    const pattern = new RegExp('(' + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi')
    return escaped.replace(pattern, '<mark>$1</mark>')
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  }
</script>

<div class="game-search">
  <div class="card">
    <h2>Search Games</h2>
    <p class="help-text">Filter the dataset by title, description keywords, mechanics, and categories. All filters are combined with AND logic.</p>

    <div class="search-filters">
      <div class="filter-row">
        <div class="filter-group" style="flex:1; min-width: 200px;">
          <label>Title</label>
          <input type="text" bind:value={titleQuery} on:keydown={handleKeydown} placeholder="Search by game title..." style="width:100%;" />
        </div>

        <div class="filter-group" style="flex:1; min-width: 200px;">
          <label>Description keywords</label>
          <input type="text" bind:value={descQuery} on:keydown={handleKeydown} placeholder="e.g. deck building victory points" style="width:100%;" />
        </div>
      </div>

      <div class="filter-row">
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="filter-group" style="flex:1; min-width: 200px;">
          <label>Mechanics</label>
          <div class="tag-picker">
            <input type="text" bind:value={mechSearchText}
              on:focus={() => mechDropdownOpen = true}
              placeholder="Type to filter mechanics..." />
            {#if mechDropdownOpen}
              <div class="searchable-backdrop" on:click={() => mechDropdownOpen = false}></div>
              <div class="dropdown">
                {#each filteredMechs.slice(0, 20) as m}
                  <div on:click={() => addMechanic(m)}>{m.name} <span style="color:var(--text-dim)">({m.game_count})</span></div>
                {/each}
                {#if filteredMechs.length === 0}
                  <div style="color:var(--text-dim)">No matches</div>
                {/if}
              </div>
            {/if}
          </div>
          {#if selectedMechanics.length > 0}
            <div class="selected-tags">
              {#each selectedMechanics as m}
                <span class="chip" on:click={() => removeMechanic(m)}>{m.name} &times;</span>
              {/each}
            </div>
          {/if}
        </div>

        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="filter-group" style="flex:1; min-width: 200px;">
          <label>Categories</label>
          <div class="tag-picker">
            <input type="text" bind:value={catSearchText}
              on:focus={() => catDropdownOpen = true}
              placeholder="Type to filter categories..." />
            {#if catDropdownOpen}
              <div class="searchable-backdrop" on:click={() => catDropdownOpen = false}></div>
              <div class="dropdown">
                {#each filteredCats.slice(0, 20) as c}
                  <div on:click={() => addCategory(c)}>{c.name} <span style="color:var(--text-dim)">({c.game_count})</span></div>
                {/each}
                {#if filteredCats.length === 0}
                  <div style="color:var(--text-dim)">No matches</div>
                {/if}
              </div>
            {/if}
          </div>
          {#if selectedCategories.length > 0}
            <div class="selected-tags">
              {#each selectedCategories as c}
                <span class="chip" on:click={() => removeCategory(c)}>{c.name} &times;</span>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn" on:click={() => search(1)} disabled={!hasFilters || loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
        <button class="btn btn-secondary" on:click={clearAll}>Clear</button>
      </div>
    </div>
  </div>

  {#if loading}
    <div class="loading">Searching...</div>
  {:else if results !== null}
    <div class="card">
      <div class="results-header">
        <span>{total.toLocaleString()} game{total !== 1 ? 's' : ''} found</span>
        {#if pages > 1}
          <span class="pagination-info">Page {page} of {pages}</span>
        {/if}
      </div>

      {#if results.length === 0}
        <p style="color:var(--text-dim); padding: 1rem 0;">No games match your filters.</p>
      {:else}
        <div class="results-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Game</th>
                <th>Year</th>
                <th>Rating</th>
                <th>Weight</th>
                <th>Playtime</th>
                <th>Rated by</th>
              </tr>
            </thead>
            <tbody>
              {#each results as game}
                <tr>
                  <td>
                    <a href="https://boardgamegeek.com/boardgame/{game.id}" target="_blank" rel="noopener">{game.name}</a>
                    {#if game.snippet}
                      <div class="desc-result-snippet">{@html highlightWords(game.snippet, descQuery)}</div>
                    {/if}
                  </td>
                  <td>{game.year_published || '—'}</td>
                  <td>{game.average ? game.average.toFixed(1) : '—'}</td>
                  <td>{game.weight ? game.weight.toFixed(1) : '—'}</td>
                  <td>{game.playing_time || '—'}{game.playing_time ? ' min' : ''}</td>
                  <td>{game.users_rated ? game.users_rated.toLocaleString() : '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        {#if pages > 1}
          <div class="pagination">
            <button class="btn btn-secondary" disabled={page <= 1} on:click={() => search(page - 1)}>Prev</button>
            <span>Page {page} of {pages}</span>
            <button class="btn btn-secondary" disabled={page >= pages} on:click={() => search(page + 1)}>Next</button>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .search-filters {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .filter-row {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .filter-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
  }

  .pagination-info {
    color: var(--text-dim);
    font-size: 0.85rem;
  }

  .results-table-wrap {
    overflow-x: auto;
  }

  .tag-picker .dropdown {
    z-index: 100;
  }

  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    margin-top: 1rem;
    font-size: 0.85rem;
  }
</style>
