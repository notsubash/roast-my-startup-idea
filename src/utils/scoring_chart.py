import matplotlib

matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from judges.schemas import RoastPanel

_VERDICT_COLORS = {
    "PASS": "#2ecc71",
    "FAIL": "#e74c3c",
    "CONDITIONAL": "#f39c12",
}

_BG_COLOR = "#0e1117"
_GRID_COLOR = "#333333"
_TEXT_COLOR = "#fafafa"


def generate_radar_chart(
    roast_panel: RoastPanel,
    output_path: Path = Path("roast_radar.png"),
) -> Path:
    """Generate a radar chart of judge scores with dark-theme styling."""
    labels = [v.judge.value.upper() for v in roast_panel.verdicts]
    scores = [v.score for v in roast_panel.verdicts]
    colors = [_VERDICT_COLORS.get(v.verdict.value, "#95a5a6") for v in roast_panel.verdicts]

    num_vars = len(labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

    scores_closed = scores + scores[:1]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_facecolor(_BG_COLOR)

    ax.fill(angles_closed, scores_closed, alpha=0.20, color="#e74c3c")
    ax.plot(angles_closed, scores_closed, color="#e74c3c", linewidth=2, marker="o", markersize=8)

    for angle, score, color in zip(angles, scores, colors, strict=False):
        ax.plot(angle, score, "o", color=color, markersize=14, zorder=5)
        ax.annotate(
            str(score),
            xy=(angle, score),
            fontsize=11,
            fontweight="bold",
            ha="center",
            va="center",
            color="white",
            zorder=6,
        )

    ax.set_ylim(0, 10)
    ax.set_yticks(range(2, 11, 2))
    ax.set_yticklabels([str(i) for i in range(2, 11, 2)], fontsize=9, color="#888888")
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=12, fontweight="bold", color=_TEXT_COLOR)
    ax.set_title("Judge Scores", fontsize=16, pad=20, fontweight="bold", color=_TEXT_COLOR)

    ax.spines["polar"].set_color(_GRID_COLOR)
    ax.grid(color=_GRID_COLOR, linewidth=0.5)
    ax.tick_params(axis="y", colors="#888888")

    avg_score = sum(scores) / len(scores)
    ax.text(
        0.5,
        -0.08,
        f"Average: {avg_score:.1f}/10",
        transform=ax.transAxes,
        ha="center",
        fontsize=13,
        fontweight="bold",
        color=_TEXT_COLOR,
    )

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return output_path
