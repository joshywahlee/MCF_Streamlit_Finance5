# Finance Team 5 - Customer Financial Health & Commercial Behavior Score
# CSE 6748 Analytics Practicum - MCF NA Predictive Customer Intelligence
# Team: Joshua Lee, Karnali Vyawahare, Melanie Kurapatti
#
# How to run: streamlit run Finance5_Streamlit_App.py
# Then upload Finance5_Streamlit_Data.xlsx (created by the last cell of our Data Transformation notebook).
# The app does not save any data. The uploaded file is only kept while the browser tab is open.

import io

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Finance 5 | Customer Financial Health", layout="wide")


# Settings
TEAM = "Finance Team 5: Joshua Lee, Karnali Vyawahare, Melanie Kurapatti"
MCF_BLUE = "#27509B"
MCF_YELLOW = "#FCE500"

CHURN_BANDS = ["At-risk", "Watch", "Healthy"]
EXPANSION_BANDS = ["High", "Medium", "Low"]
GROUPS = ["Financial", "Commercial", "Engagement"]
GROUP_COLORS = ["#27509B", "#eb6834", "#1baf7a"]

# groups smaller than this are hidden in tables (sponsor data guideline)
MIN_GROUP_SIZE = 10

# sheets the notebook writes to the Excel file
SHEETS = ["Parents", "Accounts", "AR_History", "About", "Model_Metrics", "Coefficients", "Snapshot_Links"]


# Load the Excel file from the notebook
@st.cache_data(show_spinner="Reading the data file...")
def load_workbook(file_bytes):
    book = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)

    # check that every sheet is there
    for sheet in SHEETS:
        if sheet not in book:
            raise ValueError("The file is missing the sheet '" + sheet + "'. Re-run the notebook and upload the new file.")

    parents = book["Parents"]
    accounts = book["Accounts"]
    history = book["AR_History"]

    # keep IDs as text so they match across sheets
    parents["Parent Root"] = parents["Parent Root"].astype(str)
    accounts["Parent Root"] = accounts["Parent Root"].astype(str)
    accounts["Account Number"] = accounts["Account Number"].astype(str)
    history["Parent Root"] = history["Parent Root"].astype(str)
    history["Account Number"] = history["Account Number"].astype(str)
    history["Month"] = pd.to_datetime(history["Month"])

    parents["Segment"] = parents["Segment"].fillna("Unassigned").astype(str)
    parents["Caveats"] = parents["Caveats"].fillna("")
    return book


def uploader(key):
    uploaded = st.file_uploader("Upload Finance5_Streamlit_Data.xlsx", type=["xlsx"], key=key)
    if uploaded is not None:
        # only read the file again if it is a new file
        if st.session_state.get("file_name") != (uploaded.name, uploaded.size):
            try:
                st.session_state["book"] = load_workbook(uploaded.getvalue())
                st.session_state["file_name"] = (uploaded.name, uploaded.size)
                st.rerun()
            except Exception as error:
                st.error("Could not read the file: " + str(error))


def get_data():
    # every page except Home needs the file to be loaded first
    if "book" not in st.session_state:
        st.info("No data loaded yet. Please upload Finance5_Streamlit_Data.xlsx on the Home page.")
        st.stop()
    return st.session_state["book"]


def about_value(book, item):
    about = book["About"]
    match = about[about["Item"] == item]["Value"]
    if len(match) == 0:
        return "?"
    return match.iloc[0]


def show_data_date(book):
    st.caption(about_value(book, "Data as of") + " | Built: " + str(about_value(book, "Built"))
               + " | Churn model confidence: " + str(about_value(book, "Churn model confidence"))
               + " | Expansion model confidence: " + str(about_value(book, "Expansion model confidence")))


def hide_small_groups(table, count_col):
    # replace numbers with blanks for groups with fewer than MIN_GROUP_SIZE accounts
    table = table.copy()
    small = table[count_col] < MIN_GROUP_SIZE
    for col in table.columns:
        if col != count_col and pd.api.types.is_numeric_dtype(table[col]):
            table[col] = table[col].astype(float).where(~small)
    table[count_col] = table[count_col].astype(int).astype(str)
    table.loc[small, count_col] = "<" + str(MIN_GROUP_SIZE)
    return table


def band_text(band):
    if band == "At-risk":
        return ":red[**At-risk**]"
    if band == "Watch":
        return ":orange[**Watch**]"
    if band == "Healthy":
        return ":green[**Healthy**]"
    return ":blue[**" + str(band) + "**]"


