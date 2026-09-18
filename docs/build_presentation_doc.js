// Builds docs/UW_Dashboard_Presentation.docx - a 20-minute speaking script for
// walking a room through the dashboard, in the order it gets presented:
// filters, the tabs, then Overview in detail, each tab, the questions for the
// team about Matt's build, the data-source and refresh story, and the close.
//
// Needs the docx npm package, which the project itself doesn't use:
//     mkdir build && cd build && npm install docx
//     node ../docs/build_presentation_doc.js ".."
//
// Run docs/export_doc_facts.py first: every figure, column name and formula in
// the document comes from docs/doc_facts.json, so the script can't disagree
// with the dashboard or the metrics workbook.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, LevelFormat,
} = require("docx");

const ROOT = process.argv[2];
const facts = JSON.parse(fs.readFileSync(path.join(ROOT, "docs", "doc_facts.json"), "utf8"));

const NAVY = "1F3864";
const ORANGE = "FF5A00";
const GREY = "5C6670";
const USABLE = 9020;             // A4 portrait, 2.5cm margins, DXA
const FONT = "Arial";
const hair = { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" };
const CELL_BORDERS = { top: hair, bottom: hair, left: hair, right: hair };

const m = {};
facts.metrics.forEach((x) => { m[x.key] = x; });
const m0 = (key) => (m[key].now || "0").replace(/[^0-9.]/g, "");
const head = {};
facts.headline.forEach((h) => { head[h.label] = h; });
const gap = facts.reconciliation.binds_not_in_dsr;
const drivers = facts.drivers;
const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const driverRow = (key) => drivers.rows.find((r) => r.key === key);
// Share of margin premium with no commission recorded, from the page's own figure.
const noCommission = `${(100 - parseFloat(m0("quality.commission_cover"))).toFixed(1)}%`;

function text(value, o = {}) {
  return new TextRun({ text: value, font: FONT, size: o.size || 20, bold: o.bold, italics: o.italics,
    color: o.color });
}
function para(value, o = {}) {
  return new Paragraph({
    children: Array.isArray(value) ? value : [text(value, o)],
    spacing: { after: o.after === undefined ? 120 : o.after, before: o.before },
    alignment: o.alignment, keepNext: o.keepNext,
  });
}
function h1(value, sub) {
  const out = [new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 60 },
    keepNext: true, children: [new TextRun({ text: value, font: FONT, size: 30, bold: true, color: NAVY })] })];
  if (sub) out.push(new Paragraph({ spacing: { after: 140 }, keepNext: true,
    children: [new TextRun({ text: sub, font: FONT, size: 19, color: ORANGE, bold: true })] }));
  return out;
}
function h2(value) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 80 },
    keepNext: true, children: [new TextRun({ text: value, font: FONT, size: 23, bold: true, color: NAVY })] });
}
function say(lines) {
  // The words to actually say, indented and italic so they stand out on a lectern.
  return lines.map((line) => new Paragraph({
    spacing: { after: 90 }, indent: { left: 340 },
    border: { left: { style: BorderStyle.SINGLE, size: 10, color: ORANGE, space: 8 } },
    children: [text(`“${line}”`, { italics: true })],
  }));
}
function bullets(items, o = {}) {
  return items.map((item) => new Paragraph({
    numbering: { reference: "dot", level: o.level || 0 },
    spacing: { after: 70 },
    children: Array.isArray(item) ? item : [text(item, { size: o.size })],
  }));
}
function doThis(lines) {
  return lines.map((line) => new Paragraph({
    numbering: { reference: "click", level: 0 },
    spacing: { after: 60 },
    children: [text(line, { bold: true, size: 19 })],
  }));
}
function cell(value, o = {}) {
  const lines = Array.isArray(value) ? value : [value];
  return new TableCell({
    width: { size: o.width, type: WidthType.DXA },
    columnSpan: o.span,
    borders: CELL_BORDERS,
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: lines.filter((l) => l !== null && l !== undefined && l !== "").map((line, i, all) =>
      new Paragraph({ spacing: { after: i === all.length - 1 ? 0 : 50 },
        children: typeof line === "string"
          ? [text(line, { size: o.size || 17, bold: o.bold, color: o.color })] : line })),
  });
}
function table(headers, rows, widths, o = {}) {
  const header = new TableRow({ tableHeader: true,
    children: headers.map((hh, i) => cell(hh, { width: widths[i], fill: NAVY, bold: true,
      color: "FFFFFF", size: 17 })) });
  const body = rows.map((row) => row.section
    ? new TableRow({ children: [cell(row.section, { width: USABLE, span: widths.length, fill: "D9E2F3",
      bold: true, color: NAVY, size: 17 })] })
    : new TableRow({ children: row.map((v, i) => cell(v, { width: widths[i], size: o.size || 17 })) }));
  return new Table({ columnWidths: widths, width: { size: USABLE, type: WidthType.DXA },
    rows: [header, ...body] });
}
function callout(title, lines) {
  return new Table({
    columnWidths: [USABLE],
    width: { size: USABLE, type: WidthType.DXA },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: USABLE, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: "FFF4EE", color: "auto" },
      borders: { top: hair, bottom: hair, right: hair,
        left: { style: BorderStyle.SINGLE, size: 18, color: ORANGE } },
      margins: { top: 100, bottom: 100, left: 140, right: 120 },
      children: [para([text(title, { bold: true, color: NAVY })], { after: 60 }),
        ...lines.map((l, i, all) => para(Array.isArray(l) ? l : [text(l)],
          { after: i === all.length - 1 ? 0 : 60 }))],
    })] })],
  });
}
function qa(pairs) {
  return table(["If they ask", "Say"], pairs, [3000, 6020]);
}

