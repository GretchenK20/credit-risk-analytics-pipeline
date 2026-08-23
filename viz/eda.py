"""
EDA: Exploratory Data Analysis Layer
Tool: Matplotlib + Pandas
Data: data/gold/quarterly_mart_latest.csv, scatter_mart_latest.csv, bls_choropleth_latest.csv

Runs before Bokeh visualizations to:
1. Understand distributions of key variables
2. Check for outliers and skew
3. Examine correlations
4. Validate data quality
5. Identify the story before telling it

Outputs: data/eda/ folder with PNG charts + eda_summary.txt
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving files
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
EDA_DIR  = BASE_DIR / "data" / "eda"
EDA_DIR.mkdir(parents=True, exist_ok=True)

STYLE = {
    "red":    "#E8474C",
    "amber":  "#F4A225",
    "blue":   "#2166AC",
    "green":  "#4DAC26",
    "purple": "#7B2D8B",
    "gray":   "#888888",
    "bg":     "#FAFAFA",
}

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         10,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "figure.dpi":        120,
})

summary_lines = []

def log(msg):
    print(msg)
    summary_lines.append(msg)


# ── Load data ──────────────────────────────────────────────────────────────────
df = pd.read_csv(BASE_DIR / "data/gold/quarterly_mart_latest.csv", parse_dates=["date"])
scatter = pd.read_csv(BASE_DIR / "data/gold/scatter_mart_latest.csv", parse_dates=["date"])
bls = pd.read_csv(BASE_DIR / "data/gold/bls_choropleth_latest.csv")

df = df.sort_values("date").reset_index(drop=True)
df["quarter_label"] = df["date"].dt.year.astype(str) + " Q" + df["date"].dt.quarter.astype(str)

log("=" * 60)
log("CREDIT RISK ANALYTICS PIPELINE — EDA SUMMARY")
log("=" * 60)
log(f"\nDataset: {len(df)} quarters ({df['date'].min().date()} to {df['date'].max().date()})")
log(f"Columns: {list(df.select_dtypes(include=[np.number]).columns)}\n")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 1: Descriptive Statistics & Distributions
# ══════════════════════════════════════════════════════════════════════════════
log("--- EDA Figure 1: Distributions ---")

key_vars = {
    "delinquency_all":             ("Consumer Loan Delinquency Rate (%)", STYLE["red"]),
    "chargeoff_credit_card":       ("Credit Card Charge-Off Rate (%)",    STYLE["amber"]),
    "fed_funds_rate":              ("Federal Funds Rate (%)",              STYLE["blue"]),
    "unemployment_rate":           ("Unemployment Rate (%)",               STYLE["green"]),
    "consumer_credit_outstanding": ("Consumer Credit Outstanding",         STYLE["purple"]),
}

fig, axes = plt.subplots(2, 3, figsize=(14, 8))
fig.suptitle("EDA: Variable Distributions (2014–2024 Quarterly)", fontsize=13, fontweight="bold", y=1.01)
axes = axes.flatten()

for i, (col, (label, color)) in enumerate(key_vars.items()):
    ax = axes[i]
    if col not in df.columns:
        ax.set_visible(False)
        continue

    data = df[col].dropna()

    # Histogram + KDE
    ax.hist(data, bins=15, color=color, alpha=0.6, edgecolor="white", density=True)

    # KDE overlay
    kde_x = np.linspace(data.min(), data.max(), 200)
    kde = stats.gaussian_kde(data)
    ax.plot(kde_x, kde(kde_x), color=color, linewidth=2)

    # Mean + median lines
    ax.axvline(data.mean(),   color="black",      linestyle="--", linewidth=1.2, label=f"Mean: {data.mean():.2f}")
    ax.axvline(data.median(), color=STYLE["gray"], linestyle=":",  linewidth=1.2, label=f"Median: {data.median():.2f}")

    ax.set_title(label, fontsize=9, fontweight="bold")
    ax.set_xlabel("Value")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)

    # Stats annotation
    skew = stats.skew(data)
    kurt = stats.kurtosis(data)
    ax.text(0.97, 0.97, f"Skew: {skew:.2f}\nKurt: {kurt:.2f}",
            transform=ax.transAxes, fontsize=7.5,
            va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))

    log(f"  {col}: mean={data.mean():.3f}, std={data.std():.3f}, "
        f"skew={skew:.3f}, min={data.min():.3f}, max={data.max():.3f}")

axes[-1].set_visible(False)
fig.tight_layout()
out1 = EDA_DIR / "eda_fig1_distributions.png"
fig.savefig(out1, bbox_inches="tight", facecolor="white")
plt.close(fig)
log(f"\nSaved: {out1}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 2: Correlation Matrix
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 2: Correlation Matrix ---")

corr_cols = [c for c in key_vars.keys() if c in df.columns]
corr_labels = [key_vars[c][0].replace(" (%)", "").replace(" Outstanding", "") for c in corr_cols]
corr_matrix = df[corr_cols].corr()

fig, ax = plt.subplots(figsize=(8, 6))
fig.suptitle("EDA: Pearson Correlation Matrix", fontsize=13, fontweight="bold")

im = ax.imshow(corr_matrix.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
plt.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")

ax.set_xticks(range(len(corr_labels)))
ax.set_yticks(range(len(corr_labels)))
ax.set_xticklabels(corr_labels, rotation=30, ha="right", fontsize=9)
ax.set_yticklabels(corr_labels, fontsize=9)

# Annotate cells
for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        val = corr_matrix.values[i, j]
        color = "white" if abs(val) > 0.6 else "black"
        ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                fontsize=9, color=color, fontweight="bold")

fig.tight_layout()
out2 = EDA_DIR / "eda_fig2_correlation_matrix.png"
fig.savefig(out2, bbox_inches="tight", facecolor="white")
plt.close(fig)

log("  Key correlations:")
for i, c1 in enumerate(corr_cols):
    for j, c2 in enumerate(corr_cols):
        if i < j:
            r = corr_matrix.loc[c1, c2]
            if abs(r) > 0.4:
                log(f"    {c1} vs {c2}: r={r:.3f}")
log(f"\nSaved: {out2}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 3: Time Series Overview with Rolling Stats
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 3: Time Series with Rolling Stats ---")

fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
fig.suptitle("EDA: Time Series with 4-Quarter Rolling Mean", fontsize=13, fontweight="bold")

series_plot = [
    ("delinquency_all",       "Consumer Loan Delinquency Rate (%)", STYLE["red"]),
    ("chargeoff_credit_card", "Credit Card Charge-Off Rate (%)",    STYLE["amber"]),
    ("fed_funds_rate",        "Federal Funds Rate (%)",              STYLE["blue"]),
]

event_dates = {
    "COVID-19\nOnset":      "2020-03-15",
    "Fed Rate\nHike Cycle": "2022-03-15",
    "SVB\nCollapse":        "2023-03-10",
}

for ax, (col, label, color) in zip(axes, series_plot):
    if col not in df.columns:
        continue
    data = df[col].dropna()
    dates = df.loc[data.index, "date"]

    # Raw values
    ax.plot(dates, data, color=color, alpha=0.5, linewidth=1.2, label="Quarterly")

    # Rolling mean
    roll = data.rolling(4, min_periods=2).mean()
    ax.plot(dates, roll, color=color, linewidth=2.2, label="4Q Rolling Mean")

    # Shaded std band
    roll_std = data.rolling(4, min_periods=2).std()
    ax.fill_between(dates, roll - roll_std, roll + roll_std,
                    color=color, alpha=0.12, label="±1 Std Dev")

    # Event lines
    for evt_label, evt_date in event_dates.items():
        ax.axvline(pd.Timestamp(evt_date), color=STYLE["gray"],
                   linestyle="--", linewidth=1, alpha=0.7)

    ax.set_ylabel(label, fontsize=9)
    ax.legend(fontsize=8, loc="upper left")

    # Min/max annotations
    idx_max = data.idxmax()
    idx_min = data.idxmin()
    ax.annotate(f"Max: {data[idx_max]:.2f}%",
                xy=(df.loc[idx_max, "date"], data[idx_max]),
                xytext=(10, 5), textcoords="offset points",
                fontsize=8, color=color, fontweight="bold")
    ax.annotate(f"Min: {data[idx_min]:.2f}%",
                xy=(df.loc[idx_min, "date"], data[idx_min]),
                xytext=(10, -12), textcoords="offset points",
                fontsize=8, color=color)

axes[-1].set_xlabel("Quarter")
fig.tight_layout()
out3 = EDA_DIR / "eda_fig3_timeseries_rolling.png"
fig.savefig(out3, bbox_inches="tight", facecolor="white")
plt.close(fig)
log(f"Saved: {out3}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 4: Scatter Matrix (pairplot) — key variables
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 4: Scatter Matrix ---")

scatter_vars = ["delinquency_all", "unemployment_rate", "fed_funds_rate", "chargeoff_credit_card"]
scatter_vars = [c for c in scatter_vars if c in df.columns]
n = len(scatter_vars)

# Color by rate regime
regime_colors = {
    "Ultra-Low (<1%)": STYLE["blue"],
    "Low (1-3%)":      "#74ADD1",
    "Moderate (3-5%)": STYLE["amber"],
    "High (5%+)":      STYLE["red"],
    "Unknown":         STYLE["gray"],
}

fig, axes = plt.subplots(n, n, figsize=(11, 9))
fig.suptitle("EDA: Scatter Matrix — Key Credit Risk Variables\n(Color = Fed Funds Rate Regime)",
             fontsize=12, fontweight="bold")

for i, col_y in enumerate(scatter_vars):
    for j, col_x in enumerate(scatter_vars):
        ax = axes[i][j]
        ax.tick_params(labelsize=7)

        if i == j:
            # Diagonal: histogram
            data = df[col_y].dropna()
            ax.hist(data, bins=12, color=STYLE["blue"], alpha=0.6, edgecolor="white")
            ax.set_title(col_y.replace("_", "\n"), fontsize=7.5, pad=2)
        else:
            # Off-diagonal: scatter colored by regime
            for regime, color in regime_colors.items():
                mask = df["rate_regime"] == regime if "rate_regime" in df.columns else pd.Series([True]*len(df))
                sub = df[mask]
                if not sub.empty and col_x in sub.columns and col_y in sub.columns:
                    ax.scatter(sub[col_x], sub[col_y], c=color, s=18, alpha=0.65, label=regime)

            # Regression line
            valid = df[[col_x, col_y]].dropna()
            if len(valid) > 3:
                m, b, r, p, _ = stats.linregress(valid[col_x], valid[col_y])
                x_line = np.linspace(valid[col_x].min(), valid[col_x].max(), 50)
                ax.plot(x_line, m * x_line + b, color="black", linewidth=1, alpha=0.5)
                ax.text(0.05, 0.92, f"r={r:.2f}", transform=ax.transAxes,
                        fontsize=7, color="black")

        if i == n-1:
            ax.set_xlabel(col_x.replace("_", " "), fontsize=7.5)
        if j == 0:
            ax.set_ylabel(col_y.replace("_", " "), fontsize=7.5)

# Add legend
handles = [plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=c, markersize=7, label=r)
           for r, c in regime_colors.items() if r != "Unknown"]
fig.legend(handles=handles, title="Rate Regime", loc="lower right",
           fontsize=8, title_fontsize=8, framealpha=0.9)

fig.tight_layout()
out4 = EDA_DIR / "eda_fig4_scatter_matrix.png"
fig.savefig(out4, bbox_inches="tight", facecolor="white")
plt.close(fig)
log(f"Saved: {out4}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 5: Outlier Detection — Z-scores
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 5: Outlier Detection ---")

outlier_cols = ["delinquency_all", "chargeoff_credit_card", "fed_funds_rate", "unemployment_rate"]
outlier_cols = [c for c in outlier_cols if c in df.columns]

fig, axes = plt.subplots(1, len(outlier_cols), figsize=(14, 5))
fig.suptitle("EDA: Outlier Detection via Z-Score (|z| > 2.5 flagged)", fontsize=12, fontweight="bold")

for ax, col in zip(axes, outlier_cols):
    data = df[col].dropna()
    z    = np.abs(stats.zscore(data))
    outliers = z > 2.5

    ax.scatter(range(len(data)), data,
               c=[STYLE["red"] if o else STYLE["blue"] for o in outliers],
               s=20, alpha=0.75, zorder=3)

    # Mean ± 2.5 std bands
    mean, std = data.mean(), data.std()
    ax.axhline(mean,           color="black",      linestyle="-",  linewidth=1, label="Mean")
    ax.axhline(mean + 2.5*std, color=STYLE["red"], linestyle="--", linewidth=1, label="+2.5σ")
    ax.axhline(mean - 2.5*std, color=STYLE["red"], linestyle="--", linewidth=1, label="-2.5σ")
    ax.fill_between(range(len(data)), mean - 2.5*std, mean + 2.5*std,
                    color=STYLE["blue"], alpha=0.07)

    n_out = outliers.sum()
    ax.set_title(f"{col.replace('_', ' ')}\n({n_out} outliers)", fontsize=9, fontweight="bold")
    ax.set_xlabel("Quarter Index")
    ax.legend(fontsize=7.5)

    log(f"  {col}: {n_out} outliers (|z|>2.5)")
    if n_out > 0:
        outlier_qtrs = df.loc[data.index[outliers], "quarter_label"].tolist()
        log(f"    Outlier quarters: {outlier_qtrs}")

fig.tight_layout()
out5 = EDA_DIR / "eda_fig5_outlier_detection.png"
fig.savefig(out5, bbox_inches="tight", facecolor="white")
plt.close(fig)
log(f"Saved: {out5}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 6: Rate Regime Analysis — Box plots
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 6: Rate Regime Box Plots ---")

if "rate_regime" in df.columns:
    regime_order = ["Ultra-Low (<1%)", "Low (1-3%)", "Moderate (3-5%)", "High (5%+)"]
    regime_order = [r for r in regime_order if r in df["rate_regime"].unique()]
    regime_palette = [STYLE["blue"], "#74ADD1", STYLE["amber"], STYLE["red"]][:len(regime_order)]

    box_vars = ["delinquency_all", "chargeoff_credit_card"]
    box_vars = [c for c in box_vars if c in df.columns]

    fig, axes = plt.subplots(1, len(box_vars), figsize=(11, 5))
    fig.suptitle("EDA: Credit Stress by Interest Rate Regime", fontsize=12, fontweight="bold")

    for ax, col in zip(axes, box_vars):
        groups = [df[df["rate_regime"] == r][col].dropna().values for r in regime_order]
        bp = ax.boxplot(groups, patch_artist=True, notch=False,
                        medianprops=dict(color="black", linewidth=2))

        for patch, color in zip(bp["boxes"], regime_palette):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xticklabels(regime_order, rotation=20, ha="right", fontsize=8.5)
        ax.set_title(col.replace("_", " ").title(), fontsize=10, fontweight="bold")
        ax.set_ylabel("Rate (%)")

        # ANOVA test
        f_stat, p_val = stats.f_oneway(*[g for g in groups if len(g) > 1])
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        ax.text(0.98, 0.98, f"ANOVA: F={f_stat:.2f}, p={p_val:.4f} {sig}",
                transform=ax.transAxes, fontsize=8,
                ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        log(f"  {col} by regime — ANOVA F={f_stat:.3f}, p={p_val:.4f} {sig}")

    fig.tight_layout()
    out6 = EDA_DIR / "eda_fig6_regime_boxplots.png"
    fig.savefig(out6, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log(f"Saved: {out6}")


# ══════════════════════════════════════════════════════════════════════════════
# EDA FIGURE 7: BLS State Distribution
# ══════════════════════════════════════════════════════════════════════════════
log("\n--- EDA Figure 7: State Unemployment Distribution ---")

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("EDA: State Unemployment Distribution — December 2024", fontsize=12, fontweight="bold")

# Left: histogram
ax = axes[0]
ax.hist(bls["unemployment_rate"], bins=14, color=STYLE["blue"],
        alpha=0.7, edgecolor="white", density=False)
ax.axvline(bls["unemployment_rate"].mean(),   color=STYLE["red"],  linestyle="--",
           linewidth=1.5, label=f"Mean: {bls['unemployment_rate'].mean():.2f}%")
ax.axvline(bls["unemployment_rate"].median(), color=STYLE["amber"], linestyle=":",
           linewidth=1.5, label=f"Median: {bls['unemployment_rate'].median():.2f}%")
ax.set_xlabel("Unemployment Rate (%)")
ax.set_ylabel("Number of States")
ax.set_title("Distribution Across States")
ax.legend(fontsize=9)

# Right: top 10 / bottom 10 bar chart
ax2 = axes[1]
top10    = bls.nlargest(10, "unemployment_rate")
bottom10 = bls.nsmallest(10, "unemployment_rate")
combined = pd.concat([top10, bottom10]).drop_duplicates()
combined = combined.sort_values("unemployment_rate", ascending=True)

colors = [STYLE["red"] if r >= bls["unemployment_rate"].mean()
          else STYLE["green"] for r in combined["unemployment_rate"]]
ax2.barh(combined["state"], combined["unemployment_rate"], color=colors, alpha=0.8)
ax2.axvline(bls["unemployment_rate"].mean(), color="black", linestyle="--",
            linewidth=1, label=f"National avg: {bls['unemployment_rate'].mean():.2f}%")
ax2.set_xlabel("Unemployment Rate (%)")
ax2.set_title("Top 10 Highest & Lowest States")
ax2.legend(fontsize=9)

fig.tight_layout()
out7 = EDA_DIR / "eda_fig7_state_distribution.png"
fig.savefig(out7, bbox_inches="tight", facecolor="white")
plt.close(fig)
log(f"Saved: {out7}")

log(f"\n  State avg: {bls['unemployment_rate'].mean():.2f}%")
log(f"  State std: {bls['unemployment_rate'].std():.2f}%")
log(f"  Highest: {bls.loc[bls['unemployment_rate'].idxmax(), 'state']} ({bls['unemployment_rate'].max():.1f}%)")
log(f"  Lowest:  {bls.loc[bls['unemployment_rate'].idxmin(), 'state']} ({bls['unemployment_rate'].min():.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# Save summary text
# ══════════════════════════════════════════════════════════════════════════════
summary_path = EDA_DIR / "eda_summary.txt"
summary_path.write_text("\n".join(summary_lines))

print(f"\n{'='*60}")
print(f"EDA COMPLETE")
print(f"Outputs saved to: {EDA_DIR}")
print(f"{'='*60}")
print(f"  Fig 1: Distributions          → eda_fig1_distributions.png")
print(f"  Fig 2: Correlation Matrix     → eda_fig2_correlation_matrix.png")
print(f"  Fig 3: Time Series + Rolling  → eda_fig3_timeseries_rolling.png")
print(f"  Fig 4: Scatter Matrix         → eda_fig4_scatter_matrix.png")
print(f"  Fig 5: Outlier Detection      → eda_fig5_outlier_detection.png")
print(f"  Fig 6: Rate Regime Box Plots  → eda_fig6_regime_boxplots.png")
print(f"  Fig 7: State Distribution     → eda_fig7_state_distribution.png")
print(f"  Summary: eda_summary.txt")
