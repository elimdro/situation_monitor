const state = {
  view: "overview",
  meta: null,
  overview: null,
  lanes: {},
  filter: "",
  topic: "",
  loading: false,
  error: "",
};

const statusEl = document.getElementById("status");
const navEl = document.getElementById("nav");
const mainEl = document.getElementById("main");
const filterEl = document.getElementById("filter");

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "html") node.innerHTML = value;
    else node.setAttribute(key, value);
  }
  for (const child of children || []) {
    if (child) node.append(child);
  }
  return node;
}

function compact(value) {
  if (value == null || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  if (number < 1000) return String(number);
  if (number < 10000) return `${(number / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  if (number < 1000000) return `${Math.round(number / 1000)}k`;
  return `${(number / 1000000).toFixed(1).replace(/\.0$/, "")}m`;
}

function ago(iso) {
  if (!iso) return "";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

function matches(text) {
  const query = state.filter.trim().toLowerCase();
  if (!query) return true;
  return (text || "").toLowerCase().includes(query);
}

async function getJSON(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function viewId() {
  const hash = location.hash.replace("#", "");
  if (!hash || hash === "overview") return "overview";
  if (state.meta && state.meta.lanes.some((lane) => lane.id === hash)) return hash;
  return "overview";
}

function setStatus(text, live) {
  statusEl.replaceChildren();
  if (live) statusEl.append(el("span", { class: "live" }));
  statusEl.append(document.createTextNode(text));
}

function renderNav() {
  const lanes = [{ id: "overview", title: "Overview", accent: "#7aa2f7" }].concat(
    (state.meta && state.meta.lanes) || (state.overview && state.overview.lanes) || [],
  );
  const counts = {};
  for (const lane of (state.overview && state.overview.lanes) || []) {
    counts[lane.id] = lane.trend_count;
  }
  navEl.replaceChildren();
  for (const lane of lanes) {
    const count = counts[lane.id];
    const button = el("button", {
      class: `nav-item${lane.id === state.view ? " active" : ""}`,
      type: "button",
      style: `--accent:${lane.accent || "#7aa2f7"}`,
    }, [
      el("span", { text: lane.title }),
      count ? el("span", { class: "nav-count", text: String(count) }) : null,
    ]);
    button.addEventListener("click", () => {
      location.hash = lane.id;
    });
    navEl.append(button);
  }
}

function warnings(list) {
  if (!list || !list.length) return null;
  return el("div", { class: "banner" }, list.map((item) => el("p", { text: item })));
}

function trendLink(trend) {
  const volume = trend.posts ? compact(trend.posts) : "";
  const name = el("span", {}, [document.createTextNode(trend.name)]);
  if (trend.place) name.append(el("span", { class: "place", text: trend.place }));
  return el("a", { class: "trend", href: trend.url, target: "_blank", rel: "noreferrer" }, [
    el("span", { class: "rank", text: String(trend.rank).padStart(2, "0") }),
    name,
    el("span", { class: "volume", text: volume ? `${volume} posts` : "" }),
  ]);
}

function trendColumn(title, group) {
  const rows = (group.trends || []).filter((trend) => matches(trend.name));
  const panel = el("section", { class: "panel" }, [
    el("h3", { text: title || group.name }),
  ]);
  if (!(group.trends || []).length) {
    panel.append(el("p", { class: "empty", text: "X did not return a trend list." }));
    return panel;
  }
  if (!rows.length) {
    panel.append(el("p", { class: "empty", text: "Nothing in this list matches the filter." }));
    return panel;
  }
  for (const trend of rows) panel.append(trendLink(trend));
  return panel;
}

function avatar(user) {
  if (user.avatar) {
    const image = el("img", { alt: "", src: user.avatar, referrerpolicy: "no-referrer" });
    image.addEventListener("error", () => {
      image.replaceWith(el("span", { class: "fallback", text: (user.name || "?").slice(0, 1) }));
    });
    return image;
  }
  return el("span", { class: "fallback", text: (user.name || "?").slice(0, 1) });
}

function postCard(post, maxScore) {
  const metrics = post.metrics || {};
  const bits = [
    metrics.replies ? `${compact(metrics.replies)} replies` : "",
    metrics.reposts ? `${compact(metrics.reposts)} reposts` : "",
    metrics.likes ? `${compact(metrics.likes)} likes` : "",
    metrics.views ? `${compact(metrics.views)} views` : "",
  ].filter(Boolean);
  const card = el("a", { class: "card", href: post.url, target: "_blank", rel: "noreferrer" }, [
    el("div", { class: "heat" }, [el("span", { style: `--p:${maxScore ? post.score / maxScore : 0}` })]),
    el("div", { class: "who" }, [
      avatar(post.user),
      el("div", {}, [
        el("strong", { text: post.user.name || post.user.screen_name }),
        el("span", { text: `@${post.user.screen_name} · ${ago(post.created_at)}` }),
      ]),
    ]),
    el("p", { class: "clamp", text: post.text }),
    post.media && post.media.preview
      ? el("img", { class: "preview", alt: post.media.title || "", src: post.media.preview, referrerpolicy: "no-referrer" })
      : null,
    el("div", { class: "meta" }, [
      post.media && post.media.type ? el("span", { class: "tag", text: post.media.type }) : null,
      ...bits.map((bit) => el("span", { class: "metric", text: bit })),
    ]),
  ]);
  return card;
}

function renderOverview() {
  const data = state.overview;
  mainEl.style.setProperty("--accent", "#7aa2f7");
  if (!data) {
    mainEl.replaceChildren(el("p", { class: "lede", text: state.error || "Reading the trend lists…" }));
    return;
  }
  const head = el("header", { class: "page-head" }, [
    el("p", { class: "kicker", text: "General" }),
    el("h1", { text: "Trending on X" }),
    el("p", { class: "lede", text: "Worldwide and United States lists, plus posts moving on the public trending timeline." }),
  ]);
  const columns = el("div", { class: "grid" }, [
    trendColumn(data.worldwide.name, data.worldwide),
    trendColumn(data.united_states.name, data.united_states),
  ]);
  const moving = (data.moving || []).filter((post) => matches(`${post.text} ${post.user.name} ${post.user.screen_name}`));
  const maxScore = moving.reduce((best, post) => Math.max(best, post.score || 0), 0);
  const feed = el("div", { class: "posts" }, moving.map((post) => postCard(post, maxScore)));
  mainEl.replaceChildren(...[
    head,
    warnings(data.warnings),
    el("section", { class: "section" }, [el("h2", { text: "Trend lists" }), columns]),
    el("section", { class: "section" }, [
      el("h2", { text: "Moving now" }),
      moving.length ? feed : el("p", { class: "empty", text: "No trending posts matched." }),
    ]),
  ].filter(Boolean));
}

function renderLane() {
  const lane = state.lanes[state.view];
  const meta = (state.meta && state.meta.lanes.find((item) => item.id === state.view)) || { title: state.view, accent: "#7aa2f7" };
  mainEl.style.setProperty("--accent", meta.accent || "#7aa2f7");
  if (!lane) {
    mainEl.replaceChildren(
      el("header", { class: "page-head" }, [
        el("p", { class: "kicker", text: "Lane" }),
        el("h1", { text: meta.title || "Lane" }),
        el("p", { class: "lede", text: state.error || "Reading posts from the accounts in this lane…" }),
      ]),
    );
    return;
  }
  const accounts = el("div", { class: "accounts" });
  for (const account of lane.accounts || []) {
    accounts.append(el("a", { href: account.url, target: "_blank", rel: "noreferrer", text: account.name }));
  }
  const head = el("header", { class: "page-head" }, [
    el("p", { class: "kicker", text: "Field" }),
    el("h1", { text: lane.title }),
    el("p", { class: "lede", text: lane.summary }),
    accounts,
  ]);
  const sections = [head, warnings(lane.warnings)];

  const topics = (lane.topics || []).filter((topic) => matches(topic.label));
  if (topics.length) {
    const chips = el("div", { class: "chips" });
    for (const topic of topics) {
      const chip = el("button", {
        class: `chip${state.topic === topic.label ? " on" : ""}`,
        type: "button",
      }, [
        document.createTextNode(topic.label),
        el("b", { text: String(topic.count) }),
      ]);
      chip.addEventListener("click", () => {
        state.topic = state.topic === topic.label ? "" : topic.label;
        filterEl.value = state.topic.replace(/^#/, "");
        state.filter = filterEl.value;
        renderMain();
      });
      chips.append(chip);
    }
    sections.push(el("section", { class: "section" }, [el("h2", { text: "Repeated here" }), chips]));
  }

  const trends = (lane.trends || []).filter((trend) => matches(trend.name));
  if (trends.length) {
    const panel = el("section", { class: "panel" });
    for (const trend of trends) panel.append(trendLink(trend));
    sections.push(el("section", { class: "section" }, [el("h2", { text: "Also on the trend list" }), panel]));
  }

  if (lane.news && lane.news.length) {
    const stories = el("div", { class: "stories" });
    for (const story of lane.news.filter((item) => matches(`${item.title} ${item.hook} ${item.summary}`))) {
      stories.append(el("a", { class: "card", href: story.url, target: "_blank", rel: "noreferrer" }, [
        story.category ? el("div", { class: "tag", text: story.category }) : null,
        el("strong", { text: story.title }),
        story.hook ? el("p", { class: "hook", text: story.hook }) : null,
        story.summary ? el("p", { class: "summary clamp", text: story.summary }) : null,
        el("div", { class: "meta" }, [el("span", { class: "when", text: ago(story.updated_at) })]),
      ]));
    }
    if (stories.childNodes.length) {
      sections.push(el("section", { class: "section" }, [el("h2", { text: "X News" }), stories]));
    }
  }

  const posts = (lane.posts || []).filter((post) => {
    const blob = `${post.text} ${post.user.name} ${post.user.screen_name} ${(post.hashtags || []).join(" ")}`;
    return matches(blob);
  });
  const maxScore = posts.reduce((best, post) => Math.max(best, post.score || 0), 0);
  sections.push(el("section", { class: "section" }, [
    el("h2", { text: `Heating up · last ${lane.window_days} days` }),
    posts.length
      ? el("div", { class: "posts" }, posts.map((post) => postCard(post, maxScore)))
      : el("p", { class: "empty", text: "No posts matched. Refresh, or clear the filter." }),
  ]));
  mainEl.replaceChildren(...sections.filter(Boolean));
}

function renderMain() {
  if (state.view === "overview") renderOverview();
  else renderLane();
}

function paintStatus() {
  const payload = state.view === "overview" ? state.overview : state.lanes[state.view];
  if (state.loading && !payload) {
    setStatus("Reading X…", false);
    return;
  }
  if (state.error && !payload) {
    setStatus(state.error, false);
    return;
  }
  if (!payload) {
    setStatus("Ready", false);
    return;
  }
  const when = ago(payload.fetched_at);
  const source = payload.official ? "X API + public timelines" : "Public X timelines";
  const cache = payload.cached ? " · cached" : "";
  setStatus(`${source} · updated ${when}${cache}`, true);
}

async function load(fresh) {
  state.loading = true;
  state.error = "";
  paintStatus();
  renderMain();
  const query = fresh ? "?fresh=1" : "";
  try {
    if (state.view === "overview") {
      state.overview = await getJSON(`/api/overview${query}`);
    } else {
      state.lanes[state.view] = await getJSON(`/api/lanes/${state.view}${query}`);
      if (!state.overview) state.overview = await getJSON("/api/overview");
    }
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loading = false;
    renderNav();
    renderMain();
    paintStatus();
  }
}

async function show(id) {
  state.view = id;
  state.topic = "";
  renderNav();
  const cached = id === "overview" ? state.overview : state.lanes[id];
  if (!cached) await load(false);
  else {
    renderMain();
    paintStatus();
  }
}

filterEl.addEventListener("input", () => {
  state.filter = filterEl.value;
  state.topic = "";
  renderMain();
});
document.getElementById("refresh").addEventListener("click", () => load(true));
document.addEventListener("keydown", (event) => {
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") {
    if (event.key === "Escape") filterEl.blur();
    return;
  }
  if (event.key === "/") {
    event.preventDefault();
    filterEl.focus();
  } else if (event.key === "r" || event.key === "R") {
    load(true);
  }
});
window.addEventListener("hashchange", () => {
  const id = viewId();
  if (id !== state.view) show(id);
});

getJSON("/api/meta").then((meta) => {
  state.meta = meta;
  renderNav();
  show(viewId());
}).catch((error) => {
  state.error = error.message;
  renderMain();
  paintStatus();
});

setInterval(() => {
  if (!state.loading && document.visibilityState === "visible") load(false);
}, 180000);