# Page 1: Home
def page_home():
    st.title("Customer Financial Health & Commercial Behavior Score")
    st.write("MCF NA - Predictive Customer Intelligence - Financial & Sales domain")
    st.write(TEAM)
    st.write("Each parent account gets a **health score** (risk of full churn) and an **expansion score**. "
             "For each score the app shows the sub-scores it is built from, the top 3 drivers, a suggested next step, "
             "and which team should act on it.")

    if "book" not in st.session_state:
        st.subheader("Load the data")
        uploader("upload_home")
        st.caption("The app does not store any data. The file is only kept while this browser tab is open.")
        st.stop()

    book = st.session_state["book"]
    parents = book["Parents"]
    show_data_date(book)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Parent accounts scored", f"{len(parents):,}")
    col2.metric("At-risk + Watch", f"{parents['Churn_Band'].isin(['At-risk', 'Watch']).sum():,}")
    col3.metric("Expected full churns", f"{parents['Churn_Probability'].sum():,.0f}",
                help="Sum of the churn probabilities")
    col4.metric("High expansion", f"{(parents['Expansion_Band'] == 'High').sum():,}")

    st.subheader("Where to go")
    guide = pd.DataFrame({
        "Who": ["Strategic: Finance & Sales leadership",
                "Operational: B&C and CS managers",
                "Process executors: AM, AE, CSM, B&C staff",
                "Reference",
                "Reference"],
        "Page": ["Portfolio Health", "Priority Worklist", "Account 360", "How the Score Works", "Data Foundation"],
        "What it answers": ["Where is the risk and opportunity, who acts, how many devices are exposed",
                            "Which accounts go to which team, and why",
                            "Parent account, its child accounts and AR history, with drivers and next step",
                            "Definitions, validation results, variable weights, limits",
                            "How the monthly AR snapshots link to accounts"],
    })
    st.dataframe(guide, hide_index=True, width="stretch")

    with st.expander("Caveats that apply to every score"):
        caveats = book["About"][book["About"]["Item"] == "Caveat"]["Value"]
        for caveat in caveats:
            st.write("- " + caveat)


