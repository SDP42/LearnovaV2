/**
 * Ready-made lessons. Each opens the Create screen pre-filled with real,
 * complete source content — pick one, hit generate, get a deck. They double as
 * a showcase of what the engine does with each kind of material.
 *
 * `kind` drives the accent + icon. `minutes` is a rough generated-deck length.
 */

export const TEMPLATE_KINDS = {
  process: { label: "Process", hint: "Ordered steps → flowchart, revealed one at a time" },
  worked: { label: "Worked example", hint: "A problem solved line by line" },
  compare: { label: "Comparison", hint: "Two things across the same aspects → table" },
  data: { label: "Data", hint: "Numbers over categories → chart" },
  concept: { label: "Concept", hint: "Definitions kept exact, ideas as a map" },
  timeline: { label: "Timeline", hint: "Dated events → animated timeline" },
};

export const TEMPLATES = [
  {
    id: "ml-workflow",
    kind: "process",
    title: "The Machine Learning Workflow",
    blurb: "Seven stages from framing a problem to shipping a model, with the pitfalls at each step.",
    minutes: 6,
    topic: "The Machine Learning Workflow",
    text: `## The Machine Learning Workflow

1. Frame the problem: decide what you are predicting and what a good answer looks like, because the metric you choose shapes every later decision.
2. Collect and label a dataset that reflects the real conditions the model will run in, since a model can only learn from what it is shown.
3. Split the data into training, validation and test sets before doing anything else, so that you never tune against data you later evaluate on.
4. Choose a model family and a loss function that match the problem type — classification, regression or ranking.
5. Train the model, then tune the hyperparameters on the validation set while watching for over- and under-fitting.
6. Evaluate once on the held-out test set. This number is your honest estimate of real-world performance.
7. If performance is poor, gather more or better data, or change the model, then repeat from step 2 — never from step 6.

## Common Pitfalls
- Data leakage: information from the test set influences training, so the score looks great and production does not.
- Optimising on the test set: every peek at the test score and adjustment afterwards inflates your estimate.
- Ignoring class imbalance: 99% accuracy is meaningless when 99% of examples are one class.`,
  },
  {
    id: "solve-linear",
    kind: "worked",
    title: "Solving a Linear Equation",
    blurb: "2x + 3 = 11, step by step, with the reason for every move.",
    minutes: 4,
    topic: "Solving a Linear Equation",
    text: `## Solve 2x + 3 = 11

Start with the equation as given: 2x + 3 = 11.
Subtract 3 from both sides so the variable term is alone: 2x = 8.
Divide both sides by 2, the coefficient of x: x = 4.
Check by substituting back: 2(4) + 3 = 8 + 3 = 11, which matches, so x = 4 is correct.

## Why each step works
Subtracting the same amount from both sides keeps the equation balanced.
Dividing both sides by the same non-zero number keeps it balanced too.
Checking is not optional — it catches arithmetic slips before they cost marks.`,
  },
  {
    id: "sql-vs-nosql",
    kind: "compare",
    title: "SQL vs NoSQL Databases",
    blurb: "When a fixed schema and strong consistency win, and when flexibility and scale win.",
    minutes: 5,
    topic: "SQL vs NoSQL Databases",
    text: `## SQL vs NoSQL

SQL databases use a fixed schema defined up front, guarantee ACID transactions, scale vertically by adding power to one machine, and suit structured data with complex relationships and queries.
NoSQL databases use a flexible or schema-less model, favour eventual consistency, scale horizontally across many machines, and suit large volumes of unstructured or rapidly changing data.

## Choosing between them
- Choose SQL when correctness and complex joins matter more than raw write throughput — banking, inventory, reporting.
- Choose NoSQL when you need to absorb a firehose of writes or the shape of the data keeps changing — event logs, user activity, product catalogues.
- Many real systems use both: a relational store for the source of truth and a document or key-value store for scale and speed.`,
  },
  {
    id: "energy-mix",
    kind: "data",
    title: "Global Electricity by Source",
    blurb: "The world's power mix as a chart, plus what wind actually trades off.",
    minutes: 5,
    topic: "Renewable Energy Mix",
    text: `## Global Electricity by Source
Coal supplies 36 percent of world electricity, natural gas 23 percent, hydro 15 percent, nuclear 10 percent, wind 7 percent, solar 5 percent, and other renewables 4 percent.

## Advantages and Drawbacks of Wind
- An advantage is that wind is free and effectively inexhaustible.
- A benefit is zero direct emissions while the turbine is running.
- A drawback is that output is intermittent and cannot be dispatched on demand.
- A limitation is the visual and noise impact on nearby communities, which slows planning approval.`,
  },
  {
    id: "thermo-basics",
    kind: "concept",
    title: "Thermodynamics: Key Definitions",
    blurb: "The laws stated precisely and kept verbatim, then heat engines in plain terms.",
    minutes: 5,
    topic: "Thermodynamics Basics",
    text: `## Key Definitions
Entropy is defined as a measure of the number of microscopic configurations that correspond to a thermodynamic system's macroscopic state.
The first law of thermodynamics states that energy cannot be created or destroyed, only transferred or converted from one form to another.
The second law of thermodynamics states that the total entropy of an isolated system can never decrease over time.

## Heat Engines
A heat engine converts thermal energy into mechanical work by exploiting a temperature difference between a hot reservoir and a cold reservoir.
No heat engine can be perfectly efficient, because some energy must always be rejected to the cold reservoir to satisfy the second law.`,
  },
  {
    id: "internet-history",
    kind: "timeline",
    title: "A Short History of the Internet",
    blurb: "Six milestones from ARPANET to mobile-first, and why each one mattered.",
    minutes: 5,
    topic: "A Short History of the Internet",
    text: `## Key Milestones
- 1969: ARPANET connects its first four university nodes, proving that packet switching works.
- 1983: ARPANET adopts TCP/IP on the same day across the network, the moment the modern internet begins.
- 1989: Tim Berners-Lee proposes the World Wide Web at CERN as a way to link documents across machines.
- 1993: the Mosaic browser adds inline images and a friendly interface, bringing the web to a general audience.
- 2004: social platforms shift the web from pages you read to content you create.
- 2007: the smartphone puts the internet in a pocket and makes mobile the default way most people connect.

## Why it matters
Each step lowered the barrier to being online, moving the network from a research tool to everyday infrastructure that billions depend on.`,
  },
  {
    id: "photosynthesis",
    kind: "process",
    title: "Photosynthesis, Stage by Stage",
    blurb: "Light reactions and the Calvin cycle, with the role each molecule plays.",
    minutes: 6,
    topic: "Photosynthesis",
    text: `## Photosynthesis

1. Light absorption: chlorophyll pigments in the thylakoid membranes capture photons and become excited.
2. Water photolysis: the energy splits water molecules, releasing oxygen as a by-product and supplying electrons.
3. The electron transport chain uses those electrons to pump protons and generate ATP and NADPH.
4. Carbon fixation: in the Calvin cycle, the enzyme Rubisco attaches carbon dioxide to a five-carbon sugar.
5. Reduction: ATP and NADPH from the light reactions convert the fixed carbon into a three-carbon sugar.
6. Regeneration: most of that sugar is recycled to keep the cycle running; the rest becomes glucose.

## Limiting factors
Temperature above about 35 degrees Celsius lowers net efficiency through photorespiration.
Under drought, stomata close to save water, which also cuts off the carbon dioxide supply and reduces yield.`,
  },
  {
    id: "supply-demand",
    kind: "concept",
    title: "Supply and Demand",
    blurb: "The two curves, what shifts them, and how a market finds its price.",
    minutes: 5,
    topic: "Supply and Demand",
    text: `## The Two Forces
The demand curve slopes downward: as price falls, buyers are willing to purchase more.
The supply curve slopes upward: as price rises, sellers are willing to produce more.
The market equilibrium is the price at which the quantity demanded equals the quantity supplied.

## What Shifts Each Curve
- Demand shifts with income, tastes, the price of substitutes, and expectations about the future.
- Supply shifts with input costs, technology, taxes, and the number of sellers in the market.
- A shift in either curve moves the equilibrium price and quantity in a predictable direction.`,
  },
  {
    id: "bubble-sort",
    kind: "worked",
    title: "Bubble Sort, Traced",
    blurb: "Sorting [5, 1, 4, 2] one comparison at a time.",
    minutes: 4,
    topic: "Bubble Sort",
    text: `## Bubble Sort on [5, 1, 4, 2]

Compare 5 and 1: 5 is larger, so swap. The list is now [1, 5, 4, 2].
Compare 5 and 4: 5 is larger, so swap. The list is now [1, 4, 5, 2].
Compare 5 and 2: 5 is larger, so swap. The list is now [1, 4, 2, 5]. The largest value has bubbled to the end.
Start again: compare 1 and 4, no swap. Compare 4 and 2, swap. The list is now [1, 2, 4, 5].
One more pass makes no swaps, so the list is sorted.

## Cost
Each pass makes n comparisons and there can be up to n passes, so bubble sort is O(n squared) in the worst case.
It is rarely used in practice but it is the clearest first example of how a sort works.`,
  },
  {
    id: "cell-respiration",
    kind: "compare",
    title: "Aerobic vs Anaerobic Respiration",
    blurb: "Same goal — release energy — very different yield and by-products.",
    minutes: 4,
    topic: "Cellular Respiration",
    text: `## Aerobic vs Anaerobic Respiration

Aerobic respiration uses oxygen, takes place mainly in the mitochondria, fully breaks glucose down to carbon dioxide and water, and yields about 30 to 32 ATP per glucose molecule.
Anaerobic respiration runs without oxygen, takes place in the cytoplasm, only partially breaks glucose down, and yields just 2 ATP per glucose molecule.

## By-products
- In animals, anaerobic respiration produces lactic acid, which builds up during hard exercise.
- In yeast and plants, it produces ethanol and carbon dioxide, the basis of brewing and baking.`,
  },
  {
    id: "climate-drivers",
    kind: "data",
    title: "Sources of Global Greenhouse Emissions",
    blurb: "Which sectors emit the most, as a chart, and the one lever that matters most.",
    minutes: 4,
    topic: "Greenhouse Gas Emissions by Sector",
    text: `## Global Emissions by Sector
Energy use in industry accounts for about 24 percent of emissions, transport 16 percent, buildings 18 percent, agriculture and land use 18 percent, direct industrial processes 5 percent, and other energy 19 percent.

## The Common Thread
Most of these figures trace back to burning fossil fuels for energy.
Decarbonising electricity generation and then electrifying transport and heating addresses the largest share of the problem.`,
  },
  {
    id: "scientific-method",
    kind: "process",
    title: "The Scientific Method",
    blurb: "From observation to conclusion, and why it loops rather than ends.",
    minutes: 4,
    topic: "The Scientific Method",
    text: `## The Scientific Method

1. Observe something in the world that is not fully explained.
2. Ask a specific, answerable question about that observation.
3. Form a hypothesis: a testable, falsifiable statement about what is happening.
4. Design an experiment that would produce different results depending on whether the hypothesis is true.
5. Collect data carefully, controlling the variables you are not testing.
6. Analyse the results and decide whether they support or contradict the hypothesis.
7. Report what you found so others can check it, then refine the question and go again.

## Why it loops
A single experiment rarely settles anything. Confidence grows only when a result holds up across many independent tests.`,
  },
];

export const templatesByKind = (kind) =>
  kind === "all" ? TEMPLATES : TEMPLATES.filter((t) => t.kind === kind);
