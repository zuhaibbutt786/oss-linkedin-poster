const searchBtn = document.getElementById('searchBtn');
const searchQuery = document.getElementById('searchQuery');
const languageSelect = document.getElementById('language');
const sortBySelect = document.getElementById('sortBy');
const projectsEl = document.getElementById('projects');
const statusEl = document.getElementById('status');
const postText = document.getElementById('postText');
const copyBtn = document.getElementById('copyBtn');
const shareLink = document.getElementById('shareLink');

let selectedRepo = null;

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return n.toString();
}

function buildQuery() {
  let q = searchQuery.value.trim() || 'stars:>500';
  const lang = languageSelect.value;
  if (lang) q += ` language:${lang}`;
  return q;
}

async function searchProjects() {
  const q = buildQuery();
  const sort = sortBySelect.value;
  statusEl.textContent = 'Searching GitHub...';
  projectsEl.innerHTML = '';

  const url = `https://api.github.com/search/repositories?q=${encodeURIComponent(q)}&sort=${sort}&order=desc&per_page=12`;

  try {
    const res = await fetch(url, {
      headers: { 'Accept': 'application/vnd.github.v3+json' }
    });

    if (!res.ok) {
      if (res.status === 403) {
        throw new Error('Rate limit exceeded. Try again later.');
      }
      throw new Error(`GitHub API error: ${res.status}`);
    }

    const data = await res.json();
    statusEl.textContent = `Found ${data.total_count.toLocaleString()} repositories (showing top ${data.items.length})`;

    if (!data.items || data.items.length === 0) {
      projectsEl.innerHTML = '<p style="color:var(--muted)">No projects found. Try a different query.</p>';
      return;
    }

    data.items.forEach(repo => {
      const card = document.createElement('article');
      card.className = 'card';
      card.innerHTML = `
        <h3><a href="${repo.html_url}" target="_blank" rel="noopener">${repo.full_name}</a></h3>
        <p class="desc">${repo.description || 'No description'}</p>
        <div class="meta">
          <span>⭐ ${formatNumber(repo.stargazers_count)}</span>
          <span>🍴 ${formatNumber(repo.forks_count)}</span>
          ${repo.language ? `<span>💻 ${repo.language}</span>` : ''}
        </div>
        <div class="actions">
          <button class="btn secondary select-btn">Select for LinkedIn</button>
          <a href="${repo.html_url}" target="_blank" rel="noopener" class="btn primary">View Repo</a>
        </div>
      `;

      card.querySelector('.select-btn').addEventListener('click', () => selectRepo(repo));
      projectsEl.appendChild(card);
    });
  } catch (err) {
    statusEl.textContent = 'Error: ' + err.message;
    console.error(err);
  }
}

function selectRepo(repo) {
  selectedRepo = repo;
  const stars = formatNumber(repo.stargazers_count);
  const text = `This open-source project is quietly changing how people build AI systems.\n\n🚀 ${repo.full_name}\n\n${repo.description || ''}\n\n⭐ ${stars} stars  |  💻 ${repo.language || 'N/A'}\n\n${repo.html_url}\n\n#OpenSource #MachineLearning #AI #DataScience #GenAI #NLP #ComputerVision #BigData #Research`;
  postText.value = text;
  updateShareLink();
  postText.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function updateShareLink() {
  if (!selectedRepo) {
    shareLink.href = 'https://www.linkedin.com/sharing/share-offsite/?url=https://github.com';
    return;
  }
  const url = encodeURIComponent(selectedRepo.html_url);
  shareLink.href = `https://www.linkedin.com/sharing/share-offsite/?url=${url}`;
}

copyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(postText.value);
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy Text'; }, 2000);
  } catch {
    postText.select();
    document.execCommand('copy');
    copyBtn.textContent = 'Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy Text'; }, 2000);
  }
});

shareLink.addEventListener('click', (e) => {
  if (!selectedRepo) {
    e.preventDefault();
    alert('Please select a project first.');
  }
});

searchBtn.addEventListener('click', searchProjects);
searchQuery.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchProjects();
});

searchProjects();
updateShareLink();