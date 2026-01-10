function createCheckbox(parent, id, name) {
  const group = document.createElement("div");
  const input = document.createElement("input");
  const label = document.createElement("label");
  input.type = "checkbox";
  input.id = id;
  label.innerHTML = name;
  label.htmlFor = id;
  group.append(input);
  group.append(label);
  parent.append(group);
  return input;
}

function createFilter(parent, title, mapping, callback) {
  const container = document.createElement("div");
  container.innerHTML = `<h3>${title}</h3>`;
  const inputs = [];
  const set = new Set();

  const allInput = createCheckbox(container, title + "All", "Any");
  const names = Array.isArray(mapping) ? mapping : Object.keys(mapping);
  for (let name of names) {
    const value = Array.isArray(mapping) ? name : mapping[name];
    const input = createCheckbox(container,title + value, name);
    input.addEventListener("change", () => {
      if (input.checked) {
        if (allInput.checked) {
          set.clear();
        }
        set.add(value);
        allInput.checked = false;
      } else {
        set.delete(value);
      }
      callback();
    });
    inputs.push(input);
    set.add(value);
  }

  const values = Array.isArray(mapping) ? mapping : Object.values(mapping);
  allInput.checked = true;
  allInput.addEventListener("change", () => {
    for (let input of inputs) input.checked = false;
    if (allInput.checked) values.forEach((v) => set.add(v));
    else set.clear();
    callback();
  });

  parent.append(container);

  return function (entry) {
    const value = entry[title.toLowerCase()];
    if (Array.isArray(value)) {
      return value.find((v) => set.has(v)) !== undefined;
    }
    return set.has(value);
  }
}

function addIcons(text) {
  const actions = [
    "one-action",
    "two-actions",
    "three-actions",
    "reaction",
    "free-action",
  ];
  for (let action of actions) {
    text = text.replaceAll(
      `[${action}]`,
      `<img class="action" src="icons/${action}.svg" alt="[${action}]"/>`,
    );
  }
  return text;
}

document.addEventListener("DOMContentLoaded", async function () {
  const response = await fetch("data.json");
  const data = await response.json();

  const container = document.getElementById("main");
  const remastered = document.getElementById("remastered");
  const hideUnpinned = document.getElementById("hideUnpinned");
  const filterContainer = document.getElementById("filters");
  const print = document.getElementById("print");
  const cards = {};
  const filters = [];

  function updateCards() {
    if (Object.keys(cards).length === 0) return;
    for (let entry of data.spells) {
      const visible = !hideUnpinned.checked && filters.every((f) => f(entry));
      for (let card of cards[entry.id]) {
        card.style.display =
          card.classList.contains("pinned") || visible ? "" : "none";
      }
    }
  }

  function updateFilters() {
    while (filters.length) filters.pop();
    filterContainer.innerHTML = "";
    const filterGroups = {...data.filters, ...(remastered.checked ? data.remaster : data.legacy)}
    for (let title of Object.keys(filterGroups)) {
      filters.push(createFilter(filterContainer, title, filterGroups[title], updateCards));
    }
    updateCards();
  }

  updateFilters();
  remastered.addEventListener("change", () => updateFilters());
  hideUnpinned.addEventListener("change", () => updateCards());
  print.addEventListener("click", () => window.print());

  for (let entry of data.spells) {
    if (entry.traditions.length === 0) entry.traditions = ["No Tradition"];
    cards[entry.id] = [];
    let page = 0;
    const titles = [];
    const content = document.createElement("div");
    content.innerHTML = addIcons(entry.description);

    while (content.childNodes.length > 0) {
      const card = document.createElement("div");
      card.classList.add("card");
      card.classList.add(`card-${page + 1}`);
      card.classList.add(entry.id);

      const inner = document.createElement("div");
      card.append(inner);

      const title = document.createElement("div");
      title.classList.add("title");
      title.innerText = entry.title;
      if (page === 0) {
        const type = document.createElement("span");
        type.classList.add("type");
        type.append(`${entry.type} ${entry.level}`);
        title.prepend(type, " ");

        const actions = document.createElement("span");
        actions.classList.add("actions");
        actions.innerHTML = addIcons(entry.actions);
        title.append(" ", actions);
      }
      inner.append(title);
      titles.push(title);

      if (page === 0) {
        const traits = document.createElement("div");
        traits.classList.add("traits");

        if (entry.rarity !== "Common") {
          const rarity = document.createElement("div");
          rarity.classList.add("rarity");
          rarity.classList.add(entry.rarity.toLowerCase());
          rarity.append(entry.rarity);
          traits.append(rarity);
        }

        for (let name of entry.traits) {
          const trait = document.createElement("div");
          trait.classList.add(`trait-${name.replaceAll(" ", "-").toLowerCase()}`);
          trait.append(name)
          traits.append(trait);
        }

        inner.append(traits);
      }

      const description = document.createElement("div");
      description.classList.add("description");
      inner.append(description);

      const copyright = document.createElement("div");
      copyright.classList.add("copyright");
      copyright.append(`${entry.source} \u00A9 ${entry.copyright}`);
      inner.append(copyright);

      card.addEventListener("click", () => {
        for (let card of cards[entry.id]) {
          card.classList.toggle("pinned");
        }
      });
      cards[entry.id].push(card);
      container.append(card);

      description.append(...content.childNodes);
      while (description.childNodes.length > 1 && description.clientHeight < description.scrollHeight) {
        content.prepend(description.lastElementChild);
      }
      page++;
    }
    if (page > 1) {
      for (let i = 0; i < page; i++) {
          const pageNumber = document.createElement("span");
          pageNumber.classList.add("page");
          pageNumber.append(`(${i + 1}/${page})`);
          titles[i].append(" ", pageNumber);
      }
    }
  }

  updateCards();
});