# Page 2: Portfolio Health (strategic view)
def page_portfolio():
    book = get_data()
    parents = book["Parents"]
    st.title("Portfolio Health")
    st.caption("Strategic view: where churn risk and expansion opportunity are across the portfolio.")
    show_data_date(book)

    # filters
    col1, col2, col3 = st.columns(3)
    platforms = col1.multiselect("Platform", sorted(parents["Platform"].dropna().astype(str).unique()))
    segments = col2.multiselect("Segment", sorted(parents["Segment"].unique()))
    levels = col3.multiselect("Level", sorted(parents["Level"].dropna().unique()))

    df = parents.copy()
    if platforms:
        df = df[df["Platform"].astype(str).isin(platforms)]
    if segments:
        df = df[df["Segment"].isin(segments)]
    if levels:
        df = df[df["Level"].isin(levels)]

    if len(df) < MIN_GROUP_SIZE:
        st.warning("Fewer than 10 accounts match these filters, so the results are hidden.")
        st.stop()

    at_risk_or_watch = df["Churn_Band"].isin(["At-risk", "Watch"])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Parent accounts", f"{len(df):,}")
    col2.metric("At-risk", f"{(df['Churn_Band'] == 'At-risk').sum():,}")
    col3.metric("Expected full churns", f"{df['Churn_Probability'].sum():,.1f}")
    col4.metric("Devices in At-risk + Watch", f"{df.loc[at_risk_or_watch, 'Parent_Fleet_Size'].sum():,.0f}",
                help="Contract units (fleet size) of these accounts")
    col5.metric("High expansion", f"{(df['Expansion_Band'] == 'High').sum():,}")

    left, right = st.columns(2)

    # churn band vs expansion band
    with left:
        st.markdown("**Churn band vs. expansion band** (parent accounts)")
        counts = df.groupby(["Churn_Band", "Expansion_Band"]).size().reset_index(name="accounts")
        counts["label"] = counts["accounts"].astype(str)
        counts.loc[counts["accounts"] < MIN_GROUP_SIZE, "label"] = "<10"

        heatmap = alt.Chart(counts).mark_rect(stroke="white", strokeWidth=2).encode(
            x=alt.X("Expansion_Band:N", sort=EXPANSION_BANDS, title="Expansion band", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Churn_Band:N", sort=CHURN_BANDS, title="Churn band"),
            color=alt.Color("accounts:Q", scale=alt.Scale(range=["#E8EEF8", MCF_BLUE]), legend=None),
            tooltip=["Churn_Band", "Expansion_Band", "label"],
        )
        labels = alt.Chart(counts).mark_text(fontSize=14).encode(
            x=alt.X("Expansion_Band:N", sort=EXPANSION_BANDS),
            y=alt.Y("Churn_Band:N", sort=CHURN_BANDS),
            text="label:N",
            color=alt.condition("datum.accounts > 600", alt.value("white"), alt.value("black")),
        )
        st.altair_chart((heatmap + labels).properties(height=280), width="stretch")
        st.caption("At-risk accounts that are also High expansion should get a retention conversation before any upsell.")

    # accounts by route
    with right:
        st.markdown("**Who acts: parent accounts by route**")
        routes = df["Route"].value_counts().reset_index()
        routes.columns = ["Route", "accounts"]
        route_chart = alt.Chart(routes).mark_bar(color=MCF_BLUE).encode(
            x=alt.X("accounts:Q", title="Parent accounts"),
            y=alt.Y("Route:N", sort="-x", title=None),
            tooltip=["Route", "accounts"],
        )
        st.altair_chart(route_chart.properties(height=280), width="stretch")

    # breakdown table
    st.markdown("**Breakdown** (groups with fewer than 10 accounts are hidden)")
    breakdown_col = st.radio("Break down by", ["Platform", "Segment", "Level"], horizontal=True)
    df["group"] = df[breakdown_col].fillna("None").astype(str)
    breakdown = df.groupby("group").agg(
        accounts=("Parent Root", "count"),
        at_risk_pct=("Churn_Band", lambda s: (s == "At-risk").mean()),
        avg_churn_probability=("Churn_Probability", "mean"),
        high_expansion_pct=("Expansion_Band", lambda s: (s == "High").mean()),
        devices=("Parent_Fleet_Size", "sum"),
    ).reset_index()
    breakdown = breakdown.rename(columns={"group": breakdown_col}).sort_values("accounts", ascending=False)
    st.dataframe(hide_small_groups(breakdown, "accounts"), hide_index=True, width="stretch", column_config={
        "at_risk_pct": st.column_config.NumberColumn("At-risk %", format="percent"),
        "avg_churn_probability": st.column_config.NumberColumn("Avg churn probability", format="percent"),
        "high_expansion_pct": st.column_config.NumberColumn("High expansion %", format="percent"),
        "devices": st.column_config.NumberColumn("Devices under contract", format="%d"),
    })

    # most common top driver for at-risk and watch accounts
    st.markdown("**Most common top churn driver** (At-risk and Watch accounts)")
    drivers = df.loc[at_risk_or_watch, "Churn_Driver_1"].dropna().str.extract(r"^\[(\w+)\]\s*(.*)$")
    drivers.columns = ["group", "driver"]
    top_drivers = drivers.value_counts().reset_index(name="accounts").head(8)
    if len(top_drivers) > 0:
        driver_chart = alt.Chart(top_drivers).mark_bar().encode(
            x=alt.X("accounts:Q", title="Parent accounts"),
            y=alt.Y("driver:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320)),
            color=alt.Color("group:N", scale=alt.Scale(domain=GROUPS, range=GROUP_COLORS), title="Sub-score"),
            tooltip=["group", "driver", "accounts"],
        )
        st.altair_chart(driver_chart.properties(height=260), width="stretch")
    st.caption("Drivers show associations found by the model, not causes.")


# Page 3: Priority Worklist (operational view)
def page_worklist():
    book = get_data()
    parents = book["Parents"]
    st.title("Priority Worklist")
    st.caption("Operational view: each parent account is routed to the team that should act, with the reason and the next step.")
    show_data_date(book)

    all_routes = list(parents["Route"].value_counts().index)
    default_routes = [r for r in all_routes if r != "Monitor"]

    col1, col2, col3 = st.columns([2, 1, 1])
    routes = col1.multiselect("Route (team)", all_routes, default=default_routes)
    churn_bands = col2.multiselect("Churn band", CHURN_BANDS)
    expansion_bands = col3.multiselect("Expansion band", EXPANSION_BANDS)
    search = st.text_input("Search for an account token", placeholder="e.g. ACCT_01234")

    df = parents.copy()
    if routes:
        df = df[df["Route"].isin(routes)]
    if churn_bands:
        df = df[df["Churn_Band"].isin(churn_bands)]
    if expansion_bands:
        df = df[df["Expansion_Band"].isin(expansion_bands)]
    if search:
        df = df[df["Parent_Name"].astype(str).str.upper().str.contains(search.strip().upper(), na=False)]

    df = df.sort_values(["Churn_Probability", "Expansion_Probability"], ascending=False)

    columns = ["Parent_Name", "Level", "Child_Accounts", "Churn_Band", "Health_Score", "Expansion_Band",
               "Expansion_Score", "Route", "Churn_Driver_1", "Churn_Action_1", "Churn_Confidence"]
    st.write(f"**{len(df):,} parent accounts**, sorted by churn probability")

    table = st.dataframe(df[columns], hide_index=True, width="stretch", height=440,
                         on_select="rerun", selection_mode="single-row",
                         column_config={
                             "Parent_Name": "Account",
                             "Child_Accounts": "Child accounts",
                             "Churn_Band": "Churn band",
                             "Health_Score": st.column_config.NumberColumn("Health score", format="%.1f"),
                             "Expansion_Band": "Expansion band",
                             "Expansion_Score": st.column_config.NumberColumn("Expansion score", format="%.0f"),
                             "Churn_Driver_1": "Top churn driver",
                             "Churn_Action_1": "Next step",
                             "Churn_Confidence": "Confidence",
                         })

    col1, col2 = st.columns([1, 3])
    selected_rows = table.selection.rows
    if len(selected_rows) > 0:
        selected = df.iloc[selected_rows[0]]
        if col1.button("Open " + str(selected["Parent_Name"]) + " in Account 360", type="primary"):
            st.session_state["parent"] = selected["Parent Root"]
            st.switch_page(account_page)
    else:
        col1.caption("Select a row to open it in Account 360.")

    col2.download_button("Download this list (CSV)", df[columns].to_csv(index=False).encode(),
                         "finance5_worklist.csv", "text/csv")

    st.caption("Health score: 100 = safest. At-risk = lowest 10% of health scores, Watch = next 20%. "
               "The route is based on the group of the top churn driver. Financial drivers with support activity go to Support first.")


# Page 4: Account 360 (process executor view)
def subscore_chart(row, prefix):
    # bar chart of the points each group adds to the log-odds
    rows = []
    for group in GROUPS + ["Customer"]:
        points = row.get(prefix + "_" + group + "_Points", 0)
        if pd.isna(points):
            points = 0
        rows.append({"subscore": group, "points": float(points)})
    data = pd.DataFrame(rows)

    if prefix == "Churn":
        up_label = "raises churn risk"
        up_color = "#d03b3b"
    else:
        up_label = "raises expansion likelihood"
        up_color = MCF_BLUE
    data["direction"] = np.where(data["points"] > 0, up_label, "lowers it")

    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("points:Q", title="Log-odds points vs. an average account"),
        y=alt.Y("subscore:N", sort=GROUPS + ["Customer"], title=None),
        color=alt.Color("direction:N", scale=alt.Scale(domain=[up_label, "lowers it"], range=[up_color, "#9AA5B1"]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["subscore", alt.Tooltip("points:Q", format="+.2f"), "direction"],
    )
    return chart.properties(height=240)


def score_section(row, prefix):
    if prefix == "Churn":
        st.markdown("#### Churn risk (health score)")
        score = f"{row['Health_Score']:.1f}"
    else:
        st.markdown("#### Expansion")
        score = f"{row['Expansion_Score']:.0f}"

    col1, col2, col3 = st.columns(3)
    col1.metric("Score", score, help="Health score: 100 = safest. Expansion score: 100 = most likely to expand.")
    col2.markdown("Band  \n" + band_text(row[prefix + "_Band"]))
    col3.metric("Probability", f"{row[prefix + '_Probability'] * 100:.1f}%")
    st.caption("Confidence: " + str(row[prefix + "_Confidence"]))

    subscores = []
    for group in GROUPS:
        subscores.append(group + " " + f"{row[prefix + '_' + group + '_Subscore']:.0f}")
    st.caption("Sub-scores (0-100): " + ", ".join(subscores))

    st.altair_chart(subscore_chart(row, prefix), width="stretch")
    st.caption("log-odds = intercept + Financial + Commercial + Engagement + Customer points, then converted to a probability and a score.")

    st.markdown("**Drivers and suggested next step**")
    found_driver = False
    for k in [1, 2, 3]:
        driver = row.get(prefix + "_Driver_" + str(k))
        action = row.get(prefix + "_Action_" + str(k))
        if isinstance(driver, str) and driver != "":
            st.markdown("- " + driver + "  \n  Next step: *" + str(action) + "*")
            found_driver = True
    if not found_driver:
        st.caption("No strong driver: this account is close to the portfolio average.")


def page_account():
    book = get_data()
    parents = book["Parents"]
    accounts = book["Accounts"]
    history = book["AR_History"]
    st.title("Account 360")
    st.caption("Process executor view: parent account, its child accounts and AR history, with scores, drivers and next step.")

    # account picked on the worklist page (if any)
    picked = st.session_state.pop("parent", None)

    options = parents.sort_values("Churn_Probability", ascending=False)
    if st.toggle("Only show parents with child accounts", value=False):
        options = options[options["Level"] == "Parent with children"]

    ids = options["Parent Root"].tolist()
    names = {}
    for _, r in options.iterrows():
        names[r["Parent Root"]] = str(r["Parent_Name"]) + "  -  " + r["Churn_Band"] + " / " + r["Expansion_Band"] + " expansion"
    start = ids.index(picked) if picked in ids else 0
    root = st.selectbox("Parent account (sorted by churn risk)", ids, index=start, format_func=lambda x: names[x])
    row = parents.set_index("Parent Root").loc[root]

    st.subheader(str(row["Parent_Name"]))
    st.write(f"Level: **{row['Level']}** | Child accounts: **{int(row['Child_Accounts'])}** | Platform: **{row['Platform']}** | "
             f"Segment: **{row['Segment']}** | Devices under contract: **{row['Parent_Fleet_Size']:,.0f}**")

    # next step depends on the route
    if row["Route"] == "Monitor":
        next_step = "Monitor, no action needed"
    elif row["Route"] == "Account Executive - expansion":
        next_step = row["Expansion_Action_1"]
    else:
        next_step = row["Churn_Action_1"]
    st.write("**Route:** " + str(row["Route"]))
    st.write("**Next step:** " + str(next_step))

    left, right = st.columns(2)
    with left:
        score_section(row, "Churn")
    with right:
        score_section(row, "Expansion")

    if row["Caveats"] != "":
        st.info("Caveat: " + row["Caveats"])

    # child accounts
    children = accounts[accounts["Parent Root"] == root]
    st.subheader(f"Child accounts ({len(children)})")
    st.dataframe(children.drop(columns=["Parent Root"]), hide_index=True, width="stretch",
                 height=min(38 * len(children) + 40, 320))
    st.caption("Contact roles (driver, fleet manager, purchaser, accounts payable) are not in the release data. "
               "What we would need: Salesforce Contact role or AccountContactRelation.Roles.")

    # AR history
    st.subheader("AR history across the migration (monthly snapshots)")
    account_history = history[history["Parent Root"] == root]
    if len(account_history) == 0:
        st.caption("No monthly AR snapshot links to this account.")
        return

    account_names = accounts[["Account Number", "Account Name"]].drop_duplicates("Account Number")
    account_history = account_history.merge(account_names, on="Account Number", how="left")
    name_list = sorted(account_history["Account Name"].dropna().unique())
    shown = st.multiselect("Child accounts shown", name_list, default=name_list[:4])
    if shown:
        account_history = account_history[account_history["Account Name"].isin(shown)]

    long = account_history.melt(id_vars=["Account Name", "Month"], value_vars=["Total_AR_Rank", "PastDue180_Rank"],
                                var_name="measure", value_name="rank")
    long["measure"] = long["measure"].replace({"Total_AR_Rank": "Total AR rank", "PastDue180_Rank": ">180 rank"})

    line_chart = alt.Chart(long).mark_line(point=True).encode(
        x=alt.X("Month:T", title=None),
        y=alt.Y("rank:Q", title="Rank within the month", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        color=alt.Color("Account Name:N", legend=alt.Legend(orient="bottom", title="Account")),
        strokeDash=alt.StrokeDash("measure:N", legend=alt.Legend(orient="bottom", title="Measure")),
        tooltip=["Account Name", "measure", alt.Tooltip("Month:T", format="%b %Y"), alt.Tooltip("rank:Q", format=".0%")],
    )
    st.altair_chart(line_chart.properties(height=300), width="stretch")
    st.caption("These are ranks, not dollars, because financial values were transformed before release. "
               "A higher rank means a larger balance than other accounts that month.")


# Page 5: How the Score Works
def page_score():
    book = get_data()
    st.title("How the Score Works")
    show_data_date(book)

    st.subheader("Definitions")
    about = book["About"]
    st.dataframe(about[about["Item"] != "Caveat"], hide_index=True, width="stretch")

    st.subheader("Validation (20% test split)")
    st.dataframe(book["Model_Metrics"], hide_index=True, width="stretch")
    st.write("Accuracy, precision, recall and F1 are measured when the top 10% of probabilities are flagged "
             "(the size of the At-risk band). Our proposed thresholds: ROC-AUC of at least 0.65 = Medium confidence, "
             "at least 0.75 = High; top-10% lift of at least 2x; mean predicted close to the observed rate.")
    st.warning("When not to trust the churn score: it is built from one point-in-time extract, so it shows association, "
               "not a forecast window. Use it to rank accounts for review, not to predict when an account will leave.")

    st.subheader("Variable weights")
    model_choice = st.radio("Model", ["Churn", "Expansion"], horizontal=True)
    weights = book["Coefficients"]
    weights = weights[weights["Outcome"] == model_choice].copy()
    weights["size"] = weights["Coefficient"].abs()
    weights = weights.sort_values("size", ascending=False)

    weight_chart = alt.Chart(weights.head(15)).mark_bar().encode(
        x=alt.X("Coefficient:Q", title="Coefficient (log-odds per standard deviation)"),
        y=alt.Y("Label:N", sort=alt.EncodingSortField("size", order="descending"), title=None,
                axis=alt.Axis(labelLimit=320)),
        color=alt.Color("Group:N", scale=alt.Scale(domain=GROUPS + ["Customer"], range=GROUP_COLORS + ["#9AA5B1"])),
        tooltip=["Label", "Group", alt.Tooltip("Coefficient:Q", format="+.3f")],
    )
    st.altair_chart(weight_chart.properties(height=360), width="stretch")

    with st.expander("All weights (table)"):
        st.dataframe(weights.drop(columns=["size"]), hide_index=True, width="stretch")


# Page 6: Data Foundation
def page_data():
    book = get_data()
    st.title("Data Foundation")
    st.caption("How the monthly AR snapshots link to accounts across the migration.")
    show_data_date(book)

    links = book["Snapshot_Links"].copy()
    links["Month"] = pd.to_datetime("01-" + links["Snapshot"].astype(str), format="%d-%b_%y")

    st.markdown("**Snapshot rows linked to an account, by month**")
    link_chart = alt.Chart(links).mark_line(color="#1baf7a", point=True).encode(
        x=alt.X("Month:T", title=None),
        y=alt.Y("Link %:Q", title="Link rate (%)", scale=alt.Scale(domain=[50, 100])),
        tooltip=[alt.Tooltip("Month:T", format="%b %Y"), "Link %"],
    )
    st.altair_chart(link_chart.properties(height=260), width="stretch")
    st.caption("A jump in the link rate shows a change in how accounts were recorded (for example at the migration), "
               "not a change in customer behavior.")

    parents = book["Parents"]
    accounts = book["Accounts"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Accounts", f"{len(accounts):,}")
    col2.metric("Parent accounts scored", f"{len(parents):,}")
    col3.metric("Parents with child accounts", f"{(parents['Level'] == 'Parent with children').sum():,}")
    col4.metric("Accounts with no AR link", f"{(parents['Caveats'] != '').sum():,}",
                help="Financial variables are zero for these accounts")


# Navigation (pages grouped by who uses them)
home_page = st.Page(page_home, title="Home", default=True)
portfolio_page = st.Page(page_portfolio, title="Portfolio Health", url_path="portfolio")
worklist_page = st.Page(page_worklist, title="Priority Worklist", url_path="worklist")
account_page = st.Page(page_account, title="Account 360", url_path="account")
score_page = st.Page(page_score, title="How the Score Works", url_path="score")
data_page = st.Page(page_data, title="Data Foundation", url_path="data")

nav = st.navigation({
    "Start here": [home_page],
    "Strategic: Finance & Sales leadership": [portfolio_page],
    "Operational: B&C and CS managers": [worklist_page],
    "Process executors: AM, AE, CSM, B&C staff": [account_page],
    "Reference": [score_page, data_page],
})

with st.sidebar:
    st.markdown("**MCF NA - Finance Team 5**")
    st.caption("Customer Financial Health & Commercial Behavior Score")
    if "book" in st.session_state:
        st.success("Data loaded")
        with st.expander("Replace data"):
            uploader("upload_sidebar")
    st.caption("Uploaded data is only kept while this browser tab is open.")

nav.run()