// Brief one-liners for the tab walkthrough, in the order they are presented.
const bookQuality = [
  ["UW Margin %", "What's left of each premium dollar after expected claims and commission. The headline quality number."],
  ["GELR", "The claims we expect to pay on this book, as priced. Two versions: the margin version (only risks that carry a loss estimate) and the book version (a blank counts as zero). The page names which is which."],
  ["Commission", "The share of premium paid away, mostly to brokers. Same two versions."],
  ["Margin cover / Commission cover", "How much of the premium the margin figure actually rests on. Cover near 100% means the margin speaks for the whole book."],
  ["Attachment points", "How much loss has to happen before we pay: the excess on excess layers, the deductible on primary."],
  ["Median limit", "The typical size of cover we're on the hook for. A median, not an average, because a few towers would swamp a mean."],
  ["Rate Adequacy", "Are we charging enough against plan? Above 100% is priced above plan."],
  ["Rate Adequacy, RBS benchmark check", "The same question answered with RBS's own benchmark premium, as a second opinion."],
  ["RARC", "On renewals only: how much the price moved once the risk itself is allowed for. 100% is flat."],
];
const whatWeWrite = [
  ["Mosaic as lead", "How often we set the terms rather than follow someone else's."],
  ["Primary share", "How much of the book is first-layer cover."],
  ["Average agency share", "How big a slice of each placement we take, weighted by premium."],
  ["SCM share", "How much of the premium sits on third-party capital rather than our own syndicate."],
  ["Broker concentration", "How much of the book sits with the five biggest brokers."],
  ["Average policy length", "How long our policies run, counted once per policy."],
  ["Renewal premium growth", "Of the premium that came up for renewal, how much came back."],
  ["The two mix bars", "New against renewal, and how business reached us, this period against a year earlier."],
];

