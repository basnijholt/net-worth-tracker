import matplotlib
import matplotlib.pyplot as plt
import numpy as np


def plot_pie_at_date(df, date, min_euro=1, show=True, fname=None, fig=None, ax=None):
    if fig is None:
        fig, ax = plt.subplots(figsize=(15, 15))
    else:
        ax.clear()
    df = df[df.value > min_euro]
    last = (
        df[df.date == date]
        .set_index("symbol")
        .value.dropna()
        .sort_values(ascending=False)
    )

    coins = sorted(df.symbol.unique())
    color_map = dict(
        zip(coins, matplotlib.cm.get_cmap("tab20c")(np.linspace(0, 1, len(coins))))
    )
    colors = [color_map[coin] for coin in last.index]

    patches, texts, _ = ax.pie(
        last, labels=last.index, colors=colors, autopct="%1.1f%%"
    )
    factor = 100 / last.sum()
    legend_labels = [
        f"{coin} - {factor*amount:1.2f}% - €{amount:.2f}"
        for coin, amount in last.items()
    ]

    ax.axis("equal")
    ax.legend(
        patches,
        legend_labels,
        loc="upper left",
        bbox_to_anchor=(-0.25, 1.0),
        fontsize=12,
    )
    ax.set_title(str(date))
    if fname is not None:
        plt.savefig(fname)
    if show:
        plt.show()
