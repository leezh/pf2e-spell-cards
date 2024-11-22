const COPYRIGHT_HOLDERS = {
  "Pathfinder Player Core": "&copy; 2023 Paizo Inc.",
  "Pathfinder Player Core 2": "&copy; 2024 Paizo Inc.",
};

function createCheckbox(id, name, callback) {
  const group = document.createElement("div");
  const input = document.createElement("input");
  const label = document.createElement("label");
  input.type = "checkbox";
  input.id = id;
  input.addEventListener("change", callback);
  label.innerHTML = name;
  label.htmlFor = id;
  group.append(input);
  group.append(label);
  return [group, input];
}

function createFilter(title, set, prefix, callback, names) {
  names = names || {};
  const container = document.createElement("div");
  container.innerHTML = `<h3>${title}</h3>`;
  const values =
    typeof [...set][0] != "number"
      ? [...set].sort()
      : [...set].sort((a, b) => a - b);
  const inputs = new Array();

  const [allGroup, allInput] = createCheckbox(prefix + "All", "Any");
  container.append(allGroup);

  for (let value of values) {
    const name = names[value] || value;
    const [group, input] = createCheckbox(prefix + value, name, () => {
      if (input.checked) {
        if (allInput.checked) {
          values.forEach((v) => set.delete(v));
        }
        set.add(value);
        allInput.checked = false;
      } else {
        set.delete(value);
      }
      callback();
    });
    inputs.push(input);
    container.append(group);
  }

  allInput.checked = true;
  allInput.addEventListener("change", () => {
    for (let input of inputs) input.checked = false;
    if (allInput.checked) values.forEach((v) => set.add(v));
    else set.clear();
    callback();
  });
  return container;
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
  const filters = document.getElementById("filters");
  const container = document.getElementById("main");
  const hideUnpinned = document.getElementById("hideUnpinned");
  const print = document.getElementById("print");
  const response = await fetch("data.json");
  const data = await response.json();
  const cards = {};
  const typeFilter = new Set();
  const levelFilter = new Set();
  const rarityFilter = new Set();
  const traditionFilter = new Set();
  const traitsFilter = new Set();
  const sourceFilter = new Set();

  for (let cardId in data) {
    const entry = data[cardId];
    if (entry.traditions.length === 0) entry.traditions = [""];
    typeFilter.add(entry.type);
    levelFilter.add(entry.level);
    rarityFilter.add(entry.rarity);
    sourceFilter.add(entry.source);
    entry.traditions = new Set(entry.traditions);
    entry.traditions.forEach((c) => traditionFilter.add(c));
    entry.traits = new Set(entry.traits);
    entry.traits.forEach((c) => traitsFilter.add(c));
    cards[cardId] = [];

    for (let i = 0; i < entry.description.length; i++) {
      const card = document.createElement("div");
      card.classList.add("card");
      card.classList.add("card-" + (i + 1));
      card.classList.add(cardId);

      const title = document.createElement("div");
      title.classList.add("title");
      title.innerText = entry.title;
      if (i == 0) {
        const type = document.createElement("span");
        type.classList.add("type");
        type.innerText = `${entry.type} ${entry.level}`;
        title.prepend(type, " ");

        const actions = document.createElement("span");
        actions.classList.add("actions");
        actions.innerHTML = addIcons(entry.actions);
        title.append(" ", actions);
      }
      if (entry.description.length > 1) {
        const pageNumber = document.createElement("span");
        pageNumber.classList.add("page");
        pageNumber.innerHTML = `(${i + 1}/${entry.description.length})`;
        title.append(" ", pageNumber);
      }
      card.append(title);

      if (i == 0) {
        const traits = document.createElement("div");
        traits.classList.add("traits");

        if (entry.rarity != "common") {
          const rarity = document.createElement("div");
          rarity.classList.add("rarity");
          rarity.classList.add(entry.rarity);
          rarity.innerText = entry.rarity;
          traits.append(rarity);
        }

        for (let name of entry.traits) {
          const trait = document.createElement("div");
          trait.innerText = name;
          traits.append(trait);
        }

        card.append(traits);
      }

      const description = document.createElement("div");
      description.classList.add("description");
      description.innerHTML = addIcons(entry.description[i]);
      card.append(description);

      const copyrightHolder = COPYRIGHT_HOLDERS[entry.source] || "";
      const copyright = document.createElement("div");
      copyright.classList.add("copyright");
      copyright.innerHTML = entry.source + " " + copyrightHolder;
      card.append(copyright);

      card.style.display = "";
      card.addEventListener("click", () => {
        for (let card of cards[cardId]) {
          card.classList.toggle("pinned");
        }
      });
      cards[cardId].push(card);
      container.appendChild(card);

      if (description.clientHeight < description.scrollHeight) {
        console.log("overflow detected: " + entry.source + ": " + entry.title + " #" + (i + 1));
      }
    }
  }

  function updateCards() {
    for (let cardId in data) {
      const entry = data[cardId];
      let visible = !hideUnpinned.checked;
      if (traditionFilter.isDisjointFrom(entry.traditions)) visible = false;
      if (traitsFilter.isDisjointFrom(entry.traits)) visible = false;
      if (!typeFilter.has(entry.type)) visible = false;
      if (!levelFilter.has(entry.level)) visible = false;
      if (!rarityFilter.has(entry.rarity)) visible = false;
      if (!sourceFilter.has(entry.source)) visible = false;

      for (let card of cards[cardId]) {
        card.style.display =
          card.classList.contains("pinned") || visible ? "" : "none";
      }
    }
  }

  filters.append(createFilter("Type", typeFilter, "type", updateCards));
  filters.append(
    createFilter("Levels", levelFilter, "level", updateCards, {
      1: "Level 1",
      2: "Level 2",
      3: "Level 3",
      4: "Level 4",
      5: "Level 5",
      6: "Level 6",
      7: "Level 7",
      8: "Level 8",
      9: "Level 9",
      10: "Level 10",
    }),
  );
  filters.append(createFilter("Rarity", rarityFilter, "rarity", updateCards));
  filters.append(
    createFilter("Tradition", traditionFilter, "tradition", updateCards, {
      "": "No Tradition",
    }),
  );
  filters.append(createFilter("Traits", traitsFilter, "traits", updateCards));
  filters.append(createFilter("Source", sourceFilter, "source", updateCards));

  hideUnpinned.addEventListener("change", () => updateCards());
  print.addEventListener("click", () => window.print());
  updateCards();
});