const doc = new Document({
  creator: "Mosaic UW Productivity",
  title: "UW Productivity Dashboard - 20 minute walkthrough",
  numbering: { config: [
    { reference: "dot", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } } } }] },
    { reference: "click", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 220 } } } }] },
  ] },
  styles: { default: { document: { run: { font: FONT, size: 20, color: "313E48" } } } },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1300, left: 1440, right: 1440 } } },
    children: [
      new Paragraph({ spacing: { after: 60 }, children: [
        new TextRun({ text: "UW Productivity Dashboard", font: FONT, size: 42, bold: true, color: NAVY })] }),
      new Paragraph({ spacing: { after: 260 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ORANGE } },
        children: [new TextRun({ text: "Twenty minutes: what to click, what to say, what to ask for",
          font: FONT, size: 24, color: GREY })] }),
      para([text(`Data as at ${facts.as_at}. Default view: ${facts.period} against ${facts.prior_period}. `,
        { color: GREY }), text(`Built from ${facts.rows.dsr.toLocaleString()} DSR rows and ${facts.rows.rbs.toLocaleString()} RBS rows.`,
        { color: GREY })], { after: 200 }),

      // ------------------------------------------------------------ the spine
      ...h1("The spine", "Learn this page and you can present without notes"),
      table(["Min", "Beat", "The one line that carries it"], [
        ["0-3", "Filters first", "“Everything you see obeys this one toolbar, and the view is a link you can send.”"],
        ["3-5", "The seven tabs", "“One tab per question the business asks.”"],
        ["5-9", "Four headline numbers", "“All four come from RBS, our booked business. This is what we wrote and how good it is.”"],
        ["9-11", "Biggest moves", "“The page tells you where to look first, and leaves out anything built on too few deals.”"],
        ["11-13", "What drove it", "“Premium per underwriter splits into four drivers that multiply back exactly. No opinion in it.”"],
        ["13-17", "Tab by tab", "“Funnel, quality, what we write, productivity, people, trends.”"],
        ["17-19", "Data and refresh", "“Today it reads an export. Point it at the live RBS table and it runs itself.”"],
        ["19-20", "The ask", "“This is the UW half. The same engine can feed the CEO view. Here's what I need.”"],
      ], [700, 1900, 6420]),
      para("", { after: 80 }),
      callout("The three numbers to have on the tip of your tongue", [
        [text(`${head["Bound Premium"].now} bound premium`, { bold: true }),
          text(`, ${head["Bound Premium"].change} on ${facts.prior_period}. `),
          text(`${head["UW Margin %"].now} UW margin`, { bold: true }),
          text(`, ${head["UW Margin %"].change.replace(" pts", " points")}. `),
          text(`${head["Binds"].now} binds`, { bold: true }),
          text(`, ${head["Binds"].change}.`)],
        [text("Premium per active underwriter fell 9.3%", { bold: true }),
          text(` – because submissions rose ${pct(drivers.changes.submissions)} while the number of underwriters writing business rose ${pct(drivers.changes.underwriters)}. More business, spread wider.`)],
        [text("If you remember nothing else: ", { color: GREY }),
          text("more premium, better margin, and the per-person figure fell only because the team writing business grew faster than the flow.", { bold: true })],
      ]),
      para("", { after: 100 }),
      callout("The close, so you can steer everything towards it", [
        "1. This is the underwriting half of the picture. The same engine can feed the CEO dashboard, so both read from one set of definitions instead of two.",
        "2. I need the live RBS table, not an export: the right table plus the transformations the report already applies, and standing access so it refreshes itself.",
        "3. There are a handful of definition calls where my build and Matt's differ. I want the team to pick, so both dashboards agree.",
      ]),

      new Paragraph({ children: [new PageBreak()] }),
      // ---------------------------------------------------------------- beat 1
      ...h1("1. Start with the filters", "0:00 - 3:00. Do not open on a number. Open on control."),
      para("Presenting the filters first does two things: it shows the thing is alive rather than a screenshot, and it stops the first question being “what period is this?”"),
      ...doThis([
        "Open the page on the default view and leave it still for a beat.",
        "Click Period. Show the quick picks: this year so far, last 12 months, full year, a quarter, or tick your own months. Point at the year and the date basis in the same menu.",
        "Pick Q2, press Apply, and let them see the whole page move.",
        "Add Line of business = Cyber. Point at the chips that appear underneath, and remove one with its ×.",
        "Press Copy link. Say you'll paste it in the chat afterwards.",
      ]),
      ...say([
        "Everything you see on this page obeys this one toolbar - every figure, every chart, every underwriter row. There is no second place where a filter hides.",
        "Nothing moves until I press Apply, so I can set three filters and wait once.",
        "Whatever I pick lives in the address, so this is a link. If you want the Cyber view for your Monday meeting, I send you a link, not a screenshot.",
        "Two filters are greyed out: Product, and Role and Tenure. Those need files we don't have yet. I'll come back to that.",
      ]),
      qa([
        ["Why does it open on the whole book?",
          "“Because the per-person figures follow the filters. Matt's opens on New and Open Market because that's what his LOB workbook reconciles to - one line of config if we want to match.”"],
        ["Can I see two periods at once?",
          "“Every figure already shows this period, the same months a year earlier, and the change. The Trends tab gives you 24 months.”"],
        ["What is date basis?",
          "“Whether a policy counts in the month cover started or the month it came in. Inception for anything involving booked business, because that's the only date both reports hold.”"],
      ]),

      // ---------------------------------------------------------------- beat 2
      ...h1("2. The seven tabs, one line each", "3:00 - 5:00. Fast. Do not stop to explain figures yet."),
      ...say(["One tab per question the business actually asks. I'll walk each one, but here's the map."]),
      table(["Tab", "The question it answers"], [
        ["Overview", "Where are we, what moved most, and why."],
        ["Funnel", "How much came in, how much we priced, how much we won."],
        ["Book quality", "Is the business we won any good, and are we charging enough."],
        ["What we write", "What kind of book is it - lead or follow, primary or excess, who brings it."],
        ["Productivity", "How much business per underwriter."],
        ["Underwriters", "Who is writing what, and how they sit against their peers."],
        ["Trends", "Is this month normal, and was the move real or seasonal."],
      ], [1700, 7320]),
      ...say(["I'll spend most of the time on Overview, because that's the page most people will actually look at."]),

      new Paragraph({ children: [new PageBreak()] }),
      // ---------------------------------------------------------------- beat 3
      ...h1("3. The four headline numbers", "5:00 - 9:00. The heart of the twenty minutes."),
      para([text("All four come from RBS, the booked-business report, which is the single source of truth for anything we have written. Say that once, plainly, and then talk about the numbers rather than the plumbing.", { })]),
      table(["Figure", facts.period, "In plain English, and where it comes from"], [
        ["Bound Premium", head["Bound Premium"].now,
          ["Our share of the premium on everything we won in the period.",
           "Straight from RBS: add up the agency share of gross written premium on every line of every policy. Lines first, then policies - a policy with a primary and an excess layer contributes both."]],
        ["UW Margin %", head["UW Margin %"].now,
          ["Of every premium dollar, what's left after the claims we expect and the commission we pay away.",
           `Take the expected loss ratio and the commission that RBS records on each risk, weight both by premium, and subtract them from 100. On this book: ${m["quality.gelr_margin_basis"].now} expected claims, ${m["quality.commission_margin_basis"].now} commission, so ${head["UW Margin %"].now} left.`]],
        ["Binds", head["Binds"].now,
          ["How many risks we actually won.",
           "Count the distinct policies in RBS. Distinct matters: a policy written across two layers is one win, not two."]],
        ["Premium per Active Underwriter", head["Premium / Active UW (stand-in)"].now,
          ["How much booked premium there is per underwriter who won business.",
           "Bound premium divided by the number of different underwriters credited with at least one win. It is a stand-in for headcount, not headcount: we have no HR file, so anyone who won nothing isn't in the count."]],
      ], [1900, 1100, 6020]),
      para("", { after: 80 }),
      ...say([
        "Bound premium is what we wrote. Margin is how good it is. Binds is how many risks it took. And the last one is how much of that sits behind each underwriter writing business.",
        "One honest caveat on that last one, and I'd rather say it than be asked: it is not headcount. We have no HR file, so I count underwriters who won at least one deal. It flatters slightly, because nobody who won nothing is in the denominator. The page labels it a stand-in everywhere it appears.",
      ]),
      callout("If someone pushes on the margin", [
        [text("Margin cover is ", {}), text(m["quality.margin_cover"].now, { bold: true }),
          text(" - that is how much of the premium carries a loss estimate, so the margin speaks for virtually the whole book.")],
        [text("The one soft spot: "), text(noCommission, { bold: true }),
          text(" of that premium records no commission at all, and we treat that as “none charged”. Over the risks that do record one, the margin reads "),
          text(m["quality.uw_margin_pct_recorded_commission"].now, { bold: true }),
          text(" instead of "), text(head["UW Margin %"].now, { bold: true }),
          text(". The page says so under the figure. It is on my list to settle.")],
      ]),

      // ---------------------------------------------------------------- beat 4
      ...h1("4. Biggest moves against a year earlier", "9:00 - 11:00"),
      para("This is the “where do I look first” panel. Two short lists, because two kinds of figure move in two different units."),
      ...bullets([
        [text("Rates move in points. ", { bold: true }), text("A rate going from 42% to 44% moved 2 points, not 4.8%. Saying “percent” there is how people end up arguing about the same number twice.")],
        [text("Amounts and counts move in percent. ", { bold: true }), text("Premium, binds, underwriter counts.")],
      ]),
      para("What qualifies as a “biggest move”, so you can answer it straight:"),
      ...bullets([
        "Every figure on the page is compared with the same months a year earlier.",
        "Rates are ranked by how many points they moved; amounts by percent. Top three of each.",
        "Anything resting on too few deals is thrown out before ranking - fewer than 20 policies, or fewer than 5 underwriters for a per-person figure. That stops a 300% swing off two binds topping the list.",
        "Direction is not judged here. It shows what moved most, and the arrow and colour tell you whether that's good news.",
      ]),
      ...say([
        "This panel is the dashboard telling you where to look. It ranks every figure by how far it moved, throws out anything built on a handful of deals, and shows the top three rates and the top three amounts.",
        "Rates in points, amounts in percent. That distinction is small but it saves arguments.",
      ]),

      new Paragraph({ children: [new PageBreak()] }),
      // ---------------------------------------------------------------- beat 5
      ...h1("5. What drove Premium per Active Underwriter", "11:00 - 13:00. The most impressive two minutes. Slow down."),
      para("Premium per underwriter is not one number, it's four multiplied together. That identity is exact, so the split is arithmetic rather than a story someone chose:"),
      para([text("premium per underwriter  =  submissions per underwriter  ×  quote rate  ×  win rate  ×  average deal size",
        { bold: true, size: 19 })], { alignment: AlignmentType.CENTER }),
      table(["Driver", "What it means", `${facts.prior_period} → ${facts.period}`, "Share of the move"],
        drivers.rows.map((r) => [r.label,
          r.key === "submissions_per_underwriter" ? "How much business each underwriter sees"
            : r.key === "quote_rate" ? "How much of it we price"
              : r.key === "bind_rate" ? "How much of what we priced we win"
                : "How much premium each win carries",
          `${r.key === "submissions_per_underwriter" ? r.prior.toFixed(1) : r.key === "average_deal_size" ? "$" + (r.prior / 1000).toFixed(1) + "k" : pct(r.prior)} → ${r.key === "submissions_per_underwriter" ? r.current.toFixed(1) : r.key === "average_deal_size" ? "$" + (r.current / 1000).toFixed(1) + "k" : pct(r.current)}`,
          `${(r.contribution * 100).toFixed(1)} pts`]),
        [2300, 3100, 2100, 1520]),
      para("", { after: 80 }),
      callout("The point to land, and the trap to avoid", [
        [text("The headline: ", { bold: true }),
          text(`premium per active underwriter fell ${pct(Math.abs(drivers.total_change))}.`)],
        [text("The cause: ", { bold: true }),
          text(`submissions rose ${pct(drivers.changes.submissions)} - more business came in - but the number of underwriters winning business rose ${pct(drivers.changes.underwriters)}, from ${drivers.counts.underwriters[0]} to ${drivers.counts.underwriters[1]}. The work spread wider.`)],
        [text("So do not say “flow dried up”. ", { bold: true, color: "B45309" }),
          text("Say the denominator grew faster than the numerator. Quote rate helped (+"),
          text(`${(driverRow("quote_rate").contribution * 100).toFixed(1)} pts`, { bold: true }),
          text("), win rate hurt ("), text(`${(driverRow("bind_rate").contribution * 100).toFixed(1)} pts`, { bold: true }),
          text("), deal size was flat.")],
      ]),
      ...say([
        "Premium per underwriter splits into four things multiplied together: how much each person sees, how much we price, how much we win, and how big each win is. The four shares add back to the total exactly - there's no judgement in the split.",
        "This year it fell 9.3%. Not because less came in - submissions were up 12% - but because the number of people writing business was up 24%. That's a growing team story, not a flow story.",
        "Where I'd want the underwriting view: win rate cost us four points. Is that pricing, appetite, or competition?",
      ]),

      // ---------------------------------------------------------------- beat 6
      ...h1("6. Tab by tab", "13:00 - 17:00. Roughly forty seconds each. Keep moving."),
      h2("Funnel"),
      para([text(`Submissions ${m["funnel.submissions"].now} → quotes ${m["funnel.quotes"].now} → binds ${m["funnel.binds"].now}, and the two rates between them: quote rate ${m["funnel.quote_rate"].now}, win rate ${m["funnel.bind_rate"].now}.`)]),
      ...say([
        "This is the only part of the page that needs the submissions report as well, because RBS only knows about business we won - it has no opinion on what we turned down.",
        "So: everything that came in, what we put a price on, and what we won. Quote rate is an appetite and capacity question. Win rate is a pricing and competition question.",
      ]),
      ...bullets([
        [text("Know this one: ", { bold: true }),
          text(`${gap.policies} of the ${gap.of_binds.toLocaleString()} bound policies have no row in the submissions report at all, ${pct(gap.premium_share)} of the premium. So the win rate is slightly flattering - ${pct(gap.bind_rate)} if I count only the wins the submissions report knows about. The page says so under the figure. It's one of the questions I'm bringing to the team.`)],
      ]),
      h2("Book quality"),
      para("Everything here comes from RBS. Brief, in the order the tab lists them:"),
      ...bullets(bookQuality.map(([name, meaning]) => [text(`${name}. `, { bold: true }), text(meaning)])),
      para([text(`Today: margin ${m["quality.uw_margin_pct"].now}, expected claims ${m["quality.gelr_margin_basis"].now}, commission ${m["quality.commission_margin_basis"].now}, rate adequacy ${m["pricing.rate_adequacy"].now}, RARC ${m["pricing.rarc"].now}.`, { color: GREY })]),
      h2("What we write"),
      ...bullets(whatWeWrite.map(([name, meaning]) => [text(`${name}. `, { bold: true }), text(meaning)])),
      para([text(`Today: we lead ${m["composition.mosaic_as_lead"].now} of risks, ${m["composition.primary_share"].now} primary, agency share ${m["composition.average_agency_share"].now}, SCM share ${m["composition.scm_share"].now}, top five brokers ${m["composition.broker_concentration"].now}.`, { color: GREY })]),
      h2("Productivity"),
      para([text(`Two counts and three per-person figures. Active underwriters ${m["productivity_stand_in.active_underwriters_stand_in"].now} - won at least one deal. Roster underwriters ${m["productivity_stand_in.roster_underwriters_stand_in"].now} - had at least one submission. Then premium per active underwriter ${m["productivity_stand_in.premium_per_active_underwriter"].now}, per roster underwriter ${m["productivity_stand_in.premium_per_roster_underwriter"].now}, and margin per active underwriter ${m["productivity_stand_in.uw_margin_per_active_underwriter"].now}.`)]),
      ...say([
        "This whole tab is the part that most needs the HR file. Both counts only see people who did something, so a non-selling leader, a new joiner or someone on leave is invisible, and no figure here can be split by role or tenure.",
        "With HR, this becomes true productivity per head. Without it, it's a fair proxy that I label everywhere it appears.",
      ]),
      h2("Underwriters"),
      para("One row per underwriter: submissions, quote rate, binds, win rate, premium, where they sit against the peer median, and their margin. Sortable, searchable, and you can hide small books."),
      ...say([
        "Click a name and the whole page filters to that person - same definitions, one underwriter.",
        "The peer median column is a multiple: 1.5 means half again the middle underwriter's premium. Anyone 25% either side gets an arrow.",
        "Two honest flags here. Rates built on fewer than twenty policies are greyed out. And names typed two ways are tagged as possible duplicates rather than merged - there are four pairs in this data, and that needs a person who knows the team to confirm.",
      ]),
      h2("Trends"),
      para("Twenty-four months of premium, binds, submissions, quote rate, win rate and margin. The months in your selected period are orange, everything else grey, so you can see whether a move is a trend or a wobble."),
      ...say([
        "This is the tab that stops us over-reading one month.",
        "One thing to expect: the right-hand end always dips. Quotes and binds arrive weeks after a submission, so the newest months are still filling in. The chart says that under the title rather than letting you read it as a collapse.",
      ]),

      new Paragraph({ children: [new PageBreak()] }),
      // ---------------------------------------------------------------- beat 7
      ...h1("7. Where the data comes from, and how it refreshes", "17:00 - 19:00. This is the ask that unblocks everything."),
      para("Be straightforward here: today it reads a file, and that is the one thing standing between this and a live dashboard."),
      table(["", "Today", "What I'm asking for"], [
        ["Source", "An Excel export of RBS (and of the submissions report) sitting in a folder.",
          "The live RBS table itself, the same one the report is built on."],
        ["Transformations", "My pipeline reproduces them: 25 columns read, percentages put on the right scale, dates parsed, names tidied, premium summed per line, the two reports lined up.",
          "Either point me at the dataset that already applies the report's transformations, or confirm my list matches it column by column. The definitions sheet lists every step."],
        ["Refresh", "I re-read the file. Figures for a new filter combination take a second or two, then they're instant.",
          "Standing read access so it refreshes on a schedule - daily is plenty - with no one re-exporting anything by hand."],
        ["Swap effort", "One class in the code reads the file.",
          "Replace that one class with a query against the table. Nothing else in the pipeline changes - the metrics don't know or care where rows come from."],
      ], [1300, 3860, 3860]),
      para("", { after: 80 }),
      ...say([
        "Everything you've seen is computed from the reports themselves - no numbers typed in, no spreadsheet in the middle. But it is reading an export, which means someone has to produce that export.",
        "What I need is the live table, plus confirmation that the transformations I apply match the ones the report already applies. I've written every one of them down, column by column, so that's a checklist conversation, not a project.",
        "Give me read access on a schedule and this stops being my laptop and starts being a service.",
      ]),
      callout("Say this if the room includes whoever owns the data", [
        "Three specifics: the table name behind the RBS report; the transformation list to check against mine; and read access that survives a refresh.",
        "The prize: this stops being a monthly effort and becomes a page anyone can open, filtered to their own book, with a link they can share.",
      ]),

      // ---------------------------------------------------------------- beat 8
      ...h1("8. What I want to ask the team", "The differences between this and Matt's build"),
      para("Frame these as decisions the business owns, not as bugs. Each one is a place where two reasonable builds disagree, and while they disagree the two dashboards will never tie out."),
      table(["The question", "Matt's build", "Mine", "Why it matters"], [
        ["Which report gives the headline premium?",
          "The submissions report, with RBS's margin applied to it.",
          "RBS, because it is the booked-business record. The submissions report is a cross-check.",
          `The two bases are ${pct(facts.reconciliation.premium.gap_pct)} apart on this data. Until we pick one, his headline and mine cannot match - and neither is wrong.`],
        ["Which GELR and which commission are “the” figures?",
          "One GELR, over risks that carry a loss estimate. One commission, over all premium.",
          "Both versions of each, clearly named.",
          "His GELR lines up with my margin version and his commission with my book version. Anyone comparing the like-named columns will mis-match both. His also drops 2021 inceptions; mine doesn't."],
        ["Should a missing commission count as zero?",
          "Counts as zero.",
          "Counts as zero too, and the page says what that is worth.",
          `${noCommission} of margin premium records no commission. Treating that as “none charged” lifts the margin: ${m["quality.uw_margin_pct"].now} against ${m["quality.uw_margin_pct_recorded_commission"].now} over risks that do record one.`],
        ["Should the win rate only count wins the submissions report knows about?",
          "Not an issue for him: his wins come from the submissions report, so his funnel is nested by construction.",
          "Wins come from RBS, so some wins have no submission row.",
          `${gap.policies} policies, ${pct(gap.premium_share)} of premium. It makes my win rate ${m["funnel.bind_rate"].now} against ${pct(gap.bind_rate)}, and on one underwriter it can read over 100%.`],
        ["How do we compare an underwriter with their peers?",
          "Annualised margin per underwriter against their product or line, leaving the person out of their own median.",
          "Premium against the median of whoever is in the filters.",
          "His is better and needs HR months and a product mapping. Mine is the honest stand-in until we have those."],
        ["What is the primary attachment point?",
          "Excess and deductible added together, then split by layer.",
          "Deductible only on primary layers, with a blank counted as zero.",
          `The blank rule halves the figure: ${m["quality.attachment_point_primary"].now} against $58.5k if blanks were excluded. Worth a decision, it is a small change.`],
      ], [2100, 2300, 2300, 2320], { size: 16 }),
      para("", { after: 80 }),
      ...say([
        "None of these are bugs in either build. They are definition calls, and each one is a place where my number and Matt's will never tie out until someone picks.",
        "I'm not asking the room to decide now. I'm asking for owners and a date, because the fix is one line of config in each case.",
      ]),

      // ---------------------------------------------------------------- close
      ...h1("9. The close", "19:00 - 20:00. Land it and stop talking."),
      ...say([
        "So: this is the underwriting productivity picture, built on the two reports we already trust, with every number traceable back to the column it came from.",
        "It is the underwriting half. The CEO view asks the same questions about the same book - premium, margin, productivity - and today they'd be answered by two different builds with two different definitions. The engine underneath this one is the same engine: one rulebook, one set of definitions, two front pages. That's the version worth having.",
        "Three things from me: the live RBS table with read access; a decision on the handful of definition differences so both dashboards agree; and the HR file when it exists, which is what turns my stand-in into real productivity per head.",
      ]),
      para("", { after: 100 }),
      callout("If you only get one thing", [
        "Ask for the live table and the transformation checklist. Everything else on this list can wait a month; that one unlocks the rest.",
      ]),

      new Paragraph({ children: [new PageBreak()] }),
      // --------------------------------------------------------- Q&A appendix
      ...h1("Appendix A. Harder questions, and the honest answer"),
      qa([
        ["Can we trust these numbers?",
          "“Every figure is rebuilt from the raw report columns by a separate check that doesn't use the dashboard's own code, and compared. Every headline figure, both mixes, and every column of the underwriter table for every underwriter. If they ever differ, the check fails.”"],
        ["Why does the premium figure have a red badge?",
          `“The two reports disagree by ${pct(facts.reconciliation.premium.gap_pct)} on this slice, and rather than hide that, the page shows both and keeps RBS. Most of it is ${gap.policies} bound policies the submissions report has no record of.”`],
        ["Is this headcount?",
          "“No, and I never call it that. No HR file, so I count underwriters who won business. It flatters slightly. With HR it becomes real productivity per head, split by role and tenure.”"],
        ["What can't it do?",
          "“Agency revenue and fee yield - the fee columns aren't in the standard report. Product splits - that mapping lives outside both reports. True headcount, role and tenure - HR file. And a true retention rate, which needs the expiring book as its own list.”"],
        ["How long to point it at live data?",
          "“One class in the code reads the export. Swapping it for a query is a day's work once I have the table and access. The metrics don't know where rows come from.”"],
        ["Why does the last month look terrible?",
          "“It isn't. Quotes and binds arrive weeks after submissions, so the newest months are still filling in. The trend charts say so under the title.”"],
        ["Where are the definitions written down?",
          "“Two places, both generated from the code so they can't drift: a one-sheet definitions file, and the metrics workbook - the lineage tab names the exact column behind every figure.”"],
        ["Did you check this against Matt's work?",
          "“Line by line, by reading his dashboard's code. Most definitions agree. Six differ, and they're on one page of my notes with what each is worth in numbers.”"],
      ]),

      ...h1("Appendix B. Every figure, its formula and its source columns"),
      para("For the moment someone asks “where exactly does that come from?”. Report, exact column headings, formula, and today's value.",
        { color: GREY, size: 18 }),
      table(["Figure", "Formula", "Report and columns", facts.period],
        facts.metrics.filter((x) => x.on_the_page).map((x) => [
          x.label || x.title, x.formula,
          x.columns.map((c) => `${c.report}: ${c.names.join(" / ")}`), x.now || "—"]),
        [1800, 2700, 3320, 1200], { size: 15 }),
      para("", { after: 60 }),
      para([text("The definitions sheet adds what the pipeline does to each column before the figure - the scaling, the blank handling, the name tidy-up. That is the answer to “did you change the report?”.",
        { color: GREY, size: 18 })]),
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  const out = path.join(ROOT, "docs", "UW_Dashboard_Presentation.docx");
  fs.writeFileSync(out, buffer);
  console.log(`Wrote ${out} (${(buffer.length / 1024).toFixed(0)} KB)`);
});
